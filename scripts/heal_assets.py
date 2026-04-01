import sys
import os

# Add the project root to the python path
sys.path.append(os.getcwd())

from app import app
from extensions import db
from models import Post, BusNode, VoltageRegulator, ShuntCapacitor, ShuntInductor, SeriesInductor
from services.linkage_service import LinkageService, LinkageContext

def heal_assets():
    with app.app_context():
        print("Starting Asset Healing Process...")
        
        posts = Post.query.all()
        bus_nodes = BusNode.query.all()
        context = LinkageContext(posts=posts, bus_nodes=bus_nodes)
        
        # 1. Reconcile Voltage Regulators
        vrs = VoltageRegulator.query.all()
        vr_count = 0
        for vr in vrs:
            p = LinkageService.fuzzy_match_asset_to_post(vr, context=context)
            if p:
                target_bus = vr.from_bus_id or vr.to_bus_id
                if target_bus:
                    bn = BusNode.query.filter_by(bus_id=target_bus).first()
                    if not bn:
                        bn = BusNode(bus_id=target_bus, pole_id=p.id, pole_number=p.pole_number)
                        db.session.add(bn)
                    else:
                        bn.pole_id = p.id
                        bn.pole_number = p.pole_number
                    vr_count += 1
        print(f"Healed {vr_count} Voltage Regulators.")

        # 2. Reconcile Shunt Capacitors
        caps = ShuntCapacitor.query.all()
        cap_count = 0
        for cap in caps:
            p = LinkageService.fuzzy_match_asset_to_post(cap, context=context)
            if p and cap.bus_connected_id:
                bn = BusNode.query.filter_by(bus_id=cap.bus_connected_id).first()
                if not bn:
                    bn = BusNode(bus_id=cap.bus_connected_id, pole_id=p.id, pole_number=p.pole_number)
                    db.session.add(bn)
                else:
                    bn.pole_id = p.id
                    bn.pole_number = p.pole_number
                cap_count += 1
        print(f"Healed {cap_count} Shunt Capacitors.")

        # 3. Reconcile Shunt Inductors
        s_ind = ShuntInductor.query.all()
        si_count = 0
        for ind in s_ind:
            p = LinkageService.fuzzy_match_asset_to_post(ind, context=context)
            if p and ind.bus_connected_id:
                bn = BusNode.query.filter_by(bus_id=ind.bus_connected_id).first()
                if not bn:
                    bn = BusNode(bus_id=ind.bus_connected_id, pole_id=p.id, pole_number=p.pole_number)
                    db.session.add(bn)
                else:
                    bn.pole_id = p.id
                    bn.pole_number = p.pole_number
                si_count += 1
        print(f"Healed {si_count} Shunt Inductors.")

        # 4. Reconcile Series Inductors
        ser_ind = SeriesInductor.query.all()
        sei_count = 0
        for ind in ser_ind:
            p = LinkageService.fuzzy_match_asset_to_post(ind, context=context)
            if p:
                target_bus = ind.from_bus_id or ind.to_bus_id
                if target_bus:
                    bn = BusNode.query.filter_by(bus_id=target_bus).first()
                    if not bn:
                        bn = BusNode(bus_id=target_bus, pole_id=p.id, pole_number=p.pole_number)
                        db.session.add(bn)
                    else:
                        bn.pole_id = p.id
                        bn.pole_number = p.pole_number
                    sei_count += 1
        print(f"Healed {sei_count} Series Inductors.")

        db.session.commit()
        print("Asset Healing Complete!")

if __name__ == "__main__":
    heal_assets()
