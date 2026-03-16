from extensions import db
from datetime import datetime

class Customer(db.Model):
    __tablename__ = 'customer'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128))
    customer_type = db.Column(db.String(64))
    service_voltage = db.Column(db.String(32))
    phase = db.Column(db.String(32))
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'customer_id': self.customer_id,
            'name': self.name,
            'customer_type': self.customer_type,
            'service_voltage': self.service_voltage,
            'phase': self.phase,
            'lat': self.lat,
            'lng': self.lng,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class EnergyConsumption(db.Model):
    __tablename__ = 'energy_consumption'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.String(64), db.ForeignKey('customer.customer_id'), nullable=False, index=True)
    billing_period = db.Column(db.String(64))
    kwh_consumed = db.Column(db.Float)
    power_factor = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship('Customer', backref=db.backref('consumption_records', lazy=True))

    def to_dict(self):
         return {
            'id': self.id,
            'customer_id': self.customer_id,
            'billing_period': self.billing_period,
            'kwh_consumed': self.kwh_consumed,
            'power_factor': self.power_factor,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class LoadCurve(db.Model):
    __tablename__ = 'load_curve'
    id = db.Column(db.Integer, primary_key=True)
    load_curve_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    customer_type = db.Column(db.String(64), unique=True, index=True)
    description = db.Column(db.String(256))
    
    # 24 hourly multipliers
    hour_1 = db.Column(db.Float, default=1.0)
    hour_2 = db.Column(db.Float, default=1.0)
    hour_3 = db.Column(db.Float, default=1.0)
    hour_4 = db.Column(db.Float, default=1.0)
    hour_5 = db.Column(db.Float, default=1.0)
    hour_6 = db.Column(db.Float, default=1.0)
    hour_7 = db.Column(db.Float, default=1.0)
    hour_8 = db.Column(db.Float, default=1.0)
    hour_9 = db.Column(db.Float, default=1.0)
    hour_10 = db.Column(db.Float, default=1.0)
    hour_11 = db.Column(db.Float, default=1.0)
    hour_12 = db.Column(db.Float, default=1.0)
    hour_13 = db.Column(db.Float, default=1.0)
    hour_14 = db.Column(db.Float, default=1.0)
    hour_15 = db.Column(db.Float, default=1.0)
    hour_16 = db.Column(db.Float, default=1.0)
    hour_17 = db.Column(db.Float, default=1.0)
    hour_18 = db.Column(db.Float, default=1.0)
    hour_19 = db.Column(db.Float, default=1.0)
    hour_20 = db.Column(db.Float, default=1.0)
    hour_21 = db.Column(db.Float, default=1.0)
    hour_22 = db.Column(db.Float, default=1.0)
    hour_23 = db.Column(db.Float, default=1.0)
    hour_24 = db.Column(db.Float, default=1.0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        d = {
            'id': self.id,
            'load_curve_id': self.load_curve_id,
            'customer_type': self.customer_type,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        for i in range(1, 25):
            d[f'hour_{i}'] = getattr(self, f'hour_{i}')
        return d
