"""
Create a sample feeder_connections.xlsx in data/ with columns From_Bus, To_Bus.
Run once to get a template; replace with your real engineering feeder data.
"""
import os
from pathlib import Path

try:
    from openpyxl import Workbook
except ImportError:
    print("Install openpyxl: pip install openpyxl")
    raise

def main():
    base = Path(__file__).resolve().parent.parent
    data_dir = base / "data"
    data_dir.mkdir(exist_ok=True)
    path = data_dir / "feeder_connections.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Feeder"
    # Header row: Bus IDs only (no coordinates)
    ws.append(["From_Bus", "To_Bus"])
    # Example rows — replace with your bus IDs; both must exist in bus_post_mapping to draw
    ws.append(["BUS001", "BUS002"])
    ws.append(["BUS002", "BUS003"])
    wb.save(path)
    print("Created", path)

if __name__ == "__main__":
    main()
