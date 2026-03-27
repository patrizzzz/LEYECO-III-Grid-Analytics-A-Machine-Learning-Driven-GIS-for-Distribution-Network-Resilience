import pytest
import io
from services.importers.asset_importer import PostImporter, BusNodeImporter
from services.importers.network_importer import PrimaryLineImporter
from models import Post, DistributionLineSegment, BusNode

def test_post_importer_basic(db, app):
    """Test importing posts from a CSV string."""
    csv_content = (
        "Name,Pole Number,latitude,longitude,Feeder\n"
        "Pole 1,P-001,10.5,124.5,FEEDER_A\n"
        "Pole 2,P-002,10.6,124.6,FEEDER_A\n"
    )
    
    file_obj = io.BytesIO(csv_content.encode('utf-8'))
    # BaseImporter expects an object with seek/read or stream
    importer = PostImporter(file_obj)
    
    result = importer.run()
    
    assert 'error' not in result
    assert result['created'] == 2
    
    # Verify DB state
    posts = Post.query.all()
    assert len(posts) == 2
    p1 = Post.query.filter_by(pole_number="P-001").first()
    assert p1.name == "Pole 1"
    assert p1.lat == 10.5
    assert p1.feeder == "FEEDER_A"

def test_primary_line_importer(db, app):
    """Test importing distribution line segments."""
    csv_content = (
        "Segment ID,From Bus ID,To Bus ID,Length (m)\n"
        "L-001,BUS_A,BUS_B,150.5\n"
    )
    
    file_obj = io.BytesIO(csv_content.encode('utf-8'))
    importer = PrimaryLineImporter(file_obj)
    
    result = importer.run()
    
    assert 'error' not in result
    assert result['created'] == 1
    
    line = DistributionLineSegment.query.first()
    assert line.segment_id == "L-001"
    assert line.from_bus_id == "BUS_A"
    assert line.length_meters == 150.5

def test_importer_invalid_csv(db, app):
    """Test importer behavior with invalid headers."""
    csv_content = "Wrong,Header,Only\n1,2,3"
    file_obj = io.BytesIO(csv_content.encode('utf-8'))
    importer = PostImporter(file_obj)
    
    # run() handles exceptions and returns stats or error dict
    result = importer.run()
    # If required columns like pole_number are missing, it might just skip or fail
    # In this case, process_rows skips if not pole_num
    assert result.get('created', 0) == 0

def test_primary_line_coordinates(db, app):
    """Test that primary line import synchronizes coordinates with BusNode."""
    csv_content = (
        "Primary Distribution Line Segment ID,From_Bus_ID,To_Bus_ID,latitude,longitude,Feeder\n"
        "SEG-001,BUS_START,BUS_END,11.1,124.1,F1\n"
    )
    
    file_obj = io.BytesIO(csv_content.encode('utf-8'))
    importer = PrimaryLineImporter(file_obj)
    
    result = importer.run()
    assert result['created'] == 1
    
    # 1. Check segment coordinates
    seg = DistributionLineSegment.query.filter_by(segment_id="SEG-001").first()
    assert seg.latitude == 11.1
    assert seg.longitude == 124.1
    
    # 2. Check BusNode synchronization
    bn = BusNode.query.filter_by(bus_id="BUS_END").first()
    assert bn is not None
    assert bn.lat == 11.1
    assert bn.lng == 124.1
    assert bn.feeder == "F1"

def test_bus_node_invalid_pole_id(db, app):
    """Test that BusNodeImporter ignores invalid pole IDs from CSV to avoid FK violations."""
    # 1. Setup: No posts in DB
    assert Post.query.count() == 0
    
    # 2. CSV with a pole_id that doesn't exist
    csv_content = (
        "Bus ID,Pole ID,Feeder\n"
        "BUS-001,999,F1\n"
    )
    
    file_obj = io.BytesIO(csv_content.encode('utf-8'))
    importer = BusNodeImporter(file_obj)
    
    # This should NOT raise ForeignKeyViolation
    result = importer.run()
    assert result['created'] == 1
    
    # 3. Verify that pole_id was NOT set to 999
    bn = BusNode.query.filter_by(bus_id="BUS-001").first()
    assert bn.pole_id is None
