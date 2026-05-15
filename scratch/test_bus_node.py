import requests

url = 'http://localhost:5000/api/bus-nodes/bulk-import'
files = {'file': ('test.csv', 'Bus ID,Pole Number,Nominal Voltage,Feeder,Latitude,Longitude\n1,1,13.2,F1,1.0,1.0\n')}
# Note: we need admin_required to be passed, which means we might need a session or we can just mock the import directly

if __name__ == '__main__':
    # Instead of hitting the API and dealing with auth, let's just run the importer directly
    from app import app
    from extensions import db
    from services.importers.asset_importer import BusNodeImporter
    from io import StringIO
    
    with app.app_context():
        # Fake a file
        class DummyFile:
            def __init__(self, content):
                self.filename = 'test.csv'
                self.content = content.encode('utf-8')
            def read(self):
                return self.content
            def seek(self, *args):
                pass
                
        f = DummyFile('Bus ID,Pole Number,Nominal Voltage,Feeder,Latitude,Longitude\n1,1,13.2,F1,1.0,1.0\n')
        importer = BusNodeImporter(f)
        try:
            res = importer.run()
            print("Success:", res)
        except Exception as e:
            import traceback
            traceback.print_exc()
