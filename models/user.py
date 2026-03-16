from extensions import db
from datetime import datetime

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(128), unique=True, nullable=False)
    # Password hash; nullable to support viewer accounts (they use access codes instead)
    password_hash = db.Column(db.String(256), nullable=True)
    role = db.Column(db.String(32), default='viewer')
    # Viewer-specific fields
    access_code = db.Column(db.String(128), nullable=True, index=True)
    access_enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"

    def is_admin(self):
        return (self.role or '').lower() == 'admin'

    def is_viewer(self):
        return (self.role or '').lower() == 'viewer'

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'access_enabled': bool(self.access_enabled),
            'access_code': self.access_code if self.is_admin() else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def public_dict(self):
        """Public-safe dict (no secrets) for listing users"""
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'access_enabled': bool(self.access_enabled),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class UploadHistory(db.Model):
    """
    Log of uploaded files to track what data is currently loaded.
    """
    __tablename__ = 'upload_history'

    id = db.Column(db.Integer, primary_key=True)
    file_type = db.Column(db.String(50))   # 'posts', 'transformers', 'secondary_lines', 'service_drops'
    filename = db.Column(db.String(255))
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    record_count = db.Column(db.Integer, default=0) # Number of records processed/added
    status = db.Column(db.String(20), default='success')

    def to_dict(self):
        return {
            'id': self.id,
            'file_type': self.file_type,
            'filename': self.filename,
            'upload_date': self.upload_date.isoformat(),
            'record_count': self.record_count,
            'status': self.status
        }
