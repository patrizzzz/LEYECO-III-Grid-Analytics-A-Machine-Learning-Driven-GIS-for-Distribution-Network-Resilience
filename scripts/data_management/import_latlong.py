import logging
from app import app
from extensions import db
from models import LatLongData, Post

# Logger setup
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def is_valid_coordinate(lat, lng):
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return False
    return -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0


def is_in_philippines(lat, lng):
    """Return True if coordinates fall within an approximate bounding box of the Philippines."""
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        return False
    # Approximate bounds: latitude 4.0 to 22.0, longitude 116.0 to 127.5
    return (4.0 <= lat <= 22.0) and (116.0 <= lng <= 127.5)


def import_from_latlong():
    """Read all rows from latlongdata and upsert into Post table.
    Returns a dict with import statistics.
    """
    with app.app_context():
        # Attempt to read columns via DESCRIBE to find actual column names
        from sqlalchemy import text
        try:
            desc = db.session.execute(text('DESCRIBE latlongdata')).fetchall()
            col_names = [row[0] for row in desc]
        except Exception as e:
            logger.error(f"Failed to read from latlongdata table: {e}")
            return {'error': 'latlongdata table not found or DB error', 'detail': str(e)}

        logger.info(f"latlongdata columns detected: {col_names}")

        # Determine which columns map to post_id, latitude, longitude
        expected = ['post_id', 'latitude', 'longitude']
        mapping = {}
        lower_cols = [c.lower() for c in col_names]
        for name in expected:
            if name in lower_cols:
                mapping[name] = col_names[lower_cols.index(name)]

        # If any are missing, assume positional order: first=post_id, second=lat, third=lng
        if not all(k in mapping for k in expected):
            logger.warning('Column names do not match expected names; assuming first three columns are post_id, latitude, longitude in order')
            if len(col_names) < 3:
                return {'error': 'latlongdata does not have at least 3 columns'}
            mapping = {
                'post_id': col_names[0],
                'latitude': col_names[1],
                'longitude': col_names[2]
            }

        logger.info(f"Using columns: {mapping}")

        # Fetch rows using explicit column names
        try:
            sql = text(f"SELECT `{mapping['post_id']}` AS post_id, `{mapping['latitude']}` AS latitude, `{mapping['longitude']}` AS longitude FROM latlongdata")
            rows = db.session.execute(sql).fetchall()
        except Exception as e:
            logger.error(f"Failed to select from latlongdata: {e}")
            return {'error': 'failed to select from latlongdata', 'detail': str(e)}

        stats = {
            'total_rows': len(rows),
            'skipped_invalid': 0,
            'skipped_outside_ph': 0,
            'updated': 0,
            'created': 0,
        }

        for r in rows:
            # r is a Row; access by key or index
            try:
                pid_raw = r['post_id'] if 'post_id' in r.keys() else r[0]
            except Exception:
                pid_raw = r[0]
            try:
                lat_raw = r['latitude'] if 'latitude' in r.keys() else r[1]
            except Exception:
                lat_raw = r[1]
            try:
                lng_raw = r['longitude'] if 'longitude' in r.keys() else r[2]
            except Exception:
                lng_raw = r[2]

            # Validate post_id
            try:
                pid = int(pid_raw)
            except (TypeError, ValueError) as e:
                logger.warning(f"Skipping row with invalid post_id={pid_raw}: {e}")
                stats['skipped_invalid'] += 1
                continue

            # Validate coordinates
            if not is_valid_coordinate(lat_raw, lng_raw):
                logger.warning(f"Skipping post_id={pid} due to invalid coordinates: lat={lat_raw}, lng={lng_raw}")
                stats['skipped_invalid'] += 1
                continue

            lat = float(lat_raw)
            lng = float(lng_raw)

            # Ensure coordinates are within Philippines
            if not is_in_philippines(lat, lng):
                logger.warning(f"Skipping post_id={pid} as coordinates are outside the Philippines: ({lat},{lng})")
                stats['skipped_outside_ph'] += 1
                continue

            post = Post.query.get(pid)
            if post:
                if post.lat != lat or post.lng != lng:
                    logger.info(f"Updating Post {pid}: ({post.lat},{post.lng}) -> ({lat},{lng})")
                    post.lat = lat
                    post.lng = lng
                    stats['updated'] += 1
            else:
                post = Post(id=pid, name=f"Post {pid}", lat=lat, lng=lng)
                db.session.add(post)
                logger.info(f"Creating Post {pid} at ({lat},{lng})")
                stats['created'] += 1

        db.session.commit()
        logger.info(f"Import complete: {stats}")
        return stats


if __name__ == '__main__':
    stats = import_from_latlong()
    print(f"Import results: {stats}")
