import pytest
import os
import sys
import sqlalchemy as sa
from unittest.mock import patch

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Force testing mode
os.environ["TESTING"] = "True"
os.environ["SECRET_KEY"] = "test-secret-key"

from app import app as flask_app
from extensions import db as _db

@pytest.fixture(scope='session')
def app():
    """Session-wide test application."""
    # Safety: Ensure we don't accidentally wipe the production DB from .env
    env_db = os.getenv("DB_DATABASE", "mapping")
    test_db_url = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres@localhost:8080/leyeco3_test")
    
    # Force close any existing connections/engines from the app.py import
    with flask_app.app_context():
        _db.session.remove()
        _db.engine.dispose()

    if "mapping" in test_db_url.lower() or (env_db and env_db.lower() in test_db_url.lower()):
        pytest.exit(f"SAFETY ERROR: Test database URL '{test_db_url}' looks like the production database. Set TEST_DATABASE_URL to a safe test database.")

    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": test_db_url,
        "SECRET_KEY": "test-secret-key"
    })
    
    # Re-initialize with test config
    with flask_app.app_context():
        _db.engine.dispose() # Clear again to be safe
    
    with flask_app.app_context():
        # Ensure PostGIS exists
        try:
            _db.session.execute(sa.text("CREATE EXTENSION IF NOT EXISTS postgis"))
            _db.session.commit()
        except Exception:
            pass
            
        _db.create_all()
        yield flask_app
        try:
            _db.session.remove()
            _db.drop_all()
        except Exception:
            pass # Dependencies might remain in session scope

@pytest.fixture
def db(app):
    """Test database setup with automatic cleanup after each test."""
    with app.app_context():
        yield _db
        # Clean up all tables using CASCADE to handle foreign keys
        _db.session.rollback()
        try:
            # We use CASCADE to handle complex dependencies in PostgreSQL
            _db.session.execute(sa.text("""
                DO $$ DECLARE
                    r RECORD;
                BEGIN
                    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                        EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' CASCADE';
                    END LOOP;
                END $$;
            """))
            _db.session.commit()
        except Exception:
            _db.session.rollback()

@pytest.fixture
def client(app):
    """Test client."""
    return app.test_client()
