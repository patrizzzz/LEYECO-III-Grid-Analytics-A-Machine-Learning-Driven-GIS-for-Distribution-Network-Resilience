import pytest
import os
import sys
import sqlalchemy as sa
from unittest.mock import patch

# Add the current directory to sys.path so app can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load default testing environment
os.environ.setdefault("TESTING", "True")
os.environ.setdefault("SECRET_KEY", "test-key")

from app import app as flask_app
from extensions import db

@pytest.fixture
def app():
    # Use environment variables if set (e.g. by CI), otherwise fallback to a local test DB
    # We no longer default to sqlite because of PostGIS requirements
    test_db_url = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5432/app_test")
    
    with patch.dict(os.environ, {
        "DATABASE_URL": test_db_url,
        "TESTING": "True"
    }, clear=False):
        
        flask_app.config.update({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": test_db_url,
            "SECRET_KEY": "test-key"
        })
    
    with flask_app.app_context():
        # Ensure PostGIS extension is enabled in the test database
        try:
            db.session.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis"))
            db.session.commit()
        except Exception:
            pass # Might already be installed or user lacks permission

        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_app_health(client):
    """Test that the app home page loads."""
    rv = client.get('/')
    # The home page might redirect to login if not authenticated, 
    # but let's check for 200 or 302
    assert rv.status_code in [200, 302]

def test_api_transformer_risk(client):
    """Test the ML risk endpoint exists."""
    rv = client.get('/api/ml/transformer-risk')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'predictions' in data
    assert 'summary' in data
