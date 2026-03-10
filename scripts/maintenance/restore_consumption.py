import os
from app import app
from extensions import db
from utils.csv_importers import import_energy_consumption_from_csv

def restore_data():
    csv_path = "exampleconsump.csv"
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found!")
        return

    print(f"Found {csv_path}. Starting import into {app.config['SQLALCHEMY_DATABASE_URI']}...")
    
    with app.app_context():
        # We need to mock a 'file' object for the importer which expects csv_file.stream.read()
        class MockFile:
            def __init__(self, path):
                self.path = path
                self.filename = os.path.basename(path)
                with open(path, 'rb') as f:
                    self.content = f.read()
            @property
            def stream(self):
                import io
                return io.BytesIO(self.content)

        mock_file = MockFile(csv_path)
        stats = import_energy_consumption_from_csv(mock_file)
        
        print("\nImport Stats:")
        print(f"Created: {stats.get('created', 0)}")
        print(f"Updated: {stats.get('updated', 0)}")
        print(f"Skipped: {stats.get('skipped', 0)}")
        
        if stats.get('errors'):
            print(f"Errors (first 5): {stats['errors'][:5]}")

if __name__ == "__main__":
    restore_data()
