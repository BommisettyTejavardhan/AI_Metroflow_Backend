from fastapi import APIRouter, Depends
from backend.database import db_instance
from backend.auth import get_current_user
import random

router = APIRouter(prefix="/api/heatmap", tags=["Heatmap"])

@router.get("")
async def get_heatmap_data(current_user: dict = Depends(get_current_user)):
    db = db_instance.db
    if db is None:
        return {"data": []}
        
    cursor = db.stations.find({})
    heatmap_data = []
    
    async for s in cursor:
        # Fetch latest crowd log or simulate
        last_crowd = await db.crowd_data.find_one({"station_id": s["_id"]}, sort=[("timestamp", -1)])
        density = last_crowd.get("crowd_percentage", random.randint(20, 95)) if last_crowd else random.randint(20, 95)
        
        # Determine color/intensity based on density
        if density < 40:
            intensity = 0.3
            color = "Green"
        elif density < 70:
            intensity = 0.6
            color = "Yellow"
        elif density < 88:
            intensity = 0.8
            color = "Orange"
        else:
            intensity = 1.0
            color = "Red"
            
        heatmap_data.append({
            "station_id": str(s["_id"]),
            "station_name": s["name"],
            "lat": s.get("latitude", 28.6139),
            "lng": s.get("longitude", 77.2090),
            "line": s.get("line", "Unknown"),
            "line_color": s.get("line_color", "#6366f1"),
            "density": density,
            "intensity": intensity,
            "color": color
        })
        
    return {"data": heatmap_data}
