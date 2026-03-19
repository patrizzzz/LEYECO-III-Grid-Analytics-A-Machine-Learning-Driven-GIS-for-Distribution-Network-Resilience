import os
import sys
import io
from unittest.mock import MagicMock, patch

# Mock the entire flask/extensions/models layer to avoid dependency issues
sys.modules['extensions'] = MagicMock()
sys.modules['models'] = MagicMock()
sys.modules['geoalchemy2'] = MagicMock()

# Import the stuff we want to test
# We might need to mock sanitize_float too if it's imported from somewhere problematic
from services.importers.asset_importer import PostImporter

def test_post_importer_logic():
    print("Running unit test for PostImporter logic...")
    
    # Setup mocks
    mock_post_class = MagicMock()
    # Mocking Post.query.all()
    mock_existing_post = MagicMock()
    mock_existing_post.pole_number = '1-300'
    mock_existing_post.name = 'Original Name'
    mock_existing_post.lat = 10.0
    mock_existing_post.lng = 20.0
    mock_existing_post.feeder = 'Feeder A'
    
    mock_post_class.query.all.return_value = [mock_existing_post]
    
    # Patch the Post model in the importer module
    with patch('services.importers.asset_importer.Post', mock_post_class), \
         patch('services.importers.asset_importer.db') as mock_db:
        
        # Test 1: Update existing pole (coordinates only)
        csv_content = "Post ID,Latitude,Longitude,Name,Feeder\n1-300,12.34,56.78,New Name,Feeder B"
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.filename = 'test.csv'
        
        importer = PostImporter(csv_file)
        importer.current_upload_id = 999
        stats = importer.run()
        
        print(f"Update stats: {stats}")
        assert stats['updated'] == 1
        assert stats['created'] == 0
        
        # Verify coordinates WERE updated
        assert mock_existing_post.lat == 12.34
        assert mock_existing_post.lng == 56.78
        # Verify name and feeder WERE NOT updated
        assert mock_existing_post.name == 'Original Name'
        assert mock_existing_post.feeder == 'Feeder A'
        print("✓ Test 1 Passed (Coordinate-only update)")

        # Test 2: Create new pole
        csv_content_new = "Post ID,Latitude,Longitude,Name,Feeder\nNEW-456,11.11,22.22,New Pole Name,Feeder C"
        csv_file_new = io.BytesIO(csv_content_new.encode('utf-8'))
        csv_file_new.filename = 'new.csv'
        
        # Reset mock for new call
        mock_post_instance = MagicMock()
        mock_post_class.return_value = mock_post_instance
        
        importer_new = PostImporter(csv_file_new)
        importer_new.current_upload_id = 888
        stats_new = importer_new.run()
        
        print(f"Create stats: {stats_new}")
        assert stats_new['created'] == 1
        
        # Verify new post fields
        mock_post_class.assert_called_with(pole_number='NEW-456')
        assert mock_post_instance.lat == 11.11
        assert mock_post_instance.lng == 22.22
        assert mock_post_instance.name == 'New Pole Name'
        assert mock_post_instance.feeder == 'Feeder C'
        print("✓ Test 2 Passed (New pole creation)")

    print("All unit tests PASSED successfully!")

if __name__ == "__main__":
    sys.path.append(os.getcwd())
    try:
        test_post_importer_logic()
    except Exception as e:
        print(f"Unit test FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
