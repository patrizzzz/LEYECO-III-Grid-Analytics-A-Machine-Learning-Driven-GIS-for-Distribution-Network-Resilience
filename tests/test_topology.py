import pytest
from models import Post, DistributionLineSegment, DistributionTransformer, SecondaryLineSegment, SecondaryServiceDrop, Customer
from services.topology_service import TopologyService
from services.analysis_services import calculate_outage_impact

def test_downstream_trace_path(db):
    """
    Test a linear path: Substation -> P1 -> Trans -> S1 -> Customer
    """
    # 1. Setup minimal linear network
    # Primary Line: BUS_ROOT -> BUS_TRANS_PRI
    db.session.add(DistributionLineSegment(
        segment_id="L1", from_bus_id="BUS_ROOT", to_bus_id="BUS_TRANS_PRI"
    ))
    
    # Transformer: BUS_TRANS_PRI -> BUS_SEC_ROOT
    db.session.add(DistributionTransformer(
        transformer_id="T1", from_primary_bus_id="BUS_TRANS_PRI", to_secondary_bus_id="BUS_SEC_ROOT"
    ))
    
    # Secondary Line: BUS_SEC_ROOT -> BUS_S1
    db.session.add(SecondaryLineSegment(
        segment_id="L2", from_bus_id="BUS_SEC_ROOT", to_bus_id="BUS_S1"
    ))
    
    # Service Drop: BUS_S1 -> CUST_1
    db.session.add(SecondaryServiceDrop(
        service_drop_id="SD1", from_bus_id="BUS_S1", to_customer_id="CUST_1"
    ))
    
    db.session.commit()
    
    # 2. Trace from Root
    path = TopologyService.trace_downstream_sql("BUS_ROOT")
    
    # 3. Verify all levels are reached
    assert "BUS_TRANS_PRI" in path
    assert "BUS_SEC_ROOT" in path
    assert "BUS_S1" in path
    assert "CUST_1" in path
    assert len(path) == 5 # ROOT + 4 downstream

def test_upstream_trace_path(db):
    """Test tracing back from customer to substation."""
    db.session.add(DistributionLineSegment(segment_id="L1", from_bus_id="ROOT", to_bus_id="P1"))
    db.session.add(DistributionTransformer(transformer_id="T1", from_primary_bus_id="P1", to_secondary_bus_id="S1"))
    db.session.add(SecondaryServiceDrop(service_drop_id="SD1", from_bus_id="S1", to_customer_id="C1"))
    db.session.commit()
    
    path = TopologyService.trace_upstream_sql("C1")
    assert "S1" in path
    assert "P1" in path
    assert "ROOT" in path

def test_outage_impact_calculation(db):
    """Test the integrated outage impact result."""
    # Setup: 2 Customers, 1 Trans
    db.session.add(Customer(customer_id="C1", name="Cust 1", customer_type="RES1"))
    db.session.add(Customer(customer_id="C2", name="Cust 2", customer_type="RES1"))
    db.session.add(Post(pole_number="POLE_T", name="Pole T", lat=10.0, lng=124.0, primary_bus_id="PB1"))
    db.session.add(DistributionTransformer(transformer_id="TX1", from_primary_bus_id="PB1", to_secondary_bus_id="SB1"))
    db.session.add(SecondaryServiceDrop(service_drop_id="SD1", from_bus_id="SB1", to_customer_id="C1"))
    db.session.add(SecondaryServiceDrop(service_drop_id="SD2", from_bus_id="SB1", to_customer_id="C2"))
    db.session.commit()
    
    impact = calculate_outage_impact("POLE_T")
    
    assert impact['total_customers'] == 2
    assert "C1" in [c['customer_id'] for c in impact['customer_details']]
    assert "C2" in [c['customer_id'] for c in impact['customer_details']]
