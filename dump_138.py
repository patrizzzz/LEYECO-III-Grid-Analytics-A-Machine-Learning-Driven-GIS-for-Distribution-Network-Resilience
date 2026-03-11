
import pandas as pd
df = pd.read_csv('bus_data.csv')
rows = df[df['post_id'].astype(str).str.strip() == '138']
print(rows.to_string())
