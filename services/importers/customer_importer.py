from services.importers.base_importer import BaseImporter, sanitize_float
from models import Customer, EnergyConsumption, Meter, LoadCurve
from extensions import db
from sqlalchemy.dialects.postgresql import insert  # If using postgres, or generic bulk

class CustomerImporter(BaseImporter):
    file_type = 'customers'
    header_mappings = {
        'customer_id': ['Customer ID', 'customer_id'],
        'name': ['Customer Name', 'name'],
        'type': ['Customer Type', 'type'],
        'voltage': ['Service Voltage', 'voltage']
    }
    
    def process_rows(self, reader):
        existing_customers = {c.customer_id.strip().lower(): c for c in Customer.query.all()}
        for row in reader:
            cid = self.get_val(row, 'customer_id')
            if not cid: continue
            
            key = str(cid).strip().lower()
            cust = existing_customers.get(key)
            if not cust:
                cust = Customer(customer_id=cid)
                db.session.add(cust)
                existing_customers[key] = cust
                self.stats['created'] += 1
            else:
                self.stats['updated'] += 1
            
            cust.name = self.get_val(row, 'name')
            cust.customer_type = self.get_val(row, 'type')
            cust.service_voltage = self.get_val(row, 'voltage')

class ConsumptionImporter(BaseImporter):
    file_type = 'energy_consumption'
    header_mappings = {
        'customer_id': ['Customer ID', 'customer_id', 'Cust ID', 'Account Number'],
        'period': ['Billing Period', 'Billing Period Code', 'period', 'billing_period',
                   'Period', 'Month', 'Bill Period'],
        'kwh': ['kWh Consumed', 'Energy Consumed (kWHr)', 'Energy Consumed', 'kwh',
                'kWh', 'kwh_consumed', 'Consumption', 'Total kWh'],
        'pf': ['Power Factor', 'power_factor', 'PF', 'pf']
    }
    
    def process_rows(self, reader):
        """Uses bulk_insert_mappings for high speed on large datasets.
        Auto-creates stub Customer records for any missing customer IDs
        to avoid ForeignKeyViolation errors.
        """
        mappings = []
        needed_cids = set()
        
        for row in reader:
            cid = self.get_val(row, 'customer_id')
            if not cid: continue
            
            needed_cids.add(str(cid).strip())
            mappings.append({
                'customer_id': str(cid).strip(),
                'billing_period': self.get_val(row, 'period'),
                'kwh_consumed': sanitize_float(self.get_val(row, 'kwh')),
                'power_factor': sanitize_float(self.get_val(row, 'pf'))
            })
        
        if not mappings:
            return
        
        # Auto-create stub customers for any IDs not yet in the customer table
        existing_cids = {c.customer_id for c in Customer.query.with_entities(Customer.customer_id).all()}
        missing_cids = needed_cids - existing_cids
        
        if missing_cids:
            for cid in missing_cids:
                db.session.add(Customer(customer_id=cid, name=f'Customer {cid}'))
            db.session.flush()  # Flush so FKs resolve before bulk insert
        
        db.session.bulk_insert_mappings(EnergyConsumption, mappings)
        self.stats['created'] = len(mappings)
        if missing_cids:
            self.stats['auto_created_customers'] = len(missing_cids)

class LoadCurveImporter(BaseImporter):
    file_type = 'load_curves'
    header_mappings = {
        'load_curve_id': ['Load Curve ID', 'id'],
        'customer_type': ['Customer Type', 'type'],
        'description': ['Description', 'desc']
    }
    
    def process_rows(self, reader):
        existing_curves = {c.load_curve_id.strip().upper(): c for c in LoadCurve.query.all()}
        
        for row in reader:
            lcid = self.get_val(row, 'load_curve_id')
            if not lcid: continue
            
            clean_id = str(lcid).strip().upper()
            curve = existing_curves.get(clean_id)
            if not curve:
                curve = LoadCurve(load_curve_id=clean_id)
                db.session.add(curve)
                existing_curves[clean_id] = curve
                self.stats['created'] += 1
            else:
                self.stats['updated'] += 1
                
            curve.customer_type = self.get_val(row, 'customer_type')
            curve.description = self.get_val(row, 'description')
            
            # Dynamic mapping for hours
            for i in range(1, 25):
                val = self.get_val(row, [f'Hour {i}', f'hour_{i}'])
                setattr(curve, f'hour_{i}', sanitize_float(val))
