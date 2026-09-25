import asyncio
import os
import sys
import json
import random

sys.path.append(os.path.abspath("."))

from backend.database import connect_db, db_instance

async def seed_schedules():
    await connect_db()
    db = db_instance.db
    if db is None:
        print("ERROR: Could not connect to MongoDB.")
        return

    json_path = "datasets/schedules.json"
    if not os.path.exists(json_path):
        print(f"ERROR: Dataset not found at {json_path}")
        return

    print("Loading schedules.json (417k entries)... this may take a moment.")
    with open(json_path, 'r', encoding='utf-8') as f:
        all_schedules = json.load(f)

    print(f"Total records loaded: {len(all_schedules)}")

    # Group by train_number to build full schedules with multiple stops
    train_groups = {}
    for entry in all_schedules:
        tn = entry.get('train_number', 'UNKNOWN')
        if tn not in train_groups:
            train_groups[tn] = []
        train_groups[tn].append(entry)

    print(f"Unique trains found: {len(train_groups)}")

    # Sample up to 200 trains for reasonable DB size
    train_numbers = list(train_groups.keys())
    sampled_trains = random.sample(train_numbers, min(200, len(train_numbers)))

    existing = await db.schedules.count_documents({})
    print(f"Existing schedules in DB: {existing}")

    inserted = 0
    errors = 0

    for train_number in sampled_trains:
        stops = train_groups[train_number]
        # Sort stops by their sequence (use arrival time as proxy)
        stops_sorted = sorted(stops, key=lambda x: str(x.get('arrival', '00:00')))

        train_name = stops[0].get('train_name', f'Train {train_number}')

        # Build stops list
        stops_list = []
        for stop in stops_sorted:
            stops_list.append({
                "station_name": stop.get('station_name', ''),
                "station_code": stop.get('station_code', ''),
                "arrival": stop.get('arrival', '--'),
                "departure": stop.get('departure', '--'),
                "day": stop.get('day', 1)
            })

        if not stops_list:
            continue

        origin = stops_list[0]['station_name']
        destination = stops_list[-1]['station_name']

        schedule_doc = {
            "train_number": str(train_number),
            "train_name": train_name,
            "origin": origin,
            "destination": destination,
            "total_stops": len(stops_list),
            "stops": stops_list,
            "status": "On Time",
            "frequency": "Daily",
            "days_of_week": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
            "departure_time": stops_list[0].get('departure', '00:00'),
            "arrival_time": stops_list[-1].get('arrival', '00:00'),
            "platform": random.randint(1, 4),
            "route": f"{origin} → {destination}",
            "created_at": "2024-01-01T00:00:00Z"
        }

        # Upsert by train_number
        result = await db.schedules.update_one(
            {"train_number": str(train_number)},
            {"$set": schedule_doc},
            upsert=True
        )
        inserted += 1

        if inserted % 25 == 0:
            print(f"  Progress: {inserted}/{len(sampled_trains)} trains seeded...")

    print(f"\nSchedule seeding complete!")
    print(f"  Trains seeded: {inserted}")
    print(f"  Errors: {errors}")
    total = await db.schedules.count_documents({})
    print(f"  Total schedules in DB now: {total}")

if __name__ == "__main__":
    asyncio.run(seed_schedules())
