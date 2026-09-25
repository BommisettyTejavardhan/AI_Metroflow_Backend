import asyncio
import os
import sys
import random
from datetime import datetime, timedelta
sys.path.append(os.path.abspath("."))
from backend.database import connect_db, db_instance

async def seed_crowd():
    await connect_db()
    db = db_instance.db
    
    stations = await db.stations.find({}).to_list(length=50)
    if not stations:
        print("No stations found to seed crowd data.")
        return
        
    records = []
    now = datetime.utcnow()
    
    for _ in range(200):
        st = random.choice(stations)
        # Random time within the last 7 days
        ts = now - timedelta(days=random.uniform(0, 7))
        
        inflow = random.randint(50, 500)
        outflow = random.randint(40, 450)
        waiting = random.randint(10, 200)
        total = inflow + waiting
        pct = min(100, int((total / 800) * 100))
        
        level = "Green"
        if pct > 85: level = "Red"
        elif pct > 60: level = "Orange"
        elif pct > 40: level = "Yellow"
        
        records.append({
            "station_id": st["_id"],
            "passenger_count": total,
            "inflow": inflow,
            "outflow": outflow,
            "waiting_passengers": waiting,
            "crowd_percentage": pct,
            "crowd_level": level,
            "timestamp": ts
        })
        
    await db.crowd_data.insert_many(records)
    print(f"Successfully inserted {len(records)} crowd data records for the Passenger Report!")

if __name__ == "__main__":
    asyncio.run(seed_crowd())
