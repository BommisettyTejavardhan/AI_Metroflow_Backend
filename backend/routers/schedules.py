from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime, timedelta
from backend.database import db_instance
from backend.auth import RoleChecker
from backend.models.schedule import ScheduleCreate, ScheduleUpdate, ScheduleResponse, OptimizeFrequencyRequest
from backend.routers.crowd import manager

router = APIRouter(prefix="/api/schedules", tags=["Schedules"])

admin_only = RoleChecker(["Admin"])
staff_only = RoleChecker(["Admin", "Operator", "Analyst"])

@router.get("", response_model=dict)
async def list_schedules(
    train_id: Optional[str] = Query(None),
    station_id: Optional[str] = Query(None),
    route_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    db = db_instance.db
    if db is None:
        return {"data": [], "total": 0}
        
    query = {}
    if train_id:
        try:
            query["train_id"] = ObjectId(train_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid train ID")
    if station_id:
        try:
            query["station_id"] = ObjectId(station_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid station ID")
    if route_id:
        try:
            query["route_id"] = ObjectId(route_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid route ID")
    if status:
        query["status"] = status
        
    total = await db.schedules.count_documents(query)
    skip = (page - 1) * limit
    
    cursor = db.schedules.find(query).skip(skip).limit(limit)
    schedules_list = []
    
    async for s in cursor:
        s["id"] = str(s["_id"])
        s["_id"] = str(s["_id"])
        s["train_id"] = str(s["train_id"])
        s["route_id"] = str(s["route_id"])
        s["station_id"] = str(s["station_id"])
        schedules_list.append(s)
        
    # Populate referenced names
    for s in schedules_list:
        try:
            t = await db.trains.find_one({"_id": ObjectId(s["train_id"])})
            if t:
                s["train_number"] = t["train_number"]
                s["train_name"] = t["train_name"]
            
            st = await db.stations.find_one({"_id": ObjectId(s["station_id"])})
            if st:
                s["station_name"] = st["name"]
                
            rt = await db.routes.find_one({"_id": ObjectId(s["route_id"])})
            if rt:
                s["route_name"] = rt["name"]
        except Exception:
            pass
            
    return {
        "data": schedules_list,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }

@router.get("/routes")
async def list_routes():
    db = db_instance.db
    if db is None:
        return []
    cursor = db.routes.find({})
    routes = []
    async for r in cursor:
        r["id"] = str(r["_id"])
        r["_id"] = str(r["_id"])
        if "stations" in r:
            for s in r["stations"]:
                if "station_id" in s:
                    s["station_id"] = str(s["station_id"])
        routes.append(r)
    return routes

@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(schedule_id: str):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    try:
        oid = ObjectId(schedule_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid schedule ID")
        
    sched = await db.schedules.find_one({"_id": oid})
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")
        
    sched["id"] = str(sched["_id"])
    sched["_id"] = str(sched["_id"])
    sched["train_id"] = str(sched["train_id"])
    sched["route_id"] = str(sched["route_id"])
    sched["station_id"] = str(sched["station_id"])
    
    # Populate referenced names
    t = await db.trains.find_one({"_id": ObjectId(sched["train_id"])})
    if t:
        sched["train_number"] = t["train_number"]
        sched["train_name"] = t["train_name"]
    st = await db.stations.find_one({"_id": ObjectId(sched["station_id"])})
    if st:
        sched["station_name"] = st["name"]
    rt = await db.routes.find_one({"_id": ObjectId(sched["route_id"])})
    if rt:
        sched["route_name"] = rt["name"]
        
    return sched

@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(sched_in: ScheduleCreate, current_user: dict = Depends(admin_only)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    try:
        t_oid = ObjectId(sched_in.train_id)
        r_oid = ObjectId(sched_in.route_id)
        s_oid = ObjectId(sched_in.station_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid references")
        
    # Verify existences
    t = await db.trains.find_one({"_id": t_oid})
    r = await db.routes.find_one({"_id": r_oid})
    st = await db.stations.find_one({"_id": s_oid})
    
    if not t or not r or not st:
        raise HTTPException(status_code=404, detail="One or more references not found")
        
    sched_doc = sched_in.dict()
    sched_doc["train_id"] = t_oid
    sched_doc["route_id"] = r_oid
    sched_doc["station_id"] = s_oid
    
    result = await db.schedules.insert_one(sched_doc)
    sched_doc["id"] = str(result.inserted_id)
    sched_doc["_id"] = str(result.inserted_id)
    sched_doc["train_id"] = str(t_oid)
    sched_doc["route_id"] = str(r_oid)
    sched_doc["station_id"] = str(s_oid)
    return sched_doc

@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(schedule_id: str, sched_in: ScheduleUpdate, current_user: dict = Depends(staff_only)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    try:
        oid = ObjectId(schedule_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid schedule ID")
        
    existing = await db.schedules.find_one({"_id": oid})
    if not existing:
        raise HTTPException(status_code=404, detail="Schedule not found")
        
    update_data = {k: v for k, v in sched_in.dict().items() if v is not None}
    
    # Auto-adjust status if delay is set
    if "delay_min" in update_data:
        delay = update_data["delay_min"]
        if delay > 0:
            update_data["status"] = "Delayed"
            
            # Optionally: Automatically create a system alert for delay
            alert_doc = {
                "type": "Train Delay",
                "target_type": "Train",
                "target_id": str(existing["train_id"]),
                "message": f"Train is delayed by {delay} minutes at station.",
                "level": "Warning" if delay < 15 else "Critical",
                "timestamp": datetime.utcnow(),
                "status": "Active"
            }
            await db.alerts.insert_one(alert_doc)
        elif delay == 0 and existing.get("status") == "Delayed":
            update_data["status"] = "On Time"
            
    if update_data:
        await db.schedules.update_one({"_id": oid}, {"$set": update_data})
        
    updated = await db.schedules.find_one({"_id": oid})
    updated["id"] = str(updated["_id"])
    updated["_id"] = str(updated["_id"])
    updated["train_id"] = str(updated["train_id"])
    updated["route_id"] = str(updated["route_id"])
    updated["station_id"] = str(updated["station_id"])
    
    # Broadcast schedule update
    await manager.broadcast({
        "type": "schedule_update",
        "data": updated
    })
    
    return updated

@router.delete("/{schedule_id}")
async def delete_schedule(schedule_id: str, current_user: dict = Depends(admin_only)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    try:
        oid = ObjectId(schedule_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid schedule ID")
        
    result = await db.schedules.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Schedule not found")
        
    return {"message": "Schedule deleted successfully", "id": schedule_id}

@router.post("/optimize-frequency")
async def optimize_frequency(req: OptimizeFrequencyRequest, current_user: dict = Depends(staff_only)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    try:
        r_oid = ObjectId(req.route_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid route ID")
        
    route = await db.routes.find_one({"_id": r_oid})
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
        
    # Frequency optimization algorithm based on time periods
    # Simulate a smart scheduling adjustment recommendation
    periods = [
        {"name": "Early Morning (06:00 - 08:00)", "base_headway": 8, "multiplier": 1.2, "peak": False},
        {"name": "Morning Peak (08:00 - 10:30)", "base_headway": 3, "multiplier": 0.6, "peak": True},
        {"name": "Mid-Day (10:30 - 16:30)", "base_headway": 6, "multiplier": 1.0, "peak": False},
        {"name": "Evening Peak (16:30 - 20:00)", "base_headway": 3, "multiplier": 0.5, "peak": True},
        {"name": "Late Night (20:00 - 23:00)", "base_headway": 10, "multiplier": 1.5, "peak": False}
    ]
    
    recommendations = []
    
    # Calculate how many trains are currently on the route
    train_count = await db.trains.count_documents({"route_id": r_oid, "status": "In Service"})
    
    for p in periods:
        optimized_headway = max(2, int(req.target_interval_minutes * p["multiplier"]))
        # Required trains is roughly calculated by route distance (assumed ~30km) divided by speed and interval
        # Let's say a round trip is 60 minutes.
        required_trains = max(1, 60 // optimized_headway)
        
        status_rec = "Optimal"
        deficit = required_trains - train_count
        if p["peak"] and deficit > 0:
            status_rec = f"Action Required: Deploy {deficit} extra trains"
        elif deficit < -2:
            status_rec = f"Surplus: Redundant trains ({abs(deficit)}) can stand by"
            
        recommendations.append({
            "period": p["name"],
            "current_trains": train_count,
            "recommended_headway_minutes": optimized_headway,
            "required_trains": required_trains,
            "status": status_rec,
            "is_peak": p["peak"]
        })
        
    return {
        "route_id": req.route_id,
        "route_name": route["name"],
        "recommendations": recommendations,
        "analysis_timestamp": datetime.utcnow()
    }
