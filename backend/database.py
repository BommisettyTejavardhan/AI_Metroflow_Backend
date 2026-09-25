import os
import csv
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.hash import bcrypt
from backend.config import settings

class Database:
    client: AsyncIOMotorClient = None
    db = None

db_instance = Database()

async def connect_db():
    try:
        db_instance.client = AsyncIOMotorClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
        db_instance.db = db_instance.client[settings.DATABASE_NAME]
        # Ping the server to check connectivity
        await db_instance.client.admin.command('ping')
        print(f"Connected to MongoDB database: {settings.DATABASE_NAME}")
    except Exception as e:
        print(f"Warning: Failed to connect to MongoDB: {e}")
        print("FastAPI will start, but database calls will fail or use mock states.")

async def close_db():
    if db_instance.client:
        db_instance.client.close()
        print("MongoDB connection closed.")

async def init_db():
    db = db_instance.db
    if db is None:
        return
        
    print("Initializing Database Indexes...")
    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.stations.create_index("station_code", unique=True, sparse=True)
    await db.stations.create_index([("latitude", 1), ("longitude", 1)])
    await db.trains.create_index("train_number", unique=True)
    await db.routes.create_index("name", unique=True)
    await db.schedules.create_index([("train_id", 1), ("station_id", 1)])
    await db.crowd_data.create_index([("station_id", 1), ("timestamp", -1)])
    await db.alerts.create_index([("status", 1), ("timestamp", -1)])
    await db.predictions.create_index([("station", 1), ("timestamp", -1)])
    await db.passenger_history.create_index([("station_id", 1), ("timestamp", -1)])
    await db.traffic_reports.create_index("created_at")
    await db.train_status.create_index([("train_id", 1), ("timestamp", -1)])
    await db.notifications.create_index([("user_id", 1), ("timestamp", -1)])
    await db.announcements.create_index([("expiry_date", 1)])
    await db.heatmap_data.create_index([("timestamp", -1)])
    
    # Seed default users
    user_count = await db.users.count_documents({})
    if user_count == 0:
        print("Seeding default users...")
        users_to_seed = [
            {
                "name": "Platform Admin",
                "email": "admin@metroflow.com",
                "password_hash": bcrypt.hash("admin123"),
                "role": "Admin",
                "status": "Active",
                "settings": {"theme": "dark", "language": "en", "notifications": True}
            },
            {
                "name": "Delhi Operator",
                "email": "operator@metroflow.com",
                "password_hash": bcrypt.hash("operator123"),
                "role": "Metro Operator",
                "status": "Active",
                "settings": {"theme": "dark", "language": "en", "notifications": True}
            },
            {
                "name": "Lead Analyst",
                "email": "analyst@metroflow.com",
                "password_hash": bcrypt.hash("analyst123"),
                "role": "Analyst",
                "status": "Active",
                "settings": {"theme": "dark", "language": "en", "notifications": True}
            }
        ]
        await db.users.insert_many(users_to_seed)
        print("Default users seeded successfully (passwords: admin123, operator123, analyst123).")

    # Seed Stations and Routes from CSV
    station_count = await db.stations.count_documents({})
    csv_path = "datasets/Delhi-Metro-Network.csv"
    if station_count == 0 and os.path.exists(csv_path):
        print("Seeding stations and routes from Delhi Metro CSV...")
        stations_to_seed = []
        routes_by_line = {}
        
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                try:
                    s_id = row.get("Station ID", str(idx + 1)).strip()
                    name = row.get("Station Name", "").strip()
                    dist = float(row.get("Distance from Start (km)", 0.0) or 0.0)


                    line = row.get("Line", "").strip()
                    layout = row.get("Station Layout", "Elevated").strip()
                    lat = float(row.get("Latitude", 0.0))
                    lng = float(row.get("Longitude", 0.0))
                    
                    code = f"ST-{s_id.zfill(3)}"
                    
                    station_doc = {
                        "station_code": code,
                        "name": name,
                        "line": line,
                        "zone": "Delhi NCR",
                        "platforms": [1, 2],
                        "latitude": lat,
                        "longitude": lng,
                        "status": "Active"
                    }
                    stations_to_seed.append(station_doc)
                    
                    # Store route details grouped by line
                    if line not in routes_by_line:
                        routes_by_line[line] = []
                    routes_by_line[line].append({
                        "station_code": code,
                        "name": name,
                        "distance_km": dist,
                        "latitude": lat,
                        "longitude": lng
                    })
                except Exception as ex:
                    print(f"Error parsing row: {row}, error: {ex}")
                    
        if stations_to_seed:
            # Bulk insert stations
            result = await db.stations.insert_many(stations_to_seed)
            inserted_ids = result.inserted_ids
            print(f"Seeded {len(inserted_ids)} stations.")
            
            # Map station names to their inserted IDs
            station_cursor = db.stations.find({}, {"name": 1, "_id": 1, "station_code": 1})
            station_id_map = {}
            async for s in station_cursor:
                station_id_map[s["station_code"]] = s["_id"]
            
            # Create routes
            routes_docs = []
            for line, stations_in_line in routes_by_line.items():
                # Sort stations in line by distance
                stations_in_line.sort(key=lambda x: x["distance_km"])
                
                route_stations = []
                for s in stations_in_line:
                    s_id = station_id_map.get(s["station_code"])
                    if s_id:
                        route_stations.append({
                            "station_id": s_id,
                            "name": s["name"],
                            "distance_km": s["distance_km"]
                        })
                
                route_doc = {
                    "name": f"{line} Route",
                    "line": line,
                    "stations": route_stations
                }
                routes_docs.append(route_doc)
                
            if routes_docs:
                await db.routes.insert_many(routes_docs)
                print(f"Seeded {len(routes_docs)} routes based on lines.")
                
            # Seed some default trains and schedules
            await seed_trains_and_schedules(db)
            
            # Seed some initial crowd data
            await seed_crowd_data(db)

async def seed_trains_and_schedules(db):
    print("Seeding trains and schedules...")
    routes = await db.routes.find({}).to_list(length=10)
    if not routes:
        return
        
    trains_to_seed = []
    schedules_to_seed = []
    
    import random
    from datetime import datetime, timedelta
    
    for idx, r in enumerate(routes[:5]): # Take top 5 lines/routes for mock scheduling
        line_short = r["line"].split()[0].upper()
        
        # Create 2 trains for this line (one going forward, one reverse direction)
        for t_idx in [1, 2]:
            t_num = f"TR-{line_short}-{t_idx:02d}"
            t_name = f"{r['line']} Train {t_idx}"
            
            train_doc = {
                "train_number": t_num,
                "train_name": t_name,
                "route_id": r["_id"],
                "capacity": 1200,
                "current_occupancy": random.randint(100, 800),
                "status": "In Service" if t_idx == 1 else "Standing By",
                "arrival_time": "06:00",
                "departure_time": "23:00"
            }
            trains_to_seed.append(train_doc)
            
    if trains_to_seed:
        t_result = await db.trains.insert_many(trains_to_seed)
        print(f"Seeded {len(t_result.inserted_ids)} trains.")
        
        # Map train numbers to inserted IDs
        train_cursor = db.trains.find({})
        inserted_trains = await train_cursor.to_list(length=100)
        
        # Create simple schedules for 'In Service' trains
        base_time = datetime.strptime("08:00", "%H:%M")
        for t in inserted_trains:
            if t["status"] != "In Service":
                continue
            r_doc = await db.routes.find_one({"_id": t["route_id"]})
            if not r_doc or not r_doc["stations"]:
                continue
                
            stations_list = r_doc["stations"]
            curr_time = base_time
            
            # Create schedule for each station along the route
            for s_idx, rs in enumerate(stations_list):
                arr_time_str = curr_time.strftime("%H:%M")
                curr_time += timedelta(minutes=2)
                dep_time_str = curr_time.strftime("%H:%M")
                # travel to next station takes 5 minutes
                curr_time += timedelta(minutes=5)
                
                sched_doc = {
                    "train_id": t["_id"],
                    "route_id": t["route_id"],
                    "station_id": rs["station_id"],
                    "platform": random.choice([1, 2]),
                    "scheduled_arrival": arr_time_str,
                    "scheduled_departure": dep_time_str,
                    "actual_arrival": arr_time_str,
                    "actual_departure": dep_time_str,
                    "delay_min": 0,
                    "status": "On Time"
                }
                schedules_to_seed.append(sched_doc)
                
        if schedules_to_seed:
            await db.schedules.insert_many(schedules_to_seed)
            print(f"Seeded {len(schedules_to_seed)} schedule entries.")

async def seed_crowd_data(db):
    print("Seeding initial crowd data...")
    import random
    from datetime import datetime, timedelta
    
    stations = await db.stations.find({}).to_list(length=20) # seed crowd for 20 stations
    if not stations:
        return
        
    crowd_docs = []
    now = datetime.utcnow()
    
    for s in stations:
        for offset_hours in range(12, 0, -1):
            timestamp = now - timedelta(hours=offset_hours)
            
            # Simulate passenger traffic
            hour = timestamp.hour
            is_peak = (8 <= hour <= 10) or (17 <= hour <= 19)
            
            p_count = random.randint(300, 1000) if is_peak else random.randint(20, 300)
            inflow = int(p_count * random.uniform(0.4, 0.6))
            outflow = p_count - inflow + random.randint(-20, 20)
            waiting = random.randint(0, max(5, int(p_count * 0.4)))
            
            # Determine level
            percent = min(100, int((p_count / 1000) * 100))
            if percent < 30:
                level = "Green"
            elif percent < 60:
                level = "Yellow"
            elif percent < 85:
                level = "Orange"
            else:
                level = "Red"
                
            crowd_docs.append({
                "station_id": s["_id"],
                "timestamp": timestamp,
                "passenger_count": p_count,
                "inflow": max(0, inflow),
                "outflow": max(0, outflow),
                "waiting_passengers": max(0, waiting),
                "crowd_level": level,
                "crowd_percentage": percent
            })
            
    if crowd_docs:
        await db.crowd_data.insert_many(crowd_docs)
        print(f"Seeded {len(crowd_docs)} historical crowd data logs.")
