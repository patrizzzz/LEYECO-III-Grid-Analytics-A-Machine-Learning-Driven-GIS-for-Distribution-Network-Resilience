
import csv
import io
import re
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from extensions import db
from models import Post, DistributionTransformer, SecondaryLineSegment, DistributionLineSegment, SecondaryServiceDrop, UploadHistory, VoltageRegulator, ShuntCapacitor, ShuntInductor, SeriesInductor, Customer, EnergyConsumption, BusNode, LineConnection
from utils.import_helpers import find_column_value, sanitize_float

def normalize_header(header):
    """Normalize CSV header parsing."""
    if not header:
        return ""
    return re.sub(r'[^a-z0-9]+', '_', str(header).lower()).strip('_')

def import_bus_nodes_from_csv(csv_file):
    """
    Step 2 Upload: Bus Data CSV.
    Each row = one electrical bus.
    Expected columns: Bus ID, Pole ID, Bus Description, Nominal Voltage (kV), Feeder
    
    Creates/updates:
    - BusNode records (the authoritative electrical node)
    - Links to existing Post records via Pole ID to inherit physical coordinates.
    """
    stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}

    try:
        filename = getattr(csv_file, 'filename', 'bus_data.csv')
        content = csv_file.stream.read()
        try:
            text = content.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = content.decode('cp1252', errors='replace')
        stream = io.StringIO(text, newline=None)
        reader = csv.DictReader(stream)
    except Exception as e:
        return {'error': f"Failed to read CSV: {str(e)}"}

    # Pre-load existing records to avoid per-row queries
    existing_nodes = {n.bus_id.strip().lower(): n for n in BusNode.query.all()}
    existing_posts = {str(p.pole_number).strip().lower(): p for p in Post.query.all()}

    row_idx = 1
    for row in reader:
        row_idx += 1
        try:
            bus_id_raw = find_column_value(row, ['Bus ID', 'bus_id', 'Bus_ID'])
            if not bus_id_raw:
                stats['skipped'] += 1
                continue

            bus_id = str(bus_id_raw).strip()
            bus_id_key = bus_id.lower()

            pole_id_raw = find_column_value(row, ['Pole ID', 'pole_id', 'Pole Number', 'pole_number', 'post_id', 'Post ID'])
            pole_id = str(pole_id_raw).strip() if pole_id_raw else None
            
            desc = find_column_value(row, ['Bus Description', 'bus_description', 'Description']) or ''
            volt = sanitize_float(find_column_value(row, ['Nominal Voltage (kV)', 'Nominal Voltage', 'nominal_voltage']))
            feeder = find_column_value(row, ['feeder', 'Feeder', 'Feeder Name']) or ''

            lat = None
            lng = None

            # Attempt to find the physical pole to inherit coordinates
            if pole_id:
                pole_id_key = pole_id.lower()
                post = existing_posts.get(pole_id_key)
                if post:
                    lat = post.lat
                    lng = post.lng
                else:
                    # Optional: warning that the physical pole doesn't exist yet
                    pass
            else:
                 # Fallback: maybe the CSV still has lag/lng columns directly for some reason
                 lat = sanitize_float(find_column_value(row, ['latitude', 'Latitude', 'lat']))
                 lng = sanitize_float(find_column_value(row, ['longitude', 'Longitude', 'lon', 'long']))

            # --- Upsert BusNode ---
            node = existing_nodes.get(bus_id_key)
            if not node:
                node = BusNode(bus_id=bus_id)
                db.session.add(node)
                existing_nodes[bus_id_key] = node
                stats['created'] += 1
            else:
                stats['updated'] += 1

            node.pole_number     = pole_id
            node.bus_description = desc
            node.bus_type        = desc  # desc IS the type label
            node.nominal_voltage = volt
            node.feeder          = feeder
            
            # Cache coordinates on the BusNode if we found them (either from Post or fallback)
            if lat is not None: node.lat = lat
            if lng is not None: node.lng = lng

        except Exception as e:
            stats['errors'].append(f"Row {row_idx}: {str(e)}")
            stats['skipped'] += 1

    try:
        db.session.commit()
        if stats['created'] > 0 or stats['updated'] > 0:
            h = UploadHistory(
                file_type='bus_nodes',
                filename=filename,
                record_count=stats['created'] + stats['updated']
            )
            db.session.add(h)
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        return {'error': f"Database commit failed: {str(e)}"}

    return stats


def import_primary_lines_from_csv(csv_file):
    """
    Import Primary Distribution Line Segments from CSV file (like EXAMPLEDATA.csv).
    Returns stats dict: {created, updated, skipped, errors}.
    """
    stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}

    try:
        filename = getattr(csv_file, 'filename', 'primary_lines.csv')
        # Ensure we can read multiple times if needed by resetting stream if possible
        if hasattr(csv_file, 'stream'):
            csv_file.stream.seek(0)
            content = csv_file.stream.read()
        else:
            csv_file.seek(0)
            content = csv_file.read()

        try:
            text = content.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = content.decode('cp1252', errors='replace')

        stream = io.StringIO(text, newline=None)
        reader = csv.DictReader(stream)
    except Exception as e:
        return {'error': f"Failed to read CSV: {str(e)}"}

    # Cache existing segments and connections with normalized keys
    existing_segments = {str(s.segment_id).strip().upper(): s for s in DistributionLineSegment.query.all() if s.segment_id}
    existing_connections = {
        (c.from_bus.strip().upper(), c.to_bus.strip().upper(), c.connection_type): c 
        for c in LineConnection.query.filter_by(connection_type='Primary_to_Primary').all()
    }

    row_idx = 1
    for row in reader:
        row_idx += 1
        try:
            segment_id_raw = find_column_value(row, ['Primary Distribution Line Segment ID', 'segment_id'])
            from_bus = find_column_value(row, ['From_Bus_ID'])
            to_bus = find_column_value(row, ['To_Bus_ID'])

            if not segment_id_raw or not from_bus or not to_bus:
                stats['skipped'] += 1
                continue

            segment_id_clean = str(segment_id_raw).strip().upper()
            from_bus = from_bus.strip().upper()
            to_bus = to_bus.strip().upper()
            segment_id_key = segment_id_clean

            # Shared logic for attribute extraction
            phasing_val = find_column_value(row, ['Phasing'])
            configuration_val = find_column_value(row, ['Configuration'])
            system_grounding_type_val = find_column_value(row, ['System Grounding Type'])
            length_meters_val = sanitize_float(find_column_value(row, ['Length (meters)', 'Length']))
            conductor_type_val = find_column_value(row, ['Conductor Type'])
            pri_conductor_size_val = find_column_value(row, ['Conductor Size'])
            conductor_unit_val = find_column_value(row, ['Unit (C)'])
            conductor_strands_val = find_column_value(row, ['Strands (C)'])
            neutral_wire_type_val = find_column_value(row, ['Neutral Wire Type'])
            neutral_wire_size_val = find_column_value(row, ['Neutral Wire Size'])
            neutral_wire_unit_val = find_column_value(row, ['Unit (NW)'])
            neutral_wire_strands_val = find_column_value(row, ['Strands (NW)'])
            spacing_d12 = sanitize_float(find_column_value(row, ['Spacing D12 (meters)']))
            spacing_d23 = sanitize_float(find_column_value(row, ['Spacing D23 (meters)']))
            spacing_d13 = sanitize_float(find_column_value(row, ['Spacing D13 (meters)']))
            spacing_d1n = sanitize_float(find_column_value(row, ['Spacing D1n (meters)']))
            spacing_d2n = sanitize_float(find_column_value(row, ['Spacing D2n (meters)']))
            spacing_d3n = sanitize_float(find_column_value(row, ['Spacing D3n (meters)']))
            spacing_dc1_c2 = sanitize_float(find_column_value(row, ['Spacing DC1-C2 (meters)']))
            height_h1 = sanitize_float(find_column_value(row, ['Height H1 (meters)']))
            height_h2 = sanitize_float(find_column_value(row, ['Height H2 (meters)']))
            height_h3 = sanitize_float(find_column_value(row, ['Height H3 (meters)']))
            height_hn = sanitize_float(find_column_value(row, ['Height Hn (meters)']))
            earth_res = sanitize_float(find_column_value(row, ['Earth Resistivity (Ohm-meter)']))

            seg = existing_segments.get(segment_id_key)
            if seg:
                # If buses match, we update. If not, we skip duplicate ID to preserve existing line.
                if seg.from_bus_id != from_bus or seg.to_bus_id != to_bus:
                    stats['skipped'] += 1
                    stats['errors'].append(f"Row {row_idx}: Duplicate ID '{segment_id_clean}' with different connectivity. Skipping.")
                    continue
                stats['updated'] += 1
            else:
                seg = DistributionLineSegment(segment_id=segment_id_clean)
                db.session.add(seg)
                existing_segments[segment_id_key] = seg
                stats['created'] += 1

            seg.from_bus_id = from_bus
            seg.to_bus_id = to_bus
            seg.phasing = phasing_val
            seg.configuration = configuration_val
            seg.system_grounding_type = system_grounding_type_val
            seg.length_meters = length_meters_val
            seg.conductor_type = conductor_type_val
            seg.conductor_size = pri_conductor_size_val
            seg.conductor_unit = conductor_unit_val
            seg.conductor_strands = conductor_strands_val
            seg.neutral_wire_type = neutral_wire_type_val
            seg.neutral_wire_size = neutral_wire_size_val
            seg.neutral_wire_unit = neutral_wire_unit_val
            seg.neutral_wire_strands = neutral_wire_strands_val
            seg.spacing_d12 = spacing_d12
            seg.spacing_d23 = spacing_d23
            seg.spacing_d13 = spacing_d13
            seg.spacing_d1n = spacing_d1n
            seg.spacing_d2n = spacing_d2n
            seg.spacing_d3n = spacing_d3n
            seg.spacing_dc1_c2 = spacing_dc1_c2
            seg.height_h1 = height_h1
            seg.height_h2 = height_h2
            seg.height_h3 = height_h3
            seg.height_hn = height_hn
            seg.earth_resistivity = earth_res

            # --- Sync Topology to LineConnection ---
            conn_key = (from_bus, to_bus, 'Primary_to_Primary')
            if conn_key not in existing_connections:
                conn = LineConnection(
                    from_bus=from_bus,
                    to_bus=to_bus,
                    connection_type='Primary_to_Primary',
                    phasing=phasing_val
                )
                db.session.add(conn)
                existing_connections[conn_key] = conn

        except Exception as e:
            stats['errors'].append(f"Row {row_idx}: {str(e)}")
            stats['skipped'] += 1

    try:
        db.session.commit()
        if stats['created'] > 0 or stats['updated'] > 0:
            h = UploadHistory(file_type='primary_lines', filename=filename, record_count=stats['created'] + stats['updated'])
            db.session.add(h)
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        return {'error': f"Database commit failed: {str(e)}"}

    return stats


def import_posts_from_csv(csv_file):
    """
    Import Posts from CSV file (Step 1 poles or Step 3 data providing pole updates).
    Returns stats dict: {created, updated, skipped, errors}.
    """
    stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}

    try:
        filename = getattr(csv_file, 'filename', 'poles.csv')
        if hasattr(csv_file, 'stream'):
            csv_file.stream.seek(0)
            content = csv_file.stream.read()
        else:
            csv_file.seek(0)
            content = csv_file.read()

        try:
            text = content.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = content.decode('cp1252', errors='replace')
        stream = io.StringIO(text, newline=None)
        reader = csv.DictReader(stream)
    except Exception as e:
        return {'error': f"Failed to read CSV: {str(e)}"}

    existing_posts = {str(p.pole_number).strip().lower(): p for p in Post.query.all()}
    row_idx = 1

    for row in reader:
        row_idx += 1
        try:
            raw_id = find_column_value(row, ['Pole Number', 'pole_number', 'Pole#', 'post_id', 'Post ID'])
            if not raw_id:
                # Step 3 files use To_Bus_ID for location updates
                raw_id = find_column_value(row, ['To_Bus_ID', 'to_bus_id'])

            if not raw_id:
                stats['skipped'] += 1
                continue

            identifier_raw = str(raw_id).strip()
            identifier_key = identifier_raw.lower()

            lat = sanitize_float(find_column_value(row, ['latitude', 'lat']))
            lng = sanitize_float(find_column_value(row, ['longitude', 'lng', 'long']))

            p = existing_posts.get(identifier_key)
            if p:
                if lat is not None: p.lat = lat
                if lng is not None: p.lng = lng
                p.primary_bus_id = identifier_raw
                # Update optional descriptive fields if present
                feeder = find_column_value(row, ['Feeder', 'Feeder Name'])
                if feeder: p.feeder = feeder
                phasing = find_column_value(row, ['Phasing'])
                if phasing: p.phasing = phasing
                stats['updated'] += 1
            elif lat is not None and lng is not None:
                p = Post(pole_number=identifier_raw, lat=lat, lng=lng, name=f"Pole {identifier_raw}", primary_bus_id=identifier_raw)
                db.session.add(p)
                existing_posts[identifier_key] = p
                stats['created'] += 1
            else:
                stats['skipped'] += 1

        except Exception as e:
            stats['errors'].append(f"Row {row_idx}: {str(e)}")
            stats['skipped'] += 1

    try:
        db.session.commit()
        if stats['created'] > 0 or stats['updated'] > 0:
            h = UploadHistory(file_type='posts', filename=filename, record_count=stats['created'] + stats['updated'])
            db.session.add(h)
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        return {'error': f"Database commit failed: {str(e)}"}

    return stats




def import_transformers_from_csv(csv_file):
    """
    Import Distribution Transformers from CSV (example2.csv).
    """
    stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}
    
    try:
        filename = getattr(csv_file, 'filename', 'unknown_file.csv')
        stream = io.StringIO(csv_file.stream.read().decode("UTF8"), newline=None)
        reader = csv.DictReader(stream)
    except Exception as e:
        return {'error': f"Failed to read CSV: {str(e)}"}

    # Pre-fetch existing transformers and connections with normalized keys
    existing_transformers = {t.transformer_id.strip().upper(): t for t in DistributionTransformer.query.all()}
    existing_connections = {
        (c.from_bus.strip().upper(), c.to_bus.strip().upper(), c.connection_type): c 
        for c in LineConnection.query.filter_by(connection_type='Primary_to_Transformer').all()
    }

    for row_idx, row in enumerate(reader, start=2):
        try:
            tid_raw = find_column_value(row, ['Distribution Transformer ID'])
            if not tid_raw:
                stats['skipped'] += 1
                continue
            
            tid = tid_raw.strip().upper()
            t = existing_transformers.get(tid)
            if not t:
                t = DistributionTransformer(transformer_id=tid)
                db.session.add(t)
                existing_transformers[tid] = t
                stats['created'] += 1
            else:
                stats['updated'] += 1
            
            # Map fields with normalization
            from_bus = find_column_value(row, ['From Primary Bus ID', 'From\nPrimary Bus ID'])
            if from_bus: from_bus = from_bus.strip().upper()
            to_bus = find_column_value(row, ['To Secondary Bus ID', 'To \nSecondary Bus ID'])
            if to_bus: to_bus = to_bus.strip().upper()

            t.from_primary_bus_id = from_bus
            t.to_secondary_bus_id = to_bus
            t.primary_phasing = find_column_value(row, ['Primary Phasing'])
            t.secondary_phasing = find_column_value(row, ['Secondary Phasing'])
            t.installation_type = find_column_value(row, ['Installation Type'])
            t.no_dts_in_bank = sanitize_float(find_column_value(row, ['No. DTs in Bank']))
            t.connection = find_column_value(row, ['Connection'])
            t.kva_rating = sanitize_float(find_column_value(row, ['KVA Rating']))
            t.primary_voltage_kv = sanitize_float(find_column_value(row, ['Primary Voltage Rating(kV)']))
            t.secondary_voltage_kv = sanitize_float(find_column_value(row, ['Secondary Voltage Rating (kV)']))
            t.primary_tap_kv = sanitize_float(find_column_value(row, ['Primary Tap Voltage (kV)']))
            t.secondary_tap_kv = sanitize_float(find_column_value(row, ['Secondary Tap Voltage (kV)']))
            t.pct_z = sanitize_float(find_column_value(row, ['%Z']))
            t.xr_ratio = sanitize_float(find_column_value(row, ['X/R Ratio']))
            t.no_load_loss_kw = sanitize_float(find_column_value(row, ['No-Load Loss (kW)']))
            t.exciting_current_pct = sanitize_float(find_column_value(row, ['Exciting Current (%)']))
            
            # --- Sync Topology to LineConnection ---
            if t.from_primary_bus_id and t.to_secondary_bus_id:
                # Check for existing using pre-fetched cache with normalized labels
                conn_key = (t.from_primary_bus_id, t.to_secondary_bus_id, 'Primary_to_Transformer')
                if conn_key not in existing_connections:
                    conn = LineConnection(
                        from_bus=t.from_primary_bus_id,
                        to_bus=t.to_secondary_bus_id,
                        connection_type='Primary_to_Transformer',
                        phasing=t.primary_phasing
                    )
                    db.session.add(conn)
                    existing_connections[conn_key] = conn

            # --- Sync to Post Table for Map Visualization ---
            if t.from_primary_bus_id:
                # We reuse existing_posts from previous imports if possible, but here we'll pull fresh or use a local cache
                # For simplicity and to avoid pre-loading 10k poles, we'll do a quick lookup
                p = Post.query.filter((Post.pole_number == t.from_primary_bus_id) | (Post.primary_bus_id == t.from_primary_bus_id)).first()
                if p:
                    p.kva_rating = t.kva_rating
                    p.transformer_bus_id = t.from_primary_bus_id
            
        except Exception as e:
            stats['errors'].append(f"Row {row_idx}: {str(e)}")
            stats['skipped'] += 1

    try:
        db.session.commit()
        if stats['created'] > 0 or stats['updated'] > 0:
            h = UploadHistory(
                file_type='transformers',
                filename=filename,
                record_count=stats['created'] + stats['updated']
            )
            db.session.add(h)
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        return {'error': f"Database commit failed: {str(e)}"}

    return stats

def import_secondary_lines_from_csv(csv_file):
    """
    Import Secondary Line Segments from CSV (exampleSL.csv).
    """
    stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}
    
    try:
        filename = getattr(csv_file, 'filename', 'unknown_file.csv')
        stream = io.StringIO(csv_file.stream.read().decode("UTF8"), newline=None)
        reader = csv.DictReader(stream)
    except Exception as e:
        return {'error': f"Failed to read CSV: {str(e)}"}

    # Pre-fetch for optimization and robustness
    existing_segments = {s.segment_id.strip().upper(): s for s in SecondaryLineSegment.query.filter(SecondaryLineSegment.segment_id != None).all()}
    existing_connections = {
        (c.from_bus.strip().upper(), c.to_bus.strip().upper(), c.connection_type): c 
        for c in LineConnection.query.filter_by(connection_type='Secondary_to_Secondary').all()
    }

    for row_idx, row in enumerate(reader, start=2):
        try:
            # Validating minimal fields
            from_bus = find_column_value(row, ['From Bus ID'])
            to_bus = find_column_value(row, ['To  Bus ID', 'To Bus ID'])
            
            if not from_bus or not to_bus:
                stats['skipped'] += 1
                continue
            
            from_bus = from_bus.strip().upper()
            to_bus = to_bus.strip().upper()
                
            # Identifier is usually "Secondary Distribution Line ID"
            seg_id_raw = find_column_value(row, ['Secondary Distribution Line ID'])
            seg_id = seg_id_raw.strip().upper() if seg_id_raw else None
            
            # Check existing from cache
            sl = None
            if seg_id:
                sl = existing_segments.get(seg_id)
            
            if not sl:
                # Fallback check by bus connection (already normalized)
                sl = SecondaryLineSegment.query.filter_by(from_bus_id=from_bus, to_bus_id=to_bus).first()
            
            if not sl:
                sl = SecondaryLineSegment()
                db.session.add(sl)
                stats['created'] += 1
                if seg_id: existing_segments[seg_id] = sl
            else:
                stats['updated'] += 1
            
            sl.segment_id = seg_id
            sl.from_bus_id = from_bus
            sl.to_bus_id = to_bus
            sl.phasing = find_column_value(row, ['Phasing'])
            sl.installation_type = find_column_value(row, ['Installation Type'])
            sl.length_meters = sanitize_float(find_column_value(row, ['Length         (meters)', 'Length (meters)']))
            sl.conductor_type = find_column_value(row, ['Conductor Type'])
            sl.conductor_size = find_column_value(row, ['Conductor Size'])
            sl.conductor_unit = find_column_value(row, ['Unit (C)'])
            sl.feeder = find_column_value(row, ['Feeder', 'Feeder Name'])
            sl.circuit = find_column_value(row, ['Circuit', 'Circuit Name'])
            
            # --- Sync Topology to LineConnection ---
            if sl.from_bus_id and sl.to_bus_id:
                conn_key = (sl.from_bus_id, sl.to_bus_id, 'Secondary_to_Secondary')
                if conn_key not in existing_connections:
                    conn = LineConnection(
                        from_bus=sl.from_bus_id,
                        to_bus=sl.to_bus_id,
                        connection_type='Secondary_to_Secondary',
                        feeder=sl.feeder,
                        circuit=sl.circuit
                    )
                    db.session.add(conn)
                    existing_connections[conn_key] = conn
            
        except Exception as e:
            stats['errors'].append(f"Row {row_idx}: {str(e)}")
            stats['skipped'] += 1

    try:
        db.session.commit()
        if stats['created'] > 0 or stats['updated'] > 0:
            h = UploadHistory(
                file_type='secondary_lines',
                filename=filename,
                record_count=stats['created'] + stats['updated']
            )
            db.session.add(h)
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        return {'error': f"Database commit failed: {str(e)}"}

    return stats

def import_service_drops_from_csv(csv_file):
    """
    Import Secondary Service Drops from CSV (exampleSLD.csv).
    """
    stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}

    try:
        filename = getattr(csv_file, 'filename', 'unknown_file.csv')
        stream = io.StringIO(csv_file.stream.read().decode("UTF8"), newline=None)
        reader = csv.DictReader(stream)
    except Exception as e:
        return {'error': f"Failed to read CSV: {str(e)}"}

    from models import SecondaryServiceDrop # Local import to avoid circular dep if any

    # Pre-fetch for optimization with normalized keys
    existing_drops = {d.service_drop_id.strip().upper(): d for d in SecondaryServiceDrop.query.all()}
    existing_connections = {
        (c.from_bus.strip().upper(), c.to_bus.strip().upper(), c.connection_type): c 
        for c in LineConnection.query.filter_by(connection_type='Secondary_to_Customer').all()
    }

    for row_idx, row in enumerate(reader, start=2):
        try:
            # Map fields based on CSV header analysis with normalization
            service_drop_id_raw = find_column_value(row, ['Secondary Customer Service Drop ID', 'Service Drop ID'])
            if not service_drop_id_raw:
                stats['skipped'] += 1
                continue
            
            service_drop_id = service_drop_id_raw.strip().upper()

            sd = existing_drops.get(service_drop_id)
            if not sd:
                sd = SecondaryServiceDrop(service_drop_id=service_drop_id)
                db.session.add(sd)
                existing_drops[service_drop_id] = sd
                stats['created'] += 1
            else:
                stats['updated'] += 1

            from_bus = find_column_value(row, ['From Bus ID', 'From \nBus ID'])
            if from_bus: from_bus = from_bus.strip().upper()
            to_cust = find_column_value(row, ['To Customer ID', 'To \nCustomer ID'])
            if to_cust: to_cust = to_cust.strip().upper()

            sd.from_bus_id = from_bus
            sd.to_customer_id = to_cust
            sd.phasing = find_column_value(row, ['Phasing'])
            sd.installation_type = find_column_value(row, ['Installation Type'])
            sd.length_meters_1 = sanitize_float(find_column_value(row, ['Length-1 (meters)', 'Length-1         (meters)']))
            sd.length_meters_2 = sanitize_float(find_column_value(row, ['Length-2 (meters)', 'Length-2         (meters)']))
            sd.conductor_type = find_column_value(row, ['Conductor Type'])
            sd.conductor_size = find_column_value(row, ['Conductor Size', 'Conductor\nSize'])
            sd.conductor_unit = find_column_value(row, ['Unit (C)'])

            # --- Sync Topology to LineConnection ---
            if sd.from_bus_id and sd.to_customer_id:
                conn_key = (sd.from_bus_id, sd.to_customer_id, 'Secondary_to_Customer')
                if conn_key not in existing_connections:
                    conn = LineConnection(
                        from_bus=sd.from_bus_id,
                        to_bus=sd.to_customer_id,
                        connection_type='Secondary_to_Customer',
                        phasing=sd.phasing
                    )
                    db.session.add(conn)
                    existing_connections[conn_key] = conn

        except Exception as e:
            stats['errors'].append(f"Row {row_idx}: {str(e)}")
            stats['skipped'] += 1

    try:
        db.session.commit()
        if stats['created'] > 0 or stats['updated'] > 0:
            h = UploadHistory(
                file_type='service_drops',
                filename=filename,
                record_count=stats['created'] + stats['updated']
            )
            db.session.add(h)
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        return {'error': f"Database commit failed: {str(e)}"}

    return stats

def import_voltage_regulators_from_csv(csv_file):
    stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}
    try:
        filename = getattr(csv_file, 'filename', 'voltage_regulators.csv')
        content = csv_file.stream.read().decode("UTF8")
        
        # handle multi-line headers by merging first 3 lines
        lines = content.splitlines()
        if len(lines) >= 3:
            # concatenate first 3 lines, removing quotes
            header_line = (lines[0] + lines[1] + lines[2]).replace('"', '')
            # rejoin with data rows
            fixed_content = header_line + '\n' + '\n'.join(lines[3:])
            stream = io.StringIO(fixed_content, newline=None)
        else:
            stream = io.StringIO(content, newline=None)
            
        reader = csv.DictReader(stream)
    except Exception as e:
        return {'error': f"Failed to read CSV: {str(e)}"}

    row_idx = 1
    existing = {r.regulator_id: r for r in VoltageRegulator.query.all()}

    for row in reader:
        row_idx += 1
        try:
            reg_id = find_column_value(row, ['Voltage Regulator ID'])
            if not reg_id:
                stats['skipped'] += 1
                continue
            
            p = existing.get(reg_id)
            if not p:
                p = VoltageRegulator(regulator_id=reg_id)
                db.session.add(p)
                stats['created'] += 1
            else:
                stats['updated'] += 1

            p.from_bus_id = find_column_value(row, ['From Bus ID', 'From\nBus ID'])
            p.to_bus_id = find_column_value(row, ['To Bus ID', 'To\nBus ID'])
            p.regulated_bus_id = find_column_value(row, ['Regulated Bus ID'])
            p.phase_type = find_column_value(row, ['Phase Type'])
            p.phasing = find_column_value(row, ['Phasing'])
            p.phase_sense = find_column_value(row, ['Phase Sense'])
            
            p.kva_rating = sanitize_float(find_column_value(row, ['KVA Rating']))
            p.kv_rating = sanitize_float(find_column_value(row, ['KV Rating']))
            p.target_voltage = sanitize_float(find_column_value(row, ['Target Voltage', 'Target Voltage (120V base)']))
            p.bandwidth = sanitize_float(find_column_value(row, ['Bandwidth', 'Bandwidth (120V base)']))
            
            p.r_setting_a = sanitize_float(find_column_value(row, ['R-Setting Phase A']))
            p.r_setting_b = sanitize_float(find_column_value(row, ['R-Setting Phase B']))
            p.r_setting_c = sanitize_float(find_column_value(row, ['R-Setting Phase C']))
            
            p.x_setting_a = sanitize_float(find_column_value(row, ['X-Setting Phase A']))
            p.x_setting_b = sanitize_float(find_column_value(row, ['X-Setting Phase B']))
            p.x_setting_c = sanitize_float(find_column_value(row, ['X-Setting Phase C']))
            
            p.primary_current_rating = sanitize_float(find_column_value(row, ['Primary Current Rating (A)']))
            p.pt_ratio = sanitize_float(find_column_value(row, ['PT Ratio']))
            p.no_load_loss_kw = sanitize_float(find_column_value(row, ['No-Load Loss (kW)']))
            p.exciting_current_pct = sanitize_float(find_column_value(row, ['Exciting Current (%)']))

        except Exception as e:
            stats['errors'].append(f"Row {row_idx}: {str(e)}")
            stats['skipped'] += 1

    try:
        db.session.commit()
        if stats['created'] > 0 or stats['updated'] > 0:
            h = UploadHistory(file_type='voltage_regulators', filename=filename, record_count=stats['created'] + stats['updated'])
            db.session.add(h)
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        return {'error': f"Database commit failed: {str(e)}"}
    return stats

def import_shunt_capacitors_from_csv(csv_file):
    stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}
    try:
        filename = getattr(csv_file, 'filename', 'shunt_capacitors.csv')
        stream = io.StringIO(csv_file.stream.read().decode("UTF8"), newline=None)
        reader = csv.DictReader(stream)
    except Exception as e:
        return {'error': f"Failed to read CSV: {str(e)}"}

    row_idx = 1
    existing = {r.capacitor_id: r for r in ShuntCapacitor.query.all()}

    for row in reader:
        row_idx += 1
        try:
            cap_id = find_column_value(row, ['Shunt Capacitor ID'])
            if not cap_id:
                stats['skipped'] += 1
                continue
            
            p = existing.get(cap_id)
            if not p:
                p = ShuntCapacitor(capacitor_id=cap_id)
                db.session.add(p)
                stats['created'] += 1
            else:
                stats['updated'] += 1

            p.bus_connected_id = find_column_value(row, ['From Bus ID', 'From\nBus ID', 'Bus Connected (Bus ID)', 'Bus Connected\n(Bus ID)'])
            p.phase_type = find_column_value(row, ['Phase Type'])
            p.phasing = find_column_value(row, ['Phasing'])
            p.voltage_rating_kv = sanitize_float(find_column_value(row, ['Voltage Rating (kV)']))

            p.kvar_rating_a = sanitize_float(find_column_value(row, ['KVAR Rating Phase A']))
            p.kvar_rating_b = sanitize_float(find_column_value(row, ['KVAR Rating Phase B']))
            p.kvar_rating_c = sanitize_float(find_column_value(row, ['KVAR Rating Phase C']))
            p.power_loss_watts = sanitize_float(find_column_value(row, ['Power Loss (Watts)']))

        except Exception as e:
            stats['errors'].append(f"Row {row_idx}: {str(e)}")
            stats['skipped'] += 1

    try:
        db.session.commit()
        if stats['created'] > 0 or stats['updated'] > 0:
            h = UploadHistory(file_type='shunt_capacitors', filename=filename, record_count=stats['created'] + stats['updated'])
            db.session.add(h)
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        return {'error': f"Database commit failed: {str(e)}"}
    return stats

def import_shunt_inductors_from_csv(csv_file):
    stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}
    try:
        filename = getattr(csv_file, 'filename', 'shunt_inductors.csv')
        stream = io.StringIO(csv_file.stream.read().decode("UTF8"), newline=None)
        reader = csv.DictReader(stream)
    except Exception as e:
        return {'error': f"Failed to read CSV: {str(e)}"}

    row_idx = 1
    existing = {r.inductor_id: r for r in ShuntInductor.query.all()}

    for row in reader:
        row_idx += 1
        try:
            ind_id = find_column_value(row, ['Shunt Inductor ID'])
            if not ind_id:
                stats['skipped'] += 1
                continue
            
            p = existing.get(ind_id)
            if not p:
                p = ShuntInductor(inductor_id=ind_id)
                db.session.add(p)
                stats['created'] += 1
            else:
                stats['updated'] += 1

            p.bus_connected_id = find_column_value(row, ['From Bus ID', 'From\nBus ID', 'Bus Connected (Bus ID)', 'Bus Connected\n(Bus ID)'])
            p.phase_type = find_column_value(row, ['Phase Type'])
            p.phasing = find_column_value(row, ['Phasing'])
            p.voltage_rating_kv = sanitize_float(find_column_value(row, ['Voltage Rating (kV)']))

            p.resistance_a = sanitize_float(find_column_value(row, ['Resistance Phase A (Ohms)']))
            p.resistance_b = sanitize_float(find_column_value(row, ['Resistance Phase B (Ohms)']))
            p.resistance_c = sanitize_float(find_column_value(row, ['Resistance Phase C (Ohms)']))
            
            p.reactance_a = sanitize_float(find_column_value(row, ['Reactance Phase A (Ohms)', 'Reactance\nPhase A (Ohms)']))
            p.reactance_b = sanitize_float(find_column_value(row, ['Reactance Phase B (Ohms)', 'Reactance\nPhase B (Ohms)']))
            p.reactance_c = sanitize_float(find_column_value(row, ['Reactance Phase C (Ohms)', 'Reactance\nPhase C (Ohms)']))

        except Exception as e:
            stats['errors'].append(f"Row {row_idx}: {str(e)}")
            stats['skipped'] += 1

    try:
        db.session.commit()
        if stats['created'] > 0 or stats['updated'] > 0:
            h = UploadHistory(file_type='shunt_inductors', filename=filename, record_count=stats['created'] + stats['updated'])
            db.session.add(h)
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        return {'error': f"Database commit failed: {str(e)}"}
    return stats

def import_series_inductors_from_csv(csv_file):
    stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}
    try:
        filename = getattr(csv_file, 'filename', 'series_inductors.csv')
        stream = io.StringIO(csv_file.stream.read().decode("UTF8"), newline=None)
        reader = csv.DictReader(stream)
    except Exception as e:
        return {'error': f"Failed to read CSV: {str(e)}"}

    row_idx = 1
    existing = {r.inductor_id: r for r in SeriesInductor.query.all()}

    for row in reader:
        row_idx += 1
        try:
            ind_id = find_column_value(row, ['Series Inductor ID'])
            if not ind_id:
                stats['skipped'] += 1
                continue
            
            p = existing.get(ind_id)
            if not p:
                p = SeriesInductor(inductor_id=ind_id)
                db.session.add(p)
                stats['created'] += 1
            else:
                stats['updated'] += 1

            p.from_bus_id = find_column_value(row, ['From Bus ID', 'From\nBus ID'])
            p.to_bus_id = find_column_value(row, ['To Bus ID', 'To \nBus ID', 'To\nBus ID'])
            p.phase_type = find_column_value(row, ['Phase Type'])
            p.phasing = find_column_value(row, ['Phasing'])
            p.voltage_rating_kv = sanitize_float(find_column_value(row, ['Voltage Rating (kV)']))

            p.resistance_a = sanitize_float(find_column_value(row, ['Resistance Phase A (Ohms)']))
            p.resistance_b = sanitize_float(find_column_value(row, ['Resistance Phase B (Ohms)']))
            p.resistance_c = sanitize_float(find_column_value(row, ['Resistance Phase C (Ohms)']))
            
            p.reactance_a = sanitize_float(find_column_value(row, ['Reactance Phase A (Ohms)']))
            p.reactance_b = sanitize_float(find_column_value(row, ['Reactance Phase B (Ohms)']))
            p.reactance_c = sanitize_float(find_column_value(row, ['Reactance Phase C (Ohms)']))

        except Exception as e:
            stats['errors'].append(f"Row {row_idx}: {str(e)}")
            stats['skipped'] += 1

    try:
        db.session.commit()
        if stats['created'] > 0 or stats['updated'] > 0:
            h = UploadHistory(file_type='series_inductors', filename=filename, record_count=stats['created'] + stats['updated'])
            db.session.add(h)
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        return {'error': f"Database commit failed: {str(e)}"}
    return stats

def import_customers_from_csv(csv_file):
    stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}
    try:
        filename = getattr(csv_file, 'filename', 'customers.csv')
        content = csv_file.stream.read()
        try:
            text = content.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = content.decode('cp1252', errors='replace')
            
        stream = io.StringIO(text, newline=None)
        reader = csv.DictReader(stream)
    except Exception as e:
        return {'error': f"Failed to read CSV: {str(e)}"}

    row_idx = 1
    existing = {r.customer_id: r for r in Customer.query.all()}

    for row in reader:
        row_idx += 1
        try:
            c_id = find_column_value(row, ['Customer ID', 'Customer Identifier', 'Account Number'])
            if not c_id:
                stats['skipped'] += 1
                continue
            
            p = existing.get(c_id)
            if not p:
                p = Customer(customer_id=c_id)
                db.session.add(p)
                stats['created'] += 1
            else:
                stats['updated'] += 1

            p.name = find_column_value(row, ['Customer Name', 'Name'])
            p.customer_type = find_column_value(row, ['Customer Type', 'Type'])
            p.service_voltage = find_column_value(row, ['Service Voltage'])
            p.phase = find_column_value(row, ['Phase'])

        except Exception as e:
            stats['errors'].append(f"Row {row_idx}: {str(e)}")
            stats['skipped'] += 1

    try:
        db.session.commit()
        if stats['created'] > 0 or stats['updated'] > 0:
            h = UploadHistory(file_type='customers', filename=filename, record_count=stats['created'] + stats['updated'])
            db.session.add(h)
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        return {'error': f"Database commit failed: {str(e)}"}
    return stats

def import_energy_consumption_from_csv(csv_file):
    stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}
    try:
        filename = getattr(csv_file, 'filename', 'energy_consumption.csv')
        content = csv_file.stream.read()
        try:
            text = content.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = content.decode('cp1252', errors='replace')
        stream = io.StringIO(text, newline=None)
        reader = csv.DictReader(stream)
    except Exception as e:
        return {'error': f"Failed to read CSV: {str(e)}"}

    row_idx = 1
    
    for row in reader:
        row_idx += 1
        try:
            c_id = find_column_value(row, ['Customer ID', 'Account Number'])
            b_period = find_column_value(row, ['Billing Period Code', 'Billing Period'])
            
            if not c_id: # Billing period might be missing?
                stats['skipped'] += 1
                continue
            
            # Simple check or just add. 
            # We'll check if (customer_id, billing_period) exists to update.
            # If billing period is missing, we might assume it's just 'Current'? 
            # But the user said "Billing Period Code" is a column.
            
            query = EnergyConsumption.query.filter_by(customer_id=c_id)
            if b_period:
                query = query.filter_by(billing_period=b_period)
            
            rec = query.first()

            if not rec:
                rec = EnergyConsumption(customer_id=c_id, billing_period=b_period)
                db.session.add(rec)
                stats['created'] += 1
            else:
                stats['updated'] += 1
            
            rec.kwh_consumed = sanitize_float(find_column_value(row, ['Energy Consumed (kWHr)', 'Energy Consumed', 'kWHr']))
            rec.power_factor = sanitize_float(find_column_value(row, ['Power Factor']))

        except Exception as e:
            stats['errors'].append(f"Row {row_idx}: {str(e)}")
            stats['skipped'] += 1

    try:
        db.session.commit()
        if stats['created'] > 0 or stats['updated'] > 0:
            h = UploadHistory(file_type='energy_consumption', filename=filename, record_count=stats['created'] + stats['updated'])
            db.session.add(h)
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        return {'error': f"Database commit failed: {str(e)}"}
    return stats
