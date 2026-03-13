import pytest
import os
import sys
from unittest.mock import patch

# Add the current directory to sys.path so app can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set environment variables for testing *before* importing the app
# to prevent it from loading production/dev database URLs from .env
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["TESTING"] = "True"
os.environ["SECRET_KEY"] = "test-key"

from app import app as flask_app
from extensions import db

@pytest.fixture
def app():
    # Crucial: isolate environment variables during testing so we never connect to the live DB
    with patch.dict(os.environ, {
        "DATABASE_URL": "",
        "DB_DATABASE": "",
        "DB_USERNAME": "",
        "DB_PASSWORD": ""
    }, clear=False):
        
        flask_app.config.update({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SECRET_KEY": "test-key"
        })
    
    with flask_app.app_context():
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
