from extensions import db
from datetime import datetime
from geoalchemy2 import Geometry

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

    # helpers for passwords / access codes are implemented in application logic to avoid coupling
    def public_dict(self):
        """Public-safe dict (no secrets) for listing users"""
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'access_enabled': bool(self.access_enabled),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

class Post(db.Model):
    """Electrical distribution pole/post with complete infrastructure data"""
    id = db.Column(db.Integer, primary_key=True)
    pole_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    area = db.Column(db.String(128))
    
    # Primary Side Infrastructure
    feeder = db.Column(db.String(64))  # Feeder ID (e.g., "F6")
    pri_structure = db.Column(db.String(64))  # Primary Structure
    pri_conductor_size = db.Column(db.String(32))  # Primary Conductor Size
    neutral_wire = db.Column(db.String(32))  # Neutral Wire
    configuration = db.Column(db.String(64))  # Configuration (e.g., "Horizontal")
    phasing = db.Column(db.String(32))  # Phasing (e.g., "ABCN")
    primary_bus_id = db.Column(db.String(64))  # Primary Bus ID
    
    # Secondary Side Infrastructure
    sec_structure = db.Column(db.String(64))  # Secondary Structure
    sec_conductor_size = db.Column(db.String(32))  # Secondary Conductor Size
    sec_type = db.Column(db.String(64))  # Type (e.g., "Under Built")
    conductor_type = db.Column(db.String(64))  # Conductor Type (e.g., "Bare")
    sec_bus_id = db.Column(db.String(64))  # Secondary Bus ID
    
    # Transformer Data
    kva_rating = db.Column(db.Float)  # kVA Rating
    common_sole = db.Column(db.String(32))  # Common/Sole
    transformer_bus_id = db.Column(db.String(64))  # Transformer Bus ID
    transformer_phasing = db.Column(db.String(32))  # Transformer Phasing
    grounding_rod = db.Column(db.String(32))  # Grounding Rod (Yes/No)
    
    # Meter Data (stores latest meter)
    meter_id = db.Column(db.String(128))  # kWhr Meter ID/Serial
    meter_brand = db.Column(db.String(64))  # Meter Brand (Landis, Intec, Techen, etc.)
    meter_rating = db.Column(db.Float)  # Meter Rating (kWh)
    
    # Circuit & Connection Info
    circuit = db.Column(db.String(64))  # Circuit
    l2_conductor_size = db.Column(db.String(32))  # L2 Conductor Size
    l2_wire_type = db.Column(db.String(32))  # L2 Wire Type
    l1_conductor_size = db.Column(db.String(32))  # L1 Conductor Size
    l1_wire_type = db.Column(db.String(32))  # L1 Wire Type
    
    # Line segment / pole technical data (from CSV: phasing, configuration, conductor, spacing, height, etc.)
    system_grounding_type = db.Column(db.String(64))  # System Grounding Type (e.g., "Multi-grounded")
    length_meters = db.Column(db.Float)  # Length (meters)
    conductor_unit = db.Column(db.String(32))  # Unit (C) e.g. AWG, MCM
    conductor_strands = db.Column(db.String(32))  # Strands (C) e.g. 6/1
    neutral_wire_type = db.Column(db.String(32))  # Neutral Wire Type
    neutral_wire_size = db.Column(db.String(32))  # Neutral Wire Size
    neutral_wire_unit = db.Column(db.String(32))  # Unit (NW)
    neutral_wire_strands = db.Column(db.String(32))  # Strands (NW)
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
    earth_resistivity = db.Column(db.Float)  # Ohm-meter
    has_transformer = db.Column(db.Boolean, default=False)
    geom = db.Column(Geometry('POINT', srid=4326))
    
    # Tracking
    status = db.Column(db.String(64))
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
        # Pole/post technical columns (from CSV post coordinates import)
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
    meter_id = db.Column(db.String(128), index=True)  # Meter serial/ID
    meter_brand = db.Column(db.String(64))
    meter_rating = db.Column(db.Float)  # kWh rating
    kwhr_reading = db.Column(db.Float)  # Actual reading
    reading_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    post = db.relationship('Post', back_populates='meters')

    def __repr__(self):
        return f"<Meter {self.meter_id} post={self.post_id} reading={self.kwhr_reading}>"


class LatLongData(db.Model):
    """Represents existing table `latlongdata` with columns: post_id, latitude, longitude
    This maps to your external MySQL table and can be used to import/merge coordinates.
    """
    __tablename__ = 'latlongdata'

    post_id = db.Column(db.Integer, primary_key=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<LatLong post_id={self.post_id} ({self.latitude},{self.longitude})>"


# --- Bus–Post mapping: links engineering Bus IDs to map Post IDs (visualization only) ---
class BusPostMapping(db.Model):
    """Maps engineering feeder Bus IDs to Post IDs. Used only to draw feeder lines on the map.
    Does not store or infer any electrical logic."""
    __tablename__ = 'bus_post_mapping'

    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.String(64), nullable=False, index=True)   # Engineering data bus identifier
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

    post = db.relationship('Post', backref=db.backref('bus_mappings', lazy='dynamic'))

    def __repr__(self):
        return f"<BusPostMapping bus_id={self.bus_id!r} -> post_id={self.post_id}>"


# --- Bus Nodes: physical poles with GPS coordinates (Step 1 upload) ---
class BusNode(db.Model):
    """
    Each row represents one electrical bus on the network.
    The pole_number links to the physical Post where this bus is located.
    The lat/lng are cached from the Post for faster spatial queries.
    """
    __tablename__ = 'bus_node'

    id              = db.Column(db.Integer, primary_key=True)
    bus_id          = db.Column(db.String(128), unique=True, nullable=False, index=True)
    pole_number     = db.Column(db.String(128), index=True) # ID of the physical Post
    bus_description = db.Column(db.String(128))   # e.g. "Primary Line-Overhead"
    bus_type        = db.Column(db.String(64))     # "Primary Line-Overhead", "Distribution Transformer", "Secondary Line"
    nominal_voltage = db.Column(db.Float)          # kV
    feeder          = db.Column(db.String(64), index=True)
    lat             = db.Column(db.Float)          # Cached GPS latitude of the physical pole
    lng             = db.Column(db.Float)          # Cached GPS longitude of the physical pole
    geom            = db.Column(Geometry('POINT', srid=4326))
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


# --- Distribution Line Segments: electrical line data with technical specifications ---
class DistributionLineSegment(db.Model):
    """
    Electrical distribution line segment data with technical specifications.
    Connects two buses (From Bus ID → To Bus ID) with conductor and spacing details.
    """
    __tablename__ = 'distribution_line_segment'

    id = db.Column(db.Integer, primary_key=True)
    segment_id = db.Column(db.String(128), nullable=False, index=True)  # Primary Distribution Line Segment ID
    from_bus_id = db.Column(db.String(64), nullable=False)  # From Bus ID
    to_bus_id = db.Column(db.String(64), nullable=False)    # To Bus ID
    phasing = db.Column(db.String(32))  # Phasing (e.g., "ABCN")
    configuration = db.Column(db.String(64))  # Configuration (e.g., "Triangular")
    system_grounding_type = db.Column(db.String(64))  # System Grounding Type (e.g., "Multi-grounded")
    length_meters = db.Column(db.Float)  # Length (meters)
    conductor_type = db.Column(db.String(32))  # Conductor Type (e.g., "ACSR")
    conductor_size = db.Column(db.String(32))  # Conductor Size (e.g., "4/0")
    conductor_unit = db.Column(db.String(32))  # Unit (C) (e.g., "AWG")
    conductor_strands = db.Column(db.String(32))  # Strands (C) (e.g., "6/1")
    neutral_wire_type = db.Column(db.String(32))  # Neutral Wire Type (e.g., "ACSR")
    neutral_wire_size = db.Column(db.String(32))  # Neutral Wire Size (e.g., "2")
    neutral_wire_unit = db.Column(db.String(32))  # Unit (NW) (e.g., "AWG")
    neutral_wire_strands = db.Column(db.String(32))  # Strands (NW) (e.g., "6/1")
    
    # Spacing measurements (in meters)
    spacing_d12 = db.Column(db.Float)  # Spacing D12
    spacing_d23 = db.Column(db.Float)  # Spacing D23
    spacing_d13 = db.Column(db.Float)  # Spacing D13
    spacing_d1n = db.Column(db.Float)  # Spacing D1n
    spacing_d2n = db.Column(db.Float)  # Spacing D2n
    spacing_d3n = db.Column(db.Float)  # Spacing D3n
    spacing_dc1_c2 = db.Column(db.Float)  # Spacing DC1-C2
    
    # Height measurements (in meters)
    height_h1 = db.Column(db.Float)  # Height H1
    height_h2 = db.Column(db.Float)  # Height H2
    height_h3 = db.Column(db.Float)  # Height H3
    height_hn = db.Column(db.Float)  # Height Hn
    
    earth_resistivity = db.Column(db.Float)  # Earth Resistivity (Ohm-meter)
    
    # Coordinates for map visualization (if available)
    latitude = db.Column(db.Float)  # Latitude coordinate
    longitude = db.Column(db.Float)  # Longitude coordinate
    geom = db.Column(Geometry('LINESTRING', srid=4326))
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DistributionLineSegment {self.segment_id!r} ({self.from_bus_id} → {self.to_bus_id})>"

    @property
    def wire_colors(self):
        """
        Determines wire colors based on Philippine IEC standard.
        A=Brown, B=Black, C=Gray, N=Blue.
        """
        if not self.phasing:
            return []
        
        p = self.phasing.upper().strip()
        colors = []
        
        # Check presence of each phase/neutral in standard order
        if 'A' in p: colors.append('Brown (Phase A)')
        if 'B' in p: colors.append('Black (Phase B)')
        if 'C' in p: colors.append('Gray (Phase C)')
        if 'N' in p: colors.append('Blue (Neutral)')
        
        return colors

    def to_dict(self):
        return {
            'id': self.id,
            'segment_id': self.segment_id,
            'from_bus_id': self.from_bus_id,
            'to_bus_id': self.to_bus_id,
            'phasing': self.phasing,
            'wire_colors': self.wire_colors, # Added field
            'configuration': self.configuration,
            'system_grounding_type': self.system_grounding_type,
            'length_meters': self.length_meters,
            'conductor_type': self.conductor_type,
            'conductor_size': self.conductor_size,
            'conductor_unit': self.conductor_unit,
            'conductor_strands': self.conductor_strands,
            'neutral_wire_type': self.neutral_wire_type,
            'neutral_wire_size': self.neutral_wire_size,
            'neutral_wire_unit': self.neutral_wire_unit,
            'neutral_wire_strands': self.neutral_wire_strands,
            'spacing_d12': self.spacing_d12,
            'spacing_d23': self.spacing_d23,
            'spacing_d13': self.spacing_d13,
            'spacing_d1n': self.spacing_d1n,
            'spacing_d2n': self.spacing_d2n,
            'spacing_d3n': self.spacing_d3n,
            'spacing_dc1_c2': self.spacing_dc1_c2,
            'height_h1': self.height_h1,
            'height_h2': self.height_h2,
            'height_h3': self.height_h3,
            'height_hn': self.height_hn,
            'earth_resistivity': self.earth_resistivity,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# --- Inferred Line Connections: Network topology inferred from infrastructure data ---
class LineConnection(db.Model):
    """
    Inferred electrical line connections from infrastructure data.
    These are network edges connecting bus nodes based on pole infrastructure.
    
    Connections are inferred from: Primary Bus → Primary Bus, Primary → Transformer,
    Transformer → Secondary, and Secondary → Secondary relationships.
    """
    __tablename__ = 'line_connection'

    id = db.Column(db.Integer, primary_key=True)
    from_bus = db.Column(db.String(64), nullable=False, index=True)  # Source bus ID
    to_bus = db.Column(db.String(64), nullable=False, index=True)    # Destination bus ID
    connection_type = db.Column(db.String(32), nullable=False)  # "Primary_to_Primary", "Primary_to_Transformer", etc.
    feeder = db.Column(db.String(64), index=True)  # Feeder ID (e.g., "F6")
    circuit = db.Column(db.String(64))  # Circuit designation (e.g., "3 Phase")
    phasing = db.Column(db.String(32))  # Phasing (e.g., "ABCN")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('from_bus', 'to_bus', 'connection_type', name='unique_connection'),
    )

    def __repr__(self):
        return f"<LineConnection {self.from_bus} → {self.to_bus} ({self.connection_type})>"

    def to_dict(self):
        return {
            'id': self.id,
            'from_bus': self.from_bus,
            'to_bus': self.to_bus,
            'connection_type': self.connection_type,
            'feeder': self.feeder,
            'circuit': self.circuit,
            'phasing': self.phasing,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# --- Secondary Line Segments: from transformer secondary to post primary bus ---
class SecondaryLineSegment(db.Model):
    """
    Secondary circuit line segment. Connects:
    - from_bus_id: transformer's to_secondary_bus_id (line starts at transformer secondary)
    - to_bus_id: post's primary_bus_id (line ends at primary bus of a post/segment)

    Same linkage idea as distribution transformer: secondary line from_bus_id is connected
    to a transformer's to_secondary_bus_id; secondary line to_bus_id is connected to
    primary_bus_id of a post (or primary segment).
    """
    __tablename__ = 'secondary_line_segment'

    id = db.Column(db.Integer, primary_key=True)
    segment_id = db.Column(db.String(128), index=True)  # Optional segment identifier
    from_bus_id = db.Column(db.String(64), nullable=False, index=True)  # Transformer's to_secondary_bus_id
    to_bus_id = db.Column(db.String(64), nullable=False, index=True)    # Post's primary_bus_id
    feeder = db.Column(db.String(64), index=True)
    circuit = db.Column(db.String(64))
    phasing = db.Column(db.String(32))
    length_meters = db.Column(db.Float)
    installation_type = db.Column(db.String(64))   # e.g. Pole-mounted, Aerial
    conductor_type = db.Column(db.String(32))      # Conductor Type
    conductor_size = db.Column(db.String(32))      # Conductor Size
    conductor_unit = db.Column(db.String(32))      # Unit (C) e.g. AWG, MCM
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SecondaryLineSegment {self.from_bus_id} → {self.to_bus_id}>"

    def to_dict(self):
        return {
            'id': self.id,
            'segment_id': self.segment_id,
            'from_bus_id': self.from_bus_id,
            'to_bus_id': self.to_bus_id,
            'feeder': self.feeder,
            'circuit': self.circuit,
            'phasing': self.phasing,
            'length_meters': self.length_meters,
            'installation_type': self.installation_type,
            'conductor_type': self.conductor_type,
            'conductor_size': self.conductor_size,
            'conductor_unit': self.conductor_unit,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# --- Distribution Transformers: linked to posts by From Primary Bus ID ---
class DistributionTransformer(db.Model):
    """
    Distribution transformer data (example2.csv style).
    Linked to a post where post.primary_bus_id or post.pole_number equals from_primary_bus_id.
    """
    __tablename__ = 'distribution_transformer'

    id = db.Column(db.Integer, primary_key=True)
    transformer_id = db.Column(db.String(128), nullable=False, index=True)  # Distribution Transformer ID
    from_primary_bus_id = db.Column(db.String(64), nullable=False, index=True)  # From Primary Bus ID (links to Post)
    to_secondary_bus_id = db.Column(db.String(64), index=True)  # To Secondary Bus ID
    primary_phasing = db.Column(db.String(32))
    secondary_phasing = db.Column(db.String(32))
    installation_type = db.Column(db.String(64))  # e.g. Pole-mounted
    no_dts_in_bank = db.Column(db.Integer)  # No. DTs in Bank
    connection = db.Column(db.String(32))  # Connection
    kva_rating = db.Column(db.Float)  # KVA Rating
    primary_voltage_kv = db.Column(db.Float)  # Primary Voltage Rating (kV)
    secondary_voltage_kv = db.Column(db.Float)  # Secondary Voltage Rating (kV)
    primary_tap_kv = db.Column(db.Float)  # Primary Tap Voltage (kV)
    secondary_tap_kv = db.Column(db.Float)  # Secondary Tap Voltage (kV)
    pct_z = db.Column(db.Float)  # %Z
    xr_ratio = db.Column(db.Float)  # X/R Ratio
    no_load_loss_kw = db.Column(db.Float)  # No-Load Loss (kW)
    exciting_current_pct = db.Column(db.Float)  # Exciting Current (%)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DistributionTransformer {self.transformer_id!r} @ {self.from_primary_bus_id}>"

    def to_dict(self):
        return {
            'id': self.id,
            'transformer_id': self.transformer_id,
            'from_primary_bus_id': self.from_primary_bus_id,
            'to_secondary_bus_id': self.to_secondary_bus_id,
            'primary_phasing': self.primary_phasing,
            'secondary_phasing': self.secondary_phasing,
            'installation_type': self.installation_type,
            'no_dts_in_bank': self.no_dts_in_bank,
            'connection': self.connection,
            'kva_rating': self.kva_rating,
            'primary_voltage_kv': self.primary_voltage_kv,
            'secondary_voltage_kv': self.secondary_voltage_kv,
            'primary_tap_kv': self.primary_tap_kv,
            'secondary_tap_kv': self.secondary_tap_kv,
            'pct_z': self.pct_z,
            'xr_ratio': self.xr_ratio,
            'no_load_loss_kw': self.no_load_loss_kw,
            'exciting_current_pct': self.exciting_current_pct,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

# --- Secondary Service Drops: linked to Secondary Lines or Posts ---
class SecondaryServiceDrop(db.Model):
    """
    Secondary Service Drop data (exampleSLD.csv).
    Linked via 'From Bus ID' which technically connects to a Post or Secondary Line content.
    """
    __tablename__ = 'secondary_service_drop'

    id = db.Column(db.Integer, primary_key=True)
    service_drop_id = db.Column(db.String(128), index=True) # Secondary Customer Service Drop ID
    from_bus_id = db.Column(db.String(64), index=True)      # From Bus ID
    to_customer_id = db.Column(db.String(64), index=True)               # To Customer ID
    phasing = db.Column(db.String(10))
    installation_type = db.Column(db.String(64))
    length_meters_1 = db.Column(db.Float)                   # Length-1 (meters)
    length_meters_2 = db.Column(db.Float)                   # Length-2 (meters)
    conductor_type = db.Column(db.String(32))
    conductor_size = db.Column(db.String(32))
    conductor_unit = db.Column(db.String(16))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<SecondaryServiceDrop {self.service_drop_id} (Cust: {self.to_customer_id})>"

    def to_dict(self):
        return {
            'id': self.id,
            'service_drop_id': self.service_drop_id,
            'from_bus_id': self.from_bus_id,
            'to_customer_id': self.to_customer_id,
            'phasing': self.phasing,
            'installation_type': self.installation_type,
            'length_meters_1': self.length_meters_1,
            'length_meters_2': self.length_meters_2,
            'conductor_type': self.conductor_type,
            'conductor_size': self.conductor_size,
            'conductor_unit': self.conductor_unit,
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
    target_voltage = db.Column(db.Float) # 120V base
    bandwidth = db.Column(db.Float)      # 120V base
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

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

# --- Customer & Consumption Data ---
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
    # Linking by string ID from CSV
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
