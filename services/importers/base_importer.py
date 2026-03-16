import csv
import io
import re
from datetime import datetime
from flask import current_app
from extensions import db
from models import UploadHistory
from utils.import_helpers import find_column_value, sanitize_float

class BaseImporter:
    """
    Abstract base class for CSV importers.
    Subclasses must define 'file_type' and 'model_class'.
    """
    file_type = None
    model_class = None
    header_mappings = {}  # Map internal field names to possible CSV column names

    def __init__(self, csv_file):
        self.csv_file = csv_file
        self.filename = getattr(csv_file, 'filename', f"{self.file_type}.csv")
        self.stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}

    def normalize_header(self, header):
        if not header: return ""
        return re.sub(r'[^a-z0-9]+', '_', str(header).lower()).strip('_')

    def get_reader(self):
        try:
            if hasattr(self.csv_file, 'stream'):
                self.csv_file.stream.seek(0)
                content = self.csv_file.stream.read()
            else:
                self.csv_file.seek(0)
                content = self.csv_file.read()

            try:
                text = content.decode('utf-8-sig')
            except UnicodeDecodeError:
                text = content.decode('cp1252', errors='replace')

            stream = io.StringIO(text, newline=None)
            return csv.DictReader(stream)
        except Exception as e:
            current_app.logger.error(f"Failed to read CSV {self.filename}: {e}")
            return None

    def run(self):
        reader = self.get_reader()
        if reader is None:
            return {'error': f"Failed to read CSV: {self.filename}"}

        try:
            self.process_rows(reader)
            self.commit_changes()
            return self.stats
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Import failed for {self.filename}: {e}")
            return {'error': str(e)}

    def process_rows(self, reader):
        """Override this in subclasses for specific logic."""
        raise NotImplementedError

    def commit_changes(self):
        db.session.commit()
        if self.stats['created'] > 0 or self.stats['updated'] > 0:
            h = UploadHistory(
                file_type=self.file_type,
                filename=self.filename,
                record_count=self.stats['created'] + self.stats['updated']
            )
            db.session.add(h)
            db.session.commit()

    def get_val(self, row, field_name):
        """Helper to get a value using pre-defined mappings."""
        if isinstance(field_name, list):
            possible_cols = field_name
        else:
            possible_cols = self.header_mappings.get(field_name, [field_name])
        return find_column_value(row, possible_cols)
