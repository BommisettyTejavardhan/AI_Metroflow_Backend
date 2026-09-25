from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List, Dict
import asyncio
import json
import random
from datetime import datetime
from bson import ObjectId
from backend.database import db_instance
from backend.models.crowd import StationCrowdSummary

router = APIRouter(prefix="/api/crowd", tags=["Crowd Monitoring"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"New WebSocket client connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Handle broken connections gracefully
                pass

manager = ConnectionManager()

# Background simulation variables
simulation_running = False

@router.get("/live-status")
async def get_live_status():
    return await get_simulated_state()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send initial data immediately
        initial_data = await get_simulated_state()
        await websocket.send_json({
            "type": "init",
            "data": initial_data
        })
        
        # Send a welcome toast notification to prove the system works
        await websocket.send_json({
            "type": "new_alert",
            "data": {
                "id": "welcome-test",
                "type": "System Notification",
                "message": "Notification system is fully active and connected!",
                "level": "Info",
                "timestamp": datetime.utcnow().isoformat()
            }
        })
        
        while True:
            # Keep connection alive; wait for any message from client (optional)
            data = await websocket.receive_text()
            # If client requests a manual refresh
            if data == "refresh":
                state = await get_simulated_state()
                await websocket.send_json({"type": "update", "data": state})
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def get_simulated_state() -> dict:
    db = db_instance.db
    if db is None:
        return {"stations": [], "trains": [], "alerts": []}
        
    stations = await db.stations.find({}).to_list(length=None)
    trains = await db.trains.find({}).to_list(length=50)
    
    # 1. Simulate Crowd Data for Stations
    station_payloads = []
    for s in stations:
        # Determine if peak hours (08:00 - 10:00, 17:00 - 19:30)
        now = datetime.now()
        hour = now.hour
        is_peak = (8 <= hour <= 10) or (17 <= hour <= 19)
        
        # Add random fluctuation
        base = 600 if is_peak else 150
        passengers = random.randint(base - 100, base + 200)
        passengers = max(10, passengers)
        
        inflow = int(passengers * random.uniform(0.35, 0.55))
        outflow = passengers - inflow + random.randint(-15, 15)
        waiting = random.randint(5, int(passengers * 0.3))
        
        percent = min(100, int((passengers / 1000) * 100))
        if percent <= 40:
            level = "Green"
        elif percent <= 60:
            level = "Yellow"
        elif percent <= 80:
            level = "Orange"
        else:
            level = "Red"
            
        station_payloads.append({
            "station_id": str(s["_id"]),
            "name": s.get("station_name", s.get("name", "Unknown")),
            "line": s["line"],
            "latitude": s["latitude"],
            "longitude": s["longitude"],
            "distance_from_start_km": s.get("distance_from_start_km", 0),
            "passenger_count": passengers,
            "crowd_level": level,
            "crowd_percentage": percent,
            "inflow": max(0, inflow),
            "outflow": max(0, outflow),
            "waiting_passengers": max(0, waiting)
        })
        
    # 2. Simulate Train Positions
    train_payloads = []
    for idx, t in enumerate(trains):
        # Find the route stations to interpolate position
        route_stations = []
        try:
            route = await db.routes.find_one({"_id": ObjectId(t["route_id"])})
            if route and route["stations"]:
                route_stations = route["stations"]
        except Exception:
            pass
            
        if route_stations:
            # Simulate movement: select a station based on current timestamp
            station_count = len(route_stations)
            # Cycle through stations every minute
            curr_index = (datetime.now().minute + idx * 3) % station_count
            current_station_info = route_stations[curr_index]
            
            # Retrieve lat/lng of station
            st_doc = await db.stations.find_one({"_id": current_station_info["station_id"]})
            if st_doc:
                lat = st_doc["latitude"]
                lng = st_doc["longitude"]
            else:
                lat, lng = 28.6139, 77.2090 # Default Delhi center
                
            # Randomize passenger count inside train based on capacity
            occupancy_pct = random.randint(20, 95)
            curr_occ = int(t["capacity"] * (occupancy_pct / 100))
            
            # Map occupancy to color
            if occupancy_pct < 40:
                color = "Green"
            elif occupancy_pct < 70:
                color = "Yellow"
            elif occupancy_pct < 88:
                color = "Orange"
            else:
                color = "Red"
                
            train_payloads.append({
                "train_id": str(t["_id"]),
                "train_number": t["train_number"],
                "train_name": t["train_name"],
                "status": t["status"],
                "capacity": t["capacity"],
                "current_occupancy": curr_occ,
                "occupancy_percentage": occupancy_pct,
                "crowd_level": color,
                "latitude": lat + random.uniform(-0.002, 0.002), # Add tiny offset so trains aren't directly on top of station center
                "longitude": lng + random.uniform(-0.002, 0.002),
                "current_station": current_station_info["name"]
            })
            
    # 3. Fetch Recent Active Alerts
    alerts_cursor = db.alerts.find({"status": "Active"}).sort("timestamp", -1).limit(5)
    alerts_list = []
    async for a in alerts_cursor:
        a["id"] = str(a["_id"])
        alerts_list.append({
            "id": a["id"],
            "type": a["type"],
            "message": a["message"],
            "level": a["level"],
            "timestamp": a["timestamp"].isoformat()
        })
        
    return {
        "stations": station_payloads,
        "trains": train_payloads,
        "alerts": alerts_list,
        "timestamp": datetime.utcnow().isoformat()
    }

async def simulation_loop():
    global simulation_running
    if simulation_running:
        return
        
    simulation_running = True
    print("Starting Metro System Real-Time WebSocket Simulation Loop...")
    
    while True:
        try:
            await asyncio.sleep(4) # Broadcast updates every 4 seconds
            if len(manager.active_connections) > 0:
                state = await get_simulated_state()
                
                # Check for critical thresholds to raise automated alerts in DB
                await auto_generate_alerts(state)
                
                await manager.broadcast({
                    "type": "update",
                    "data": state
                })
        except Exception as e:
            print(f"Error in simulation loop: {e}")
            await asyncio.sleep(5)

async def auto_generate_alerts(state: dict):
    db = db_instance.db
    if db is None:
        return
        
    # Auto-resolve old alerts (older than 1 minute) to allow new ones to trigger
    one_min_ago = datetime.utcnow() - __import__('datetime').timedelta(minutes=1)
    await db.alerts.update_many(
        {"status": "Active", "timestamp": {"$lt": one_min_ago}},
        {"$set": {"status": "Resolved"}}
    )
        
    # Check Red Level stations and randomly trigger alerts (so it's not spamming every loop)
    red_stations = [s for s in state["stations"] if s["crowd_level"] == "Red"]
    for s in red_stations[:2]:
        if random.random() < 0.15: # 15% chance to log a persistent alert
            # Check if active overcrowding alert already exists for this station
            exists = await db.alerts.find_one({
                "target_id": s["station_id"],
                "type": "Overcrowding",
                "status": "Active"
            })
            if not exists:
                alert_doc = {
                    "type": "Overcrowding",
                    "target_type": "Station",
                    "target_id": s["station_id"],
                    "message": f"Critical overcrowding detected at {s['name']}. Crowd density is {s['crowd_percentage']}%.",
                    "level": "Critical",
                    "timestamp": datetime.utcnow(),
                    "status": "Active"
                }
                result = await db.alerts.insert_one(alert_doc)
                alert_doc["id"] = str(result.inserted_id)
                alert_doc.pop("_id", None)
                alert_doc["timestamp"] = alert_doc["timestamp"].isoformat()
                print(f"Automated Alert: Overcrowding at {s['name']}")
                await manager.broadcast({
                    "type": "new_alert",
                    "data": alert_doc
                })
    # Check for random train delay simulations
    trains_active = [t for t in state["trains"] if t["status"] == "In Service"]
    if trains_active and random.random() < 0.05: # 5% chance to delay a train
        target_train = random.choice(trains_active)
        # Check if already active delay alert
        exists = await db.alerts.find_one({
            "target_id": target_train["train_id"],
            "type": "Train Delay",
            "status": "Active"
        })
        if not exists:
            delay_min = random.choice([5, 8, 12, 20])
            alert_doc = {
                "type": "Train Delay",
                "target_type": "Train",
                "target_id": target_train["train_id"],
                "message": f"Train {target_train['train_number']} ({target_train['train_name']}) is delayed by {delay_min} mins at {target_train['current_station']}.",
                "level": "Warning" if delay_min < 15 else "Critical",
                "timestamp": datetime.utcnow(),
                "status": "Active"
            }
            result = await db.alerts.insert_one(alert_doc)
            alert_doc["id"] = str(result.inserted_id)
            alert_doc.pop("_id", None)
            alert_doc["timestamp"] = alert_doc["timestamp"].isoformat()
            print(f"Automated Alert: Delay for train {target_train['train_number']}")
            await manager.broadcast({
                "type": "new_alert",
                "data": alert_doc
            })
