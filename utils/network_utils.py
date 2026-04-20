import re
from models import LineConnection, DistributionLineSegment
from extensions import db

def normalize_bus_id(bus_id):
    """Normalize bus identifiers so equivalent IDs map consistently."""
    if bus_id is None:
        return ""
    raw = str(bus_id).strip().upper()
    if not raw:
        return ""

    # Keep dash/suffix patterns, but collapse leading zeros in the first number block.
    # Example: P00000001-7A -> P1-7A
    match = re.match(r'^([A-Z]+)(\d+)(.*)$', raw)
    if match:
        prefix, digits, suffix = match.groups()
        return f"{prefix}{digits.lstrip('0') or '0'}{suffix}"

    return raw

def infer_connections_from_posts():
    """
    Build line connections from explicit primary line topology.
    Uses DistributionLineSegment.from_bus_id/to_bus_id pairs instead of
    guessing adjacency from post ordering.
    """
    try:
        segments = DistributionLineSegment.query.all()
        if not segments:
            return 0

        connection_count = 0
        update_count = 0
        for seg in segments:
            from_bus = normalize_bus_id(seg.from_bus_id)
            to_bus = normalize_bus_id(seg.to_bus_id)
            if not from_bus or not to_bus:
                continue

            existing = LineConnection.query.filter_by(
                from_bus=from_bus,
                to_bus=to_bus,
                connection_type='Primary_to_Primary'
            ).first()

            if existing:
                changed = False
                if seg.phasing and existing.phasing != seg.phasing:
                    existing.phasing = seg.phasing
                    changed = True
                if changed:
                    update_count += 1
                continue

            conn = LineConnection(
                from_bus=from_bus,
                to_bus=to_bus,
                connection_type='Primary_to_Primary',
                phasing=seg.phasing
            )
            db.session.add(conn)
            connection_count += 1

        if connection_count > 0 or update_count > 0:
            db.session.commit()

        return connection_count
    except Exception as e:
        print(f"Error inferring connections: {e}")
        db.session.rollback()
        return 0
