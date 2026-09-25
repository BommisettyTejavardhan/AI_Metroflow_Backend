from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from bson import ObjectId
import os
import pandas as pd
from backend.database import db_instance
from backend.auth import RoleChecker
from backend.models.station import StationCreate, StationUpdate, StationResponse

router = APIRouter(prefix="/api/stations", tags=["Stations"])

# Access control lists
admin_only = RoleChecker(["Admin"])
staff_only = RoleChecker(["Admin", "Operator"])

# ─── Network map CSV cache ────────────────────────────────────────────────────
_NETWORK_MAP_CACHE = None

LINE_COLORS_MAP = {
    "Red line":          "#ef4444",
    "Yellow line":       "#eab308",
    "Blue line":         "#3b82f6",
    "Pink line":         "#ec4899",
    "Magenta line":      "#d946ef",
    "Voilet line":       "#8b5cf6",
    "Violet line":       "#8b5cf6",
    "Green line":        "#22c55e",
    "Green line branch": "#16a34a",
    "Aqua line":         "#06b6d4",
    "Rapid Metro":       "#64748b",
    "Gray line":         "#9ca3af",
    "Orange line":       "#f97316",
    "Blue line branch":  "#60a5fa",
}

def _load_network_map():
    global _NETWORK_MAP_CACHE
    if _NETWORK_MAP_CACHE is not None:
        return _NETWORK_MAP_CACHE
    csv_path = "datasets/Delhi-Metro-Network.csv"
    if not os.path.exists(csv_path):
        _NETWORK_MAP_CACHE = []
        return _NETWORK_MAP_CACHE
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    df['Station Name'] = df['Station Name'].str.strip()
    df['Line'] = df['Line'].str.strip()
    stations = []
    for _, row in df.iterrows():
        name = str(row['Station Name']).split('[')[0].strip()
        line = str(row['Line'])
        stations.append({
            "id": int(row['Station ID']),
            "name": name,
            "full_name": str(row['Station Name']),
            "line": line,
            "line_color": LINE_COLORS_MAP.get(line, "#6366f1"),
            "latitude": float(row['Latitude']),
            "longitude": float(row['Longitude']),
            "distance_from_start_km": float(row['Distance from Start (km)']),
            "station_layout": str(row['Station Layout']),
            "opening_date": str(row['Opening Date']),
        })
    _NETWORK_MAP_CACHE = stations
    return stations


@router.get("/network-map")
async def get_network_map():
    """
    Return all real Delhi Metro station coordinates from MongoDB.
    No authentication required — public map data.
    Used by LeafletMap to render accurate real-coordinate station markers.
    """
    db = db_instance.db
    if db is None:
        return {"stations": [], "count": 0}
        
    stations = await db.stations.find({}).to_list(length=None)
    
    mapped_stations = []
    for s in stations:
        mapped_stations.append({
            "id": str(s["_id"]),
            "name": s["name"],
            "full_name": s.get("full_name", s["name"]),
            "line": s["line"],
            "line_color": s.get("line_color", "#6366f1"),
            "latitude": s["latitude"],
            "longitude": s["longitude"],
            "distance_from_start_km": s.get("distance_from_start_km", 0),
            "station_layout": s.get("station_layout", "Unknown"),
            "opening_date": s.get("opening_date", "")
        })
        
    return {"stations": mapped_stations, "count": len(mapped_stations)}



@router.get("", response_model=dict)
async def list_stations(
    search: Optional[str] = Query(None, description="Search by station name or code"),
    line: Optional[str] = Query(None, description="Filter by Metro Line"),
    zone: Optional[str] = Query(None, description="Filter by Zone"),
    status: Optional[str] = Query(None, description="Filter by Status"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100)
):
    db = db_instance.db
    if db is None:
        return {"data": [], "total": 0, "page": page, "limit": limit}
        
    query = {}
    
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"station_code": {"$regex": search, "$options": "i"}}
        ]
    if line:
        query["line"] = line
    if zone:
        query["zone"] = zone
    if status:
        query["status"] = status
        
    total = await db.stations.count_documents(query)
    
    skip = (page - 1) * limit
    cursor = db.stations.find(query).skip(skip).limit(limit)
    stations_list = []
    
    async for s in cursor:
        s["id"] = str(s["_id"])
        s["_id"] = str(s["_id"])
        stations_list.append(s)
        
    return {
        "data": stations_list,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }

@router.get("/{station_id}", response_model=StationResponse)
async def get_station(station_id: str):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    try:
        oid = ObjectId(station_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid station ID format")
        
    station = await db.stations.find_one({"_id": oid})
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
        
    station["id"] = str(station["_id"])
    station["_id"] = str(station["_id"])
    return station

@router.post("", response_model=StationResponse, status_code=status.HTTP_201_CREATED)
async def create_station(station_in: StationCreate, current_user: dict = Depends(admin_only)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    # Check if station code already exists
    existing = await db.stations.find_one({"station_code": station_in.station_code})
    if existing:
        raise HTTPException(status_code=400, detail="Station code already exists")
        
    station_doc = station_in.dict()
    result = await db.stations.insert_one(station_doc)
    station_doc["id"] = str(result.inserted_id)
    station_doc["_id"] = str(result.inserted_id)
    return station_doc

@router.put("/{station_id}", response_model=StationResponse)
async def update_station(station_id: str, station_in: StationUpdate, current_user: dict = Depends(staff_only)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    try:
        oid = ObjectId(station_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid station ID format")
        
    existing = await db.stations.find_one({"_id": oid})
    if not existing:
        raise HTTPException(status_code=404, detail="Station not found")
        
    update_data = {k: v for k, v in station_in.dict().items() if v is not None}
    if update_data:
        await db.stations.update_one({"_id": oid}, {"$set": update_data})
        
    updated = await db.stations.find_one({"_id": oid})
    updated["id"] = str(updated["_id"])
    updated["_id"] = str(updated["_id"])
    return updated

@router.delete("/{station_id}")
async def delete_station(station_id: str, current_user: dict = Depends(admin_only)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    try:
        oid = ObjectId(station_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid station ID format")
        
    result = await db.stations.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Station not found")
        
    return {"message": "Station deleted successfully", "id": station_id}
