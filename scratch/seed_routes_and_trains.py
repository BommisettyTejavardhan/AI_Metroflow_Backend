import asyncio
import os
import sys
import random

sys.path.append(os.path.abspath("."))
from backend.database import connect_db, db_instance
from bson import ObjectId

async def seed():
    await connect_db()
    db = db_instance.db
    
    # Get unique routes from schedules
    schedules = await db.schedules.find({}).to_list(length=None)
    
    unique_routes = set()
    for s in schedules:
        unique_routes.add(s.get("route"))
        
    print(f"Found {len(unique_routes)} unique routes.")
    
    for r_name in unique_routes:
        if not r_name:
            continue
        
        # Upsert route
        route_doc = await db.routes.find_one({"name": r_name})
        if not route_doc:
            res = await db.routes.insert_one({"name": r_name, "status": "Active", "total_distance_km": random.randint(15, 45)})
            route_id = res.inserted_id
        else:
            route_id = route_doc["_id"]
            
        # Add a few dummy trains for this route
        for i in range(random.randint(3, 8)):
            train_doc = {
                "train_number": f"TRN-{str(route_id)[:4]}-{i}",
                "train_name": f"Express {i}",
                "route_id": str(route_id),
                "route_name": r_name,
                "status": "In Service",
                "capacity": 1500,
                "current_station": "Unknown",
                "speed_kmh": random.randint(40, 70),
                "delay_minutes": random.randint(0, 10)
            }
            await db.trains.update_one(
                {"train_number": train_doc["train_number"]},
                {"$set": train_doc},
                upsert=True
            )
            
    print("Seeding complete. Routes and Trains populated.")

if __name__ == "__main__":
    asyncio.run(seed())
