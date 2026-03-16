from extensions import db
from datetime import datetime
from geoalchemy2 import Geometry

class Post(db.Model):
    """Electrical distribution pole/post with complete infrastructure data"""
    id = db.Column(db.Integer, primary_key=True)
    pole_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    area = db.Column(db.String(128))
    
    # Primary Side Infrastructure
    feeder = db.Column(db.String(64))
    pri_structure = db.Column(db.String(64))
    pri_conductor_size = db.Column(db.String(32))
    neutral_wire = db.Column(db.String(32))
    configuration = db.Column(db.String(64))
    phasing = db.Column(db.String(32))
    primary_bus_id = db.Column(db.String(64))
    
    # Secondary Side Infrastructure
    sec_structure = db.Column(db.String(64))
    sec_conductor_size = db.Column(db.String(32))
    sec_type = db.Column(db.String(64))
    conductor_type = db.Column(db.String(64))
    sec_bus_id = db.Column(db.String(64))
    
    # Transformer Data
    kva_rating = db.Column(db.Float)
    common_sole = db.Column(db.String(32))
    transformer_bus_id = db.Column(db.String(64))
    transformer_phasing = db.Column(db.String(32))
    grounding_rod = db.Column(db.String(32))
    
    # Meter Data
    meter_id = db.Column(db.String(128))
    meter_brand = db.Column(db.String(64))
    meter_rating = db.Column(db.Float)
    
    # Circuit & Connection Info
    circuit = db.Column(db.String(64))
    l2_conductor_size = db.Column(db.String(32))
    l2_wire_type = db.Column(db.String(32))
    l1_conductor_size = db.Column(db.String(32))
    l1_wire_type = db.Column(db.String(32))
    
    system_grounding_type = db.Column(db.String(64))
    length_meters = db.Column(db.Float)
    conductor_unit = db.Column(db.String(32))
    conductor_strands = db.Column(db.String(32))
    neutral_wire_type = db.Column(db.String(32))
    neutral_wire_size = db.Column(db.String(32))
    neutral_wire_unit = db.Column(db.String(32))
    neutral_wire_strands = db.Column(db.String(32))
    spacing_d12 = db.Column(db.Float)
    spacing_d23 = db.Column(db.Float)
    spacing_d13 = db.Column(db.Float)
    spacing_d1n = db.Column(db.Float)
    spacing_d2n = db.Column(db.Float)
    spacing_d3n = db.Column(db.Float)
    spacing_dc1_c2 = db.Column(db.Float)
    height_h1 = db.Column(db.Float)
    height_h2 = db.Column(db.Float)
    height_h3 = db.Column(db.Float)
    height_hn = db.Column(db.Float)
    earth_resistivity = db.Column(db.Float)
    has_transformer = db.Column(db.Boolean, default=False)
    geom = db.Column(Geometry('POINT', srid=4326))
    
    status = db.Column(db.String(64))
    upload_id = db.Column(db.Integer, db.ForeignKey('upload_history.id'), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    meters = db.relationship('Meter', back_populates='post', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Post {self.pole_number} ({self.lat}, {self.lng})>"
    
    def to_dict(self):
        d = {
            'id': self.id,
            'pole_number': self.pole_number,
            'name': self.name,
            'lat': self.lat,
            'lng': self.lng,
            'area': self.area,
            'feeder': self.feeder,
            'phasing': self.phasing,
            'kva_rating': self.kva_rating,
            'meter_id': self.meter_id,
            'meter_brand': self.meter_brand,
            'primary_bus_id': self.primary_bus_id,
            'status': self.status,
            'has_transformer': self.has_transformer,
        }
        for key in (
            'configuration', 'system_grounding_type', 'length_meters', 'conductor_type',
            'pri_conductor_size', 'conductor_unit', 'conductor_strands', 'neutral_wire',
            'neutral_wire_type', 'neutral_wire_size', 'neutral_wire_unit', 'neutral_wire_strands',
            'spacing_d12', 'spacing_d23', 'spacing_d13', 'spacing_d1n', 'spacing_d2n', 'spacing_d3n',
            'spacing_dc1_c2', 'height_h1', 'height_h2', 'height_h3', 'height_hn', 'earth_resistivity',
        ):
            val = getattr(self, key, None)
            if val is not None:
                d[key] = val
        return d

class Meter(db.Model):
    """Historical meter readings for a post"""
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    meter_id = db.Column(db.String(128), index=True)
    meter_brand = db.Column(db.String(64))
    meter_rating = db.Column(db.Float)
    kwhr_reading = db.Column(db.Float)
    reading_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    post = db.relationship('Post', back_populates='meters')

    def __repr__(self):
        return f"<Meter {self.meter_id} post={self.post_id} reading={self.kwhr_reading}>"

class LatLongData(db.Model):
    __tablename__ = 'latlongdata'
    post_id = db.Column(db.Integer, primary_key=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<LatLong post_id={self.post_id} ({self.latitude},{self.longitude})>"

class BusPostMapping(db.Model):
    __tablename__ = 'bus_post_mapping'
    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.String(64), nullable=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    upload_id = db.Column(db.Integer, db.ForeignKey('upload_history.id'), index=True)
    post = db.relationship('Post', backref=db.backref('bus_mappings', lazy='dynamic'))

    def __repr__(self):
        return f"<BusPostMapping bus_id={self.bus_id!r} -> post_id={self.post_id}>"

class BusNode(db.Model):
    __tablename__ = 'bus_node'
    id              = db.Column(db.Integer, primary_key=True)
    bus_id          = db.Column(db.String(128), unique=True, nullable=False, index=True)
    pole_number     = db.Column(db.String(128), index=True)
    bus_description = db.Column(db.String(128))
    bus_type        = db.Column(db.String(64))
    nominal_voltage = db.Column(db.Float)
    feeder          = db.Column(db.String(64), index=True)
    lat             = db.Column(db.Float)
    lng             = db.Column(db.Float)
    geom            = db.Column(Geometry('POINT', srid=4326))
    upload_id       = db.Column(db.Integer, db.ForeignKey('upload_history.id'), index=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<BusNode {self.bus_id!r} on Pole {self.pole_number!r}>"

    def to_dict(self):
        return {
            'id': self.id,
            'bus_id': self.bus_id,
            'pole_number': self.pole_number,
            'bus_description': self.bus_description,
            'bus_type': self.bus_type,
            'nominal_voltage': self.nominal_voltage,
            'feeder': self.feeder,
            'lat': self.lat,
            'lng': self.lng,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class DistributionLineSegment(db.Model):
    __tablename__ = 'distribution_line_segment'
    id = db.Column(db.Integer, primary_key=True)
    segment_id = db.Column(db.String(128), nullable=False, index=True)
    from_bus_id = db.Column(db.String(64), nullable=False)
    to_bus_id = db.Column(db.String(64), nullable=False)
    phasing = db.Column(db.String(32))
    configuration = db.Column(db.String(64))
    system_grounding_type = db.Column(db.String(64))
    length_meters = db.Column(db.Float)
    conductor_type = db.Column(db.String(32))
    conductor_size = db.Column(db.String(32))
    conductor_unit = db.Column(db.String(32))
    conductor_strands = db.Column(db.String(32))
    neutral_wire_type = db.Column(db.String(32))
    neutral_wire_size = db.Column(db.String(32))
    neutral_wire_unit = db.Column(db.String(32))
    neutral_wire_strands = db.Column(db.String(32))
    spacing_d12 = db.Column(db.Float)
    spacing_d23 = db.Column(db.Float)
    spacing_d13 = db.Column(db.Float)
    spacing_d1n = db.Column(db.Float)
    spacing_d2n = db.Column(db.Float)
    spacing_d3n = db.Column(db.Float)
    spacing_dc1_c2 = db.Column(db.Float)
    height_h1 = db.Column(db.Float)
    height_h2 = db.Column(db.Float)
    height_h3 = db.Column(db.Float)
    height_hn = db.Column(db.Float)
    earth_resistivity = db.Column(db.Float)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    geom = db.Column(Geometry('LINESTRING', srid=4326))
    upload_id = db.Column(db.Integer, db.ForeignKey('upload_history.id'), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DistributionLineSegment {self.segment_id!r} ({self.from_bus_id} → {self.to_bus_id})>"

    @property
    def wire_colors(self):
        if not self.phasing: return []
        p = self.phasing.upper().strip()
        colors = []
        if 'A' in p: colors.append('Brown (Phase A)')
        if 'B' in p: colors.append('Black (Phase B)')
        if 'C' in p: colors.append('Gray (Phase C)')
        if 'N' in p: colors.append('Blue (Neutral)')
        return colors

    def to_dict(self):
        return {
            'id': self.id, 'segment_id': self.segment_id, 'from_bus_id': self.from_bus_id,
            'to_bus_id': self.to_bus_id, 'phasing': self.phasing, 'wire_colors': self.wire_colors,
            'configuration': self.configuration, 'system_grounding_type': self.system_grounding_type,
            'length_meters': self.length_meters, 'conductor_type': self.conductor_type,
            'conductor_size': self.conductor_size, 'conductor_unit': self.conductor_unit,
            'conductor_strands': self.conductor_strands, 'neutral_wire_type': self.neutral_wire_type,
            'neutral_wire_size': self.neutral_wire_size, 'neutral_wire_unit': self.neutral_wire_unit,
            'neutral_wire_strands': self.neutral_wire_strands, 'spacing_d12': self.spacing_d12,
            'spacing_d23': self.spacing_d23, 'spacing_d13': self.spacing_d13, 'spacing_d1n': self.spacing_d1n,
            'spacing_d2n': self.spacing_d2n, 'spacing_d3n': self.spacing_d3n, 'spacing_dc1_c2': self.spacing_dc1_c2,
            'height_h1': self.height_h1, 'height_h2': self.height_h2, 'height_h3': self.height_h3,
            'height_hn': self.height_hn, 'earth_resistivity': self.earth_resistivity,
            'latitude': self.latitude, 'longitude': self.longitude,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class LineConnection(db.Model):
    __tablename__ = 'line_connection'
    id = db.Column(db.Integer, primary_key=True)
    from_bus = db.Column(db.String(64), nullable=False, index=True)
    to_bus = db.Column(db.String(64), nullable=False, index=True)
    connection_type = db.Column(db.String(32), nullable=False)
    feeder = db.Column(db.String(64), index=True)
    circuit = db.Column(db.String(64))
    phasing = db.Column(db.String(32))
    upload_id = db.Column(db.Integer, db.ForeignKey('upload_history.id'), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('from_bus', 'to_bus', 'connection_type', name='unique_connection'),)
    def __repr__(self):
        return f"<LineConnection {self.from_bus} → {self.to_bus} ({self.connection_type})>"
    def to_dict(self):
        return {
            'id': self.id, 'from_bus': self.from_bus, 'to_bus': self.to_bus,
            'connection_type': self.connection_type, 'feeder': self.feeder,
            'circuit': self.circuit, 'phasing': self.phasing,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class SecondaryLineSegment(db.Model):
    __tablename__ = 'secondary_line_segment'
    id = db.Column(db.Integer, primary_key=True)
    segment_id = db.Column(db.String(128), index=True)
    from_bus_id = db.Column(db.String(64), nullable=False, index=True)
    to_bus_id = db.Column(db.String(64), nullable=False, index=True)
    feeder = db.Column(db.String(64), index=True)
    circuit = db.Column(db.String(64))
    phasing = db.Column(db.String(32))
    length_meters = db.Column(db.Float)
    installation_type = db.Column(db.String(64))
    conductor_type = db.Column(db.String(32))
    conductor_size = db.Column(db.String(32))
    conductor_unit = db.Column(db.String(32))
    upload_id = db.Column(db.Integer, db.ForeignKey('upload_history.id'), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SecondaryLineSegment {self.from_bus_id} → {self.to_bus_id}>"

    def to_dict(self):
        return {
            'id': self.id, 'segment_id': self.segment_id, 'from_bus_id': self.from_bus_id,
            'to_bus_id': self.to_bus_id, 'feeder': self.feeder, 'circuit': self.circuit,
            'phasing': self.phasing, 'length_meters': self.length_meters,
            'installation_type': self.installation_type, 'conductor_type': self.conductor_type,
            'conductor_size': self.conductor_size, 'conductor_unit': self.conductor_unit,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class DistributionTransformer(db.Model):
    __tablename__ = 'distribution_transformer'
    id = db.Column(db.Integer, primary_key=True)
    transformer_id = db.Column(db.String(128), nullable=False, index=True)
    from_primary_bus_id = db.Column(db.String(64), nullable=False, index=True)
    to_secondary_bus_id = db.Column(db.String(64), index=True)
    primary_phasing = db.Column(db.String(32))
    secondary_phasing = db.Column(db.String(32))
    installation_type = db.Column(db.String(64))
    no_dts_in_bank = db.Column(db.Integer)
    connection = db.Column(db.String(32))
    kva_rating = db.Column(db.Float)
    primary_voltage_kv = db.Column(db.Float)
    secondary_voltage_kv = db.Column(db.Float)
    primary_tap_kv = db.Column(db.Float)
    secondary_tap_kv = db.Column(db.Float)
    pct_z = db.Column(db.Float)
    xr_ratio = db.Column(db.Float)
    no_load_loss_kw = db.Column(db.Float)
    exciting_current_pct = db.Column(db.Float)
    upload_id = db.Column(db.Integer, db.ForeignKey('upload_history.id'), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DistributionTransformer {self.transformer_id!r} @ {self.from_primary_bus_id}>"

    def to_dict(self):
        return {
            'id': self.id, 'transformer_id': self.transformer_id,
            'from_primary_bus_id': self.from_primary_bus_id, 'to_secondary_bus_id': self.to_secondary_bus_id,
            'primary_phasing': self.primary_phasing, 'secondary_phasing': self.secondary_phasing,
            'installation_type': self.installation_type, 'no_dts_in_bank': self.no_dts_in_bank,
            'connection': self.connection, 'kva_rating': self.kva_rating,
            'primary_voltage_kv': self.primary_voltage_kv, 'secondary_voltage_kv': self.secondary_voltage_kv,
            'primary_tap_kv': self.primary_tap_kv, 'secondary_tap_kv': self.secondary_tap_kv,
            'pct_z': self.pct_z, 'xr_ratio': self.xr_ratio, 'no_load_loss_kw': self.no_load_loss_kw,
            'exciting_current_pct': self.exciting_current_pct,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class SecondaryServiceDrop(db.Model):
    __tablename__ = 'secondary_service_drop'
    id = db.Column(db.Integer, primary_key=True)
    service_drop_id = db.Column(db.String(128), index=True)
    from_bus_id = db.Column(db.String(64), index=True)
    to_customer_id = db.Column(db.String(64), index=True)
    phasing = db.Column(db.String(10))
    installation_type = db.Column(db.String(64))
    length_meters_1 = db.Column(db.Float)
    length_meters_2 = db.Column(db.Float)
    conductor_type = db.Column(db.String(32))
    conductor_size = db.Column(db.String(32))
    conductor_unit = db.Column(db.String(16))
    upload_id = db.Column(db.Integer, db.ForeignKey('upload_history.id'), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SecondaryServiceDrop {self.service_drop_id} (Cust: {self.to_customer_id})>"

    def to_dict(self):
        return {
            'id': self.id, 'service_drop_id': self.service_drop_id, 'from_bus_id': self.from_bus_id,
            'to_customer_id': self.to_customer_id, 'phasing': self.phasing,
            'installation_type': self.installation_type, 'length_meters_1': self.length_meters_1,
            'length_meters_2': self.length_meters_2, 'conductor_type': self.conductor_type,
            'conductor_size': self.conductor_size, 'conductor_unit': self.conductor_unit,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
