import pandas as pd
import re

def normalize_column_name(name):
    if not name or pd.isna(name):
        return ''
    normalized = str(name).strip().lower()
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = normalized.replace('(', '').replace(')', '').replace('-', '_').replace('%', 'pct')
    while '__' in normalized:
        normalized = normalized.replace('__', '_')
    return normalized.strip('_')

df = pd.read_csv('example2.csv', encoding='utf-8-sig')
df.columns = [normalize_column_name(c) for c in df.columns]

# Search for 130 in transformer id or bus ids
matches = df[
    (df['distribution_transformer_id'].astype(str).str.contains('130')) |
    (df['from_primary_bus_id'].astype(str).str.contains('130')) |
    (df['to_secondary_bus_id'].astype(str).str.contains('130'))
]

print(f"Matches for '130': {len(matches)}")
if len(matches) > 0:
    print(matches[['distribution_transformer_id', 'from_primary_bus_id', 'to_secondary_bus_id']].head(10))
