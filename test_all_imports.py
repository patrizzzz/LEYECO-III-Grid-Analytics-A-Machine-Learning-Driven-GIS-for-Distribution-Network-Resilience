from app import app
from services.importers.asset_importer import (
    VoltageRegulatorImporter, ShuntCapacitorImporter,
    ShuntInductorImporter, SeriesInductorImporter
)
from models import VoltageRegulator, ShuntCapacitor, ShuntInductor, SeriesInductor
import json

FILES = {
    'VR': ('exampleVR.csv', VoltageRegulatorImporter, VoltageRegulator),
    'SC': ('exampleSC.csv', ShuntCapacitorImporter, ShuntCapacitor),
    'SI': ('exampleSI.csv', ShuntInductorImporter, ShuntInductor),
    'SeriesI': ('exampleseriesI.csv', SeriesInductorImporter, SeriesInductor),
}

def test_all():
    results = {}
    with app.app_context():
        for name, (filename, ImporterClass, ModelClass) in FILES.items():
            filepath = f'data/samples/{filename}'
            try:
                class MockFile:
                    def __init__(self, stream, fn):
                        self.stream = stream
                        self.filename = fn
                with open(filepath, 'rb') as f:
                    mock = MockFile(f, filename)
                    importer = ImporterClass(mock)
                    stats = importer.run()
                    count = ModelClass.query.count()
                    results[name] = {'stats': stats, 'db_count': count}
            except Exception as e:
                results[name] = {'error': str(e)}

    with open('import_all_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print("Done. Results in import_all_results.json")

if __name__ == "__main__":
    test_all()
