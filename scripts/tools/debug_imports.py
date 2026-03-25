try:
    print("Testing imports...")
    import flask
    print("Flask imported")
    import flask_sqlalchemy
    print("SQLAlchemy imported")
    from extensions import db
    print("extensions.db imported")
    from app import app
    print("app imported successfully")
except Exception as e:
    import traceback
    print("Error during import:")
    traceback.print_exc()
