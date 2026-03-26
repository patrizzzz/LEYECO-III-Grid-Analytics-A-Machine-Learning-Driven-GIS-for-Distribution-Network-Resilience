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
            # Use io.TextIOWrapper to stream from the file-like object without loading all into memory
            if hasattr(self.csv_file, 'stream'):
                self.csv_file.stream.seek(0)
                # Wrap the binary stream in a TextIOWrapper for line-by-line reading
                stream = io.TextIOWrapper(self.csv_file.stream, encoding='utf-8-sig', errors='replace')
            else:
                self.csv_file.seek(0)
                # Handle cases where it's already a text stream or bytes
                if hasattr(self.csv_file, 'read'):
                    first_bits = self.csv_file.read(1024)
                    self.csv_file.seek(0)
                    if isinstance(first_bits, bytes):
                        stream = io.TextIOWrapper(self.csv_file, encoding='utf-8-sig', errors='replace')
                    else:
                        stream = self.csv_file
                else:
                    return None

            return csv.DictReader(stream)
        except Exception as e:
            current_app.logger.error(f"Failed to read CSV {self.filename}: {e}")
            return None

    def run(self):
        reader = self.get_reader()
        if reader is None:
            return {'error': f"Failed to read CSV: {self.filename}"}

        try:
            # Create a history record at the start
            h = UploadHistory(
                file_type=self.file_type,
                filename=self.filename,
                status='processing'
            )
            db.session.add(h)
            db.session.flush()
            self.current_upload_id = h.id
            
            self.process_rows(reader)
            
            # Update history with final stats
            h.record_count = self.stats['created'] + self.stats['updated']
            h.status = 'success'
            
            db.session.commit()
            self.stats['upload_id'] = h.id
            return self.stats
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Import failed for {self.filename}: {e}")
            # Update history record to show failure if it was created
            try:
                # We need a new session or to avoid rolling back the whole thing if we want to log the error in DB
                # but standard practice is to let the 500 hander or the log show it if rollback happens.
                pass
            except: pass
            return {'error': str(e)}

    def process_rows(self, reader):
        """Override this in subclasses for specific logic."""
        raise NotImplementedError

    def commit_changes(self):
        """
        Deprecated. Use the context-managed run() flow instead.
        Internal commits should be handled via db.session.commit() or batching.
        """
        db.session.commit()

    def get_val(self, row, field_name):
        """Helper to get a value using pre-defined mappings."""
        if isinstance(field_name, list):
            possible_cols = field_name
        else:
            possible_cols = self.header_mappings.get(field_name, [field_name])
        return find_column_value(row, possible_cols)
