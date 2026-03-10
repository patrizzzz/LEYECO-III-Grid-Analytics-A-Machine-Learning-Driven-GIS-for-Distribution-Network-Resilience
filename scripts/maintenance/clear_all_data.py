#!/usr/bin/env python3
"""
Clear ALL data from the database (for testing purposes).
WARNING: This will DELETE all records from all data tables!

Clears:
- LineConnection (network connections)
- DistributionLineSegment (line segments)
- DistributionTransformer (distribution transformers)
- BusPostMapping (bus-post mappings)
- Meter (meter readings)
- Post (poles/posts)
- LatLongData (coordinate data)

Preserves:
- User accounts (for login)
- Database schema/structure
"""

from app import app
from extensions import db
from models import (
    Post, Meter, LineConnection, DistributionLineSegment, 
    DistributionTransformer, BusPostMapping, LatLongData
)

def clear_all_data():
    """Delete all data from all tables (preserves users and schema)."""
    with app.app_context():
        try:
            print("=" * 70)
            print("CLEARING ALL DATABASE DATA")
            print("=" * 70)
            
            # Get counts before deletion (handle tables that might not exist)
            counts_before = {}
            tables_to_clear = [
                ('LineConnection', LineConnection),
                ('DistributionLineSegment', DistributionLineSegment),
                ('DistributionTransformer', DistributionTransformer),
                ('BusPostMapping', BusPostMapping),
                ('Meter', Meter),
                ('Post', Post),
            ]
            
            # Try LatLongData separately since it might not exist
            try:
                tables_to_clear.append(('LatLongData', LatLongData))
            except:
                pass
            
            print("\nCurrent data counts:")
            for table_name, model in tables_to_clear:
                try:
                    count = model.query.count()
                    counts_before[table_name] = count
                    print(f"   {table_name:30} {count:6} records")
                except Exception as e:
                    print(f"   {table_name:30} [SKIP] Table may not exist: {e}")
                    counts_before[table_name] = 0
            
            print("\nDeleting data (respecting foreign key constraints)...")
            
            # Delete in order to respect foreign key constraints
            deleted_counts = {}
            
            # 1. Delete connections first (they reference buses/posts)
            try:
                deleted_counts['LineConnection'] = LineConnection.query.delete()
                print(f"   [OK] Deleted {deleted_counts['LineConnection']} line connections")
            except Exception as e:
                print(f"   [SKIP] LineConnection: {e}")
                deleted_counts['LineConnection'] = 0
            
            # 2. Delete distribution line segments
            try:
                deleted_counts['DistributionLineSegment'] = DistributionLineSegment.query.delete()
                print(f"   [OK] Deleted {deleted_counts['DistributionLineSegment']} distribution line segments")
            except Exception as e:
                print(f"   [SKIP] DistributionLineSegment: {e}")
                deleted_counts['DistributionLineSegment'] = 0
            
            # 3. Delete distribution transformers
            try:
                deleted_counts['DistributionTransformer'] = DistributionTransformer.query.delete()
                print(f"   [OK] Deleted {deleted_counts['DistributionTransformer']} distribution transformers")
            except Exception as e:
                print(f"   [SKIP] DistributionTransformer: {e}")
                deleted_counts['DistributionTransformer'] = 0
            
            # 4. Delete bus-post mappings
            try:
                deleted_counts['BusPostMapping'] = BusPostMapping.query.delete()
                print(f"   [OK] Deleted {deleted_counts['BusPostMapping']} bus-post mappings")
            except Exception as e:
                print(f"   [SKIP] BusPostMapping: {e}")
                deleted_counts['BusPostMapping'] = 0
            
            # 5. Delete meter readings (they reference posts)
            try:
                deleted_counts['Meter'] = Meter.query.delete()
                print(f"   [OK] Deleted {deleted_counts['Meter']} meter readings")
            except Exception as e:
                print(f"   [SKIP] Meter: {e}")
                deleted_counts['Meter'] = 0
            
            # 6. Delete posts (they may reference other tables but are the main data)
            try:
                deleted_counts['Post'] = Post.query.delete()
                print(f"   [OK] Deleted {deleted_counts['Post']} posts")
            except Exception as e:
                print(f"   [SKIP] Post: {e}")
                deleted_counts['Post'] = 0
            
            # 7. Delete lat/long data (if table exists)
            try:
                deleted_counts['LatLongData'] = LatLongData.query.delete()
                print(f"   [OK] Deleted {deleted_counts['LatLongData']} lat/long records")
            except Exception as e:
                print(f"   [SKIP] LatLongData: {e}")
                deleted_counts['LatLongData'] = 0
            
            # Commit all deletions
            db.session.commit()
            
            # Verify deletion
            counts_after = {}
            for table_name, model in tables_to_clear:
                try:
                    counts_after[table_name] = model.query.count()
                except:
                    counts_after[table_name] = 0
            
            print("\n" + "=" * 70)
            print("DATABASE CLEARED SUCCESSFULLY")
            print("=" * 70)
            print("\nFinal counts (should all be 0):")
            for table, count in counts_after.items():
                status = "[OK]" if count == 0 else "[WARN]"
                print(f"   {status} {table:30} {count:6} records")
            
            print("\nDatabase is now empty and ready for fresh data import!")
            print("=" * 70)
            
            return True
            
        except Exception as e:
            db.session.rollback()
            print("\n" + "=" * 70)
            print(f"ERROR CLEARING DATABASE: {e}")
            print("=" * 70)
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("WARNING: This will DELETE ALL DATA from the database!")
    print("=" * 70)
    print("\nThis includes:")
    print("  • All posts/poles")
    print("  • All meter readings")
    print("  • All network connections")
    print("  • All distribution line segments")
    print("  • All distribution transformers")
    print("  • All bus-post mappings")
    print("  • All coordinate data")
    print("\nUser accounts will be preserved.")
    print("\n" + "-" * 70)
    
    confirm = input("\nType 'DELETE ALL' to confirm: ").strip()
    
    if confirm == 'DELETE ALL':
        clear_all_data()
    else:
        print("\n[SKIP] Deletion cancelled. No data was deleted.")
