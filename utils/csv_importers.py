
import csv
import io
import re
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from extensions import db
from models import Post, DistributionTransformer, SecondaryLineSegment, DistributionLineSegment, SecondaryServiceDrop, UploadHistory, VoltageRegulator, ShuntCapacitor, ShuntInductor, SeriesInductor, Customer, EnergyConsumption
from utils.import_helpers import find_column_value, sanitize_float

def normalize_header(header):
    """Normalize CSV header parsing."""
    if not header:
        return ""
    return re.sub(r'[^a-z0-9]+', '_', str(header).lower()).strip('_')

def import_posts_from_csv(csv_file):
    """
    Import Posts from CSV file (like EXAMPLEDATA.csv).
    Returns stats dict: {created, updated, skipped, errors}.
    """
    stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}
    
    try:
        # csv_file is a Werkzeug FileStorage object, has .filename
        filename = getattr(csv_file, 'filename', 'unknown_file.csv')
        stream = io.StringIO(csv_file.stream.read().decode("UTF8"), newline=None)
        reader = csv.DictReader(stream)
    except Exception as e:
        return {'error': f"Failed to read CSV: {str(e)}"}

    # Pre-fetch existing posts to minimize queries
    # Use normalized keys (stripped + lower) for comparison to avoid case/whitespace duplicates
    existing_posts = {str(p.pole_number).strip().lower(): p for p in Post.query.all()}
    
    row_idx = 1
    
    # Cache segment IDs to avoid querying inside the loop (which triggers autoflush)
    existing_segments = {str(s.segment_id).strip().lower(): s for s in DistributionLineSegment.query.all() if s.segment_id}
    
    for row in reader:
        row_idx += 1
        try:
            # Extract basic identifiers
            # Strategy: valid pole number or fallback to To_Bus_ID
            raw_id = find_column_value(row, ['Pole Number', 'pole_number', 'Pole#']) 
            if not raw_id:
                raw_id = find_column_value(row, ['To_Bus_ID', 'to_bus_id'])
            
            if not raw_id:
                stats['skipped'] += 1
                continue
                
            identifier_raw = str(raw_id).strip()
            if not identifier_raw:
                 stats['skipped'] += 1
                 continue
            
            # Check for existence using lowercased key
            identifier_key = identifier_raw.lower()

            lat = sanitize_float(find_column_value(row, ['latitude', 'lat']))
            lng = sanitize_float(find_column_value(row, ['longitude', 'lng', 'long']))

            # Preparing the Post object
            p = existing_posts.get(identifier_key)
            if not p:
                p = Post(pole_number=identifier_raw)
                db.session.add(p)
                existing_posts[identifier_key] = p # Add to local cache
                stats['created'] += 1
            else:
                stats['updated'] += 1

            # Update fields
            if lat is not None: p.lat = lat
            if lng is not None: p.lng = lng
            
            # Name default
            if not p.name: p.name = f"Pole {identifier_raw}"

            # Map other columns from EXAMPLEDATA.csv
            p.feeder = find_column_value(row, ['Feeder', 'Feeder Name'])
            p.phasing = find_column_value(row, ['Phasing'])
            p.configuration = find_column_value(row, ['Configuration'])
            p.system_grounding_type = find_column_value(row, ['System Grounding Type'])
            p.length_meters = sanitize_float(find_column_value(row, ['Length (meters)', 'Length']))
            p.conductor_type = find_column_value(row, ['Conductor Type'])
            p.pri_conductor_size = find_column_value(row, ['Conductor Size'])
            p.conductor_unit = find_column_value(row, ['Unit (C)'])
            p.conductor_strands = find_column_value(row, ['Strands (C)'])
            
            p.neutral_wire_type = find_column_value(row, ['Neutral Wire Type'])
            p.neutral_wire_size = find_column_value(row, ['Neutral Wire Size'])
            p.neutral_wire_unit = find_column_value(row, ['Unit (NW)'])
            p.neutral_wire_strands = find_column_value(row, ['Strands (NW)'])
            
            # Spacing
            p.spacing_d12 = sanitize_float(find_column_value(row, ['Spacing D12 (meters)']))
            p.spacing_d23 = sanitize_float(find_column_value(row, ['Spacing D23 (meters)']))
            p.spacing_d13 = sanitize_float(find_column_value(row, ['Spacing D13 (meters)']))
            p.spacing_d1n = sanitize_float(find_column_value(row, ['Spacing D1n (meters)']))
            p.spacing_d2n = sanitize_float(find_column_value(row, ['Spacing D2n (meters)']))
            p.spacing_d3n = sanitize_float(find_column_value(row, ['Spacing D3n (meters)']))
            p.spacing_dc1_c2 = sanitize_float(find_column_value(row, ['Spacing DC1-C2 (meters)']))
            
            # Heights
            p.height_h1 = sanitize_float(find_column_value(row, ['Height H1 (meters)']))
            p.height_h2 = sanitize_float(find_column_value(row, ['Height H2 (meters)']))
            p.height_h3 = sanitize_float(find_column_value(row, ['Height H3 (meters)']))
            p.height_hn = sanitize_float(find_column_value(row, ['Height Hn (meters)']))
            
            p.earth_resistivity = sanitize_float(find_column_value(row, ['Earth Resistivity (Ohm-meter)']))

            p.primary_bus_id = identifier_raw # Self-reference as valid bus

            # Also create DistributionLineSegment record for this row?
            segment_id_raw = find_column_value(row, ['Primary Distribution Line Segment ID'])
            if segment_id_raw:
                segment_id_clean = str(segment_id_raw).strip()
                segment_id_key = segment_id_clean.lower()
                
                from_bus = find_column_value(row, ['From_Bus_ID'])
                to_bus = find_column_value(row, ['To_Bus_ID'])
                if from_bus and to_bus:
                    # Upsert segment usage local cache to avoid query flushes
                    seg = existing_segments.get(segment_id_key)
                    if not seg:
                        seg = DistributionLineSegment(segment_id=segment_id_clean)
                        db.session.add(seg)
                        existing_segments[segment_id_key] = seg
                        stats['created'] += 1
                    
                    seg.from_bus_id = from_bus
                    seg.to_bus_id = to_bus
                    seg.phasing = p.phasing
                    seg.configuration = p.configuration
                    seg.system_grounding_type = p.system_grounding_type
                    seg.length_meters = p.length_meters
                    seg.conductor_type = p.conductor_type
                    seg.conductor_size = p.pri_conductor_size
                    seg.conductor_unit = p.conductor_unit
                    seg.conductor_strands = p.conductor_strands
                    seg.neutral_wire_type = p.neutral_wire_type
                    seg.neutral_wire_size = p.neutral_wire_size
                    seg.neutral_wire_unit = p.neutral_wire_unit
                    seg.neutral_wire_strands = p.neutral_wire_strands
                    seg.spacing_d12 = p.spacing_d12
                    seg.spacing_d23 = p.spacing_d23
                    seg.spacing_d13 = p.spacing_d13
                    seg.spacing_d1n = p.spacing_d1n
                    seg.spacing_d2n = p.spacing_d2n
                    seg.spacing_d3n = p.spacing_d3n
                    seg.spacing_dc1_c2 = p.spacing_dc1_c2
                    seg.height_h1 = p.height_h1
                    seg.height_h2 = p.height_h2
                    seg.height_h3 = p.height_h3
                    seg.height_hn = p.height_hn
                    seg.earth_resistivity = p.earth_resistivity
                    
        except Exception as e:
            stats['errors'].append(f"Row {row_idx}: {str(e)}")
            stats['skipped'] += 1

    try:
        db.session.commit()
        # Log history
        if stats['created'] > 0 or stats['updated'] > 0:
            h = UploadHistory(
                file_type='posts',
                filename=filename,
                record_count=stats['created'] + stats['updated']
            )
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

    for row_idx, row in enumerate(reader, start=2):
        try:
            tid = find_column_value(row, ['Distribution Transformer ID'])
            if not tid:
                stats['skipped'] += 1
                continue
            
            t = DistributionTransformer.query.filter_by(transformer_id=tid).first()
            if not t:
                t = DistributionTransformer(transformer_id=tid)
                db.session.add(t)
                stats['created'] += 1
            else:
                stats['updated'] += 1
            
            # Map fields
            t.from_primary_bus_id = find_column_value(row, ['From Primary Bus ID', 'From\nPrimary Bus ID'])
            t.to_secondary_bus_id = find_column_value(row, ['To Secondary Bus ID', 'To \nSecondary Bus ID'])
            t.primary_phasing = find_column_value(row, ['Primary Phasing'])
            t.secondary_phasing = find_column_value(row, ['Secondary Phasing'])
            t.installation_type = find_column_value(row, ['Installation Type'])
            t.kva_rating = sanitize_float(find_column_value(row, ['KVA Rating']))
            t.primary_voltage_kv = sanitize_float(find_column_value(row, ['Primary Voltage Rating(kV)']))
            t.secondary_voltage_kv = sanitize_float(find_column_value(row, ['Secondary Voltage Rating (kV)']))
            
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

    for row_idx, row in enumerate(reader, start=2):
        try:
            # Validating minimal fields
            from_bus = find_column_value(row, ['From Bus ID'])
            to_bus = find_column_value(row, ['To  Bus ID', 'To Bus ID'])
            
            if not from_bus or not to_bus:
                stats['skipped'] += 1
                continue
                
            # Identifier is usually "Secondary Distribution Line ID"
            seg_id = find_column_value(row, ['Secondary Distribution Line ID'])
            
            # Check existing
            sl = None
            if seg_id:
                sl = SecondaryLineSegment.query.filter_by(segment_id=seg_id).first()
            
            # Fallback check by bus connection if no ID or not found
            if not sl:
                sl = SecondaryLineSegment.query.filter_by(from_bus_id=from_bus, to_bus_id=to_bus).first()
            
            if not sl:
                sl = SecondaryLineSegment()
                db.session.add(sl)
                stats['created'] += 1
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

    for row_idx, row in enumerate(reader, start=2):
        try:
            # Map fields based on CSV header analysis
            service_drop_id = find_column_value(row, ['Secondary Customer Service Drop ID', 'Service Drop ID'])
            
            if not service_drop_id:
                stats['skipped'] += 1
                continue

            sd = SecondaryServiceDrop.query.filter_by(service_drop_id=service_drop_id).first()
            if not sd:
                sd = SecondaryServiceDrop(service_drop_id=service_drop_id)
                db.session.add(sd)
                stats['created'] += 1
            else:
                stats['updated'] += 1

            sd.from_bus_id = find_column_value(row, ['From Bus ID', 'From \nBus ID'])
            sd.to_customer_id = find_column_value(row, ['To Customer ID', 'To \nCustomer ID'])
            sd.phasing = find_column_value(row, ['Phasing'])
            sd.installation_type = find_column_value(row, ['Installation Type'])
            sd.length_meters_1 = sanitize_float(find_column_value(row, ['Length-1 (meters)', 'Length-1         (meters)']))
            sd.length_meters_2 = sanitize_float(find_column_value(row, ['Length-2 (meters)', 'Length-2         (meters)']))
            sd.conductor_type = find_column_value(row, ['Conductor Type'])
            sd.conductor_size = find_column_value(row, ['Conductor Size', 'Conductor\nSize'])
            sd.conductor_unit = find_column_value(row, ['Unit (C)'])

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
