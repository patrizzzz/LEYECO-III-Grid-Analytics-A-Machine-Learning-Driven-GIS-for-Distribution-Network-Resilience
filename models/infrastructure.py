from extensions import db
from datetime import datetime

class VoltageRegulator(db.Model):
    __tablename__ = 'voltage_regulator'
    id = db.Column(db.Integer, primary_key=True)
    regulator_id = db.Column(db.String(64), index=True)
    from_bus_id = db.Column(db.String(64))
    to_bus_id = db.Column(db.String(64))
    regulated_bus_id = db.Column(db.String(64))
    phase_type = db.Column(db.String(32))
    phasing = db.Column(db.String(32))
    phase_sense = db.Column(db.String(32))
    kva_rating = db.Column(db.Float)
    kv_rating = db.Column(db.Float)
    target_voltage = db.Column(db.Float)
    bandwidth = db.Column(db.Float)
    r_setting_a = db.Column(db.Float)
    r_setting_b = db.Column(db.Float)
    r_setting_c = db.Column(db.Float)
    x_setting_a = db.Column(db.Float)
    x_setting_b = db.Column(db.Float)
    x_setting_c = db.Column(db.Float)
    primary_current_rating = db.Column(db.Float)
    pt_ratio = db.Column(db.Float)
    no_load_loss_kw = db.Column(db.Float)
    exciting_current_pct = db.Column(db.Float)
    upload_id = db.Column(db.Integer, db.ForeignKey('upload_history.id'), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class ShuntCapacitor(db.Model):
    __tablename__ = 'shunt_capacitor'
    id = db.Column(db.Integer, primary_key=True)
    capacitor_id = db.Column(db.String(64), index=True)
    bus_connected_id = db.Column(db.String(64), index=True)
    phase_type = db.Column(db.String(32))
    phasing = db.Column(db.String(32))
    voltage_rating_kv = db.Column(db.Float)
    kvar_rating_a = db.Column(db.Float)
    kvar_rating_b = db.Column(db.Float)
    kvar_rating_c = db.Column(db.Float)
    power_loss_watts = db.Column(db.Float)
    upload_id = db.Column(db.Integer, db.ForeignKey('upload_history.id'), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class ShuntInductor(db.Model):
    __tablename__ = 'shunt_inductor'
    id = db.Column(db.Integer, primary_key=True)
    inductor_id = db.Column(db.String(64), index=True)
    bus_connected_id = db.Column(db.String(64), index=True)
    phase_type = db.Column(db.String(32))
    phasing = db.Column(db.String(32))
    voltage_rating_kv = db.Column(db.Float)
    resistance_a = db.Column(db.Float)
    resistance_b = db.Column(db.Float)
    resistance_c = db.Column(db.Float)
    reactance_a = db.Column(db.Float)
    reactance_b = db.Column(db.Float)
    reactance_c = db.Column(db.Float)
    upload_id = db.Column(db.Integer, db.ForeignKey('upload_history.id'), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class SeriesInductor(db.Model):
    __tablename__ = 'series_inductor'
    id = db.Column(db.Integer, primary_key=True)
    inductor_id = db.Column(db.String(64), index=True)
    from_bus_id = db.Column(db.String(64), index=True)
    to_bus_id = db.Column(db.String(64))
    phase_type = db.Column(db.String(32))
    phasing = db.Column(db.String(32))
    voltage_rating_kv = db.Column(db.Float)
    resistance_a = db.Column(db.Float)
    resistance_b = db.Column(db.Float)
    resistance_c = db.Column(db.Float)
    reactance_a = db.Column(db.Float)
    reactance_b = db.Column(db.Float)
    reactance_c = db.Column(db.Float)
    upload_id = db.Column(db.Integer, db.ForeignKey('upload_history.id'), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
