from services.linkage_service import LinkageService, normalize_id

class MockAsset:
    def __init__(self, from_bus):
        self.from_primary_bus_id = from_bus

class MockPost:
    def __init__(self, pole_number, id):
        self.id = id
        self.pole_number = pole_number
        self.primary_bus_id = None
        self.pole_num = None

def test_matching():
    # Simulate a main highway pole and a lateral pole
    p125 = MockPost("125", 1)
    p125_4 = MockPost("125-4", 2)
    
    posts = [p125, p125_4]
    
    # Test case 1: Main highway bus ID
    asset1 = MockAsset("P0000000125")
    match1 = LinkageService.fuzzy_match_asset_to_post(asset1, posts=posts)
    print(f"Asset P0000000125 matches pole: {match1.pole_number if match1 else 'None'}")
    
    # Test case 2: Lateral bus ID
    asset2 = MockAsset("P0000000125-4")
    match2 = LinkageService.fuzzy_match_asset_to_post(asset2, posts=posts)
    print(f"Asset P0000000125-4 matches pole: {match2.pole_number if match2 else 'None'}")

    # Test case 3: Lateral bus ID where lateral pole is MISSING
    posts_missing = [p125]
    match3 = LinkageService.fuzzy_match_asset_to_post(asset2, posts=posts_missing)
    print(f"Asset P0000000125-4 (missing pole) matches pole: {match3.pole_number if match3 else 'None'}")

if __name__ == "__main__":
    test_matching()
