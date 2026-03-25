import pandas as pd
import os

file_path = 'sample (1).xlsx'

if not os.path.exists(file_path):
    print(f"File not found: {file_path}")
    exit(1)

try:
    xl = pd.ExcelFile(file_path)
    with open('excel_inspection.txt', 'w', encoding='utf-8') as f:
        f.write(f"Sheet names: {xl.sheet_names}\n")

        for sheet in xl.sheet_names:
            f.write(f"\n--- Sheet: {sheet} ---\n")
            df = xl.parse(sheet, nrows=5)
            f.write(f"Columns: {list(df.columns)}\n")
            f.write("First 2 rows:\n")
            f.write(df.head(2).to_string() + "\n")
    print("Inspection complete. Results written to excel_inspection.txt")
except Exception as e:
    with open('excel_inspection.txt', 'w', encoding='utf-8') as f:
        f.write(f"Error reading Excel file: {e}\n")
    print(f"Error reading Excel file: {e}")
