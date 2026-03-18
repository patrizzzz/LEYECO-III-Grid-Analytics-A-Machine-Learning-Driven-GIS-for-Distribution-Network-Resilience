from app import app
from services.analysis_services import get_grid_health_analytics

def refresh():
    with app.app_context():
        print("Refreshing grid health analytics...")
        results = get_grid_health_analytics(force_refresh=True)
        print(f"Refresh complete. Total transformers: {results['summary']['total']}")
        print(f"Critical: {results['summary']['critical']}")

if __name__ == '__main__':
    refresh()
