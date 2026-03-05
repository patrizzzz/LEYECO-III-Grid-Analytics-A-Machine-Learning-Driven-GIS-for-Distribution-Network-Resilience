
import os
import sys
sys.path.append(os.getcwd())
from app import app
from extensions import db
from models import SecondaryLineSegment

with app.app_context():
    bus_id = 'P00000001'
    lines = SecondaryLineSegment.query.filter(
        (SecondaryLineSegment.from_bus_id == bus_id) | 
        (SecondaryLineSegment.to_bus_id == bus_id)
    ).limit(20).all()
    
    print(f"Sample of 20 connections for {bus_id}:")
    for l in lines:
        print(f"  ID: {l.id}, From: {l.from_bus_id}, To: {l.to_bus_id}")
        
    total = SecondaryLineSegment.query.filter(
        (SecondaryLineSegment.from_bus_id == bus_id) | 
        (SecondaryLineSegment.to_bus_id == bus_id)
    ).count()
    print(f"Total: {total}")
