import asyncio
import os
import sys
import pandas as pd
from datetime import datetime

sys.path.append(os.path.abspath("."))

from backend.database import connect_db, db_instance

LINE_COLORS = {
    "Red line": "#ef4444",
    "Yellow line": "#eab308",
    "Blue line": "#3b82f6",
    "Pink line": "#ec4899",
    "Magenta line": "#d946ef",
    "Voilet line": "#8b5cf6",
    "Violet line": "#8b5cf6",
    "Green line": "#22c55e",
    "Green line branch": "#16a34a",
    "Aqua line": "#06b6d4",
    "Rapid Metro": "#64748b",
    "Gray line": "#9ca3af",
    "Orange line": "#f97316",
    "Blue line branch": "#60a5fa",
}

async def seed_stations():
    await connect_db()
    db = db_instance.db
    if db is None:
        print("ERROR: Could not connect to MongoDB.")
        return

    csv_path = "datasets/Delhi-Metro-Network.csv"
    if not os.path.exists(csv_path):
        print(f"ERROR: Dataset not found at {csv_path}")
        return

    print("Loading Delhi Metro Network CSV...")
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    df['Station Name'] = df['Station Name'].str.strip()
    df['Line'] = df['Line'].str.strip()
    df['Station Layout'] = df['Station Layout'].str.strip()

    upserted = 0
    errors = 0
    existing_count = await db.stations.count_documents({})
    print(f"Existing stations in DB: {existing_count}")

    for _, row in df.iterrows():
        try:
            station_name = row['Station Name']
            # Clean station name - remove connection indicators like [Conn: Red]
            clean_name = station_name.split('[')[0].strip()
            line = row['Line']
            station_id = int(row['Station ID'])
            
            # Generate a unique station code using name prefix + ID to avoid collisions
            code_prefix = clean_name.upper().replace(' ', '_')[:8]
            station_code = f"{code_prefix}_{station_id}"
            
            doc = {
                "station_code": station_code,
                "name": clean_name,
                "full_name": station_name,
                "line": line,
                "line_color": LINE_COLORS.get(line, "#6366f1"),
                "latitude": float(row['Latitude']),
                "longitude": float(row['Longitude']),
                "distance_from_start_km": float(row['Distance from Start (km)']),
                "station_layout": row['Station Layout'],
                "opening_date": str(row['Opening Date']),
                "zone": "Delhi NCR",
                "status": "Active",
                "platforms": [{"platform_number": 1, "direction": "Both"}, {"platform_number": 2, "direction": "Both"}],
                "crowd_level": "Green",
                "passenger_count": 0,
                "crowd_percentage": 0,
                "inflow": 0,
                "outflow": 0,
                "updated_at": datetime.utcnow()
            }

            # Upsert by station name + line to avoid duplicates
            result = await db.stations.update_one(
                {"name": clean_name, "line": line},
                {"$set": doc},
                upsert=True
            )
            upserted += 1
        except Exception as e:
            print(f"  Error seeding station '{row.get('Station Name', '?')}': {e}")
            errors += 1

    print(f"\nStation seeding complete!")
    print(f"  Upserted: {upserted} stations")
    print(f"  Errors:   {errors}")
    total = await db.stations.count_documents({})
    print(f"  Total stations in DB now: {total}")

if __name__ == "__main__":
    asyncio.run(seed_stations())
