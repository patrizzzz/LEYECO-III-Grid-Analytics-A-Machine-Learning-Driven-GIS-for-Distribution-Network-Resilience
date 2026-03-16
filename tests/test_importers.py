import pytest
import io
from services.importers.asset_importer import PostImporter
from services.importers.network_importer import PrimaryLineImporter
from models import Post, DistributionLineSegment

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
