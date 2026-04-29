import os
import sys
sys.path.append(os.getcwd())
from app import app
from models import LineConnection

with app.app_context():
    total = LineConnection.query.count()
    with_circuit = LineConnection.query.filter(LineConnection.circuit.isnot(None)).count()
    print(f"Total: {total}, With Circuit: {with_circuit}")
    if with_circuit > 0:
        c = LineConnection.query.filter(LineConnection.circuit.isnot(None)).first()
        print(f"Example: {c.from_bus} -> {c.to_bus}, Feeder: {c.feeder}, Circuit: {c.circuit}")
