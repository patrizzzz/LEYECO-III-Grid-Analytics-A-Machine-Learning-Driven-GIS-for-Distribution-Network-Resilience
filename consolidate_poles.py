#!/usr/bin/env python3
import pandas as pd
from app import app, db
from models import Post, LineConnection

def consolidate():
    with app.app_context():
        print("=" * 80)
        print("REBUILDING POLE TABLE (BUS IDS AS PRIMARY)")
        print("=" * 80)

        # 1. Read coordinates
        poles_df = pd.read_csv('poles.csv')
        # 2. Get unique bus IDs
        lines_df = pd.read_csv('EXAMPLEDATA.csv')
        
        buses = []
        seen = set()
        for _, row in lines_df.iterrows():
            for b in (str(row['From_Bus_ID']).strip(), str(row['To_Bus_ID']).strip()):
                if b not in seen and b != 'nan':
                    buses.append(b)
                    seen.add(b)

        print(f"Poles: {len(poles_df)}, Unique Buses: {len(buses)}")
        limit = min(len(poles_df), len(buses))

        # 3. Clear related tables first due to Foreign Key constraints
        print("Clearing existing connections and posts...")
        LineConnection.query.delete()
        Post.query.delete()
        db.session.flush()

        # 4. Rebuild from Sequence
        for i in range(limit):
            bus_id = buses[i]
            lat = poles_df.iloc[i]['latitude']
            lng = poles_df.iloc[i]['longitude']
            
            new_post = Post(
                pole_number=bus_id,
                primary_bus_id=bus_id,
                lat=lat,
                lng=lng,
                name=f"Pole {bus_id}",
                status='active'
            )
            db.session.add(new_post)

        db.session.commit()
        print(f"Rebuild complete. Created {limit} bus-based poles.")

if __name__ == '__main__':
    consolidate()
