#!/usr/bin/env python3
import pandas as pd

df = pd.read_csv('poles_with_coordinates.csv')
print(f'Total poles: {len(df)}')
print(f'Unique poles: {df["pole_number"].nunique()}')
print(f'Duplicates: {len(df) - df["pole_number"].nunique()}')

# Keep only first occurrence of each pole (same location)
df_unique = df.drop_duplicates(subset=['pole_number'], keep='first')
print(f'\nAfter removing duplicates: {len(df_unique)} poles')

# Save cleaned version
df_unique.to_csv('poles_with_coordinates_clean.csv', index=False)
print('Saved to poles_with_coordinates_clean.csv')
