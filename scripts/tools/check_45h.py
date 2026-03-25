import pandas as pd
df1 = pd.read_csv('example2.csv')
found_in_tx = df1[df1['To  \nSecondary Bus ID'].astype(str).str.contains('108-45H') | df1['Distribution Transformer ID'].astype(str).str.contains('108-45H') | df1['From \nPrimary Bus ID'].astype(str).str.contains('108-45H')]
print("Found in Transformers (example2.csv):")
print(found_in_tx.to_string())

df2 = pd.read_csv('EXAMPLEDATA.csv')
found_in_lines = df2[df2['From_Bus_ID'].astype(str).str.contains('108-45H') | df2['To_Bus_ID'].astype(str).str.contains('108-45H')]
print("\nFound in Primary Lines (EXAMPLEDATA.csv):")
print(found_in_lines.to_string())
