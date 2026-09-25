from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from backend.database import db_instance
from backend.auth import RoleChecker
from backend.models.alert import AlertCreate, AlertUpdate, AlertResponse
from backend.routers.crowd import manager

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])

admin_only = RoleChecker(["Admin"])
staff_only = RoleChecker(["Admin", "Operator"])

@router.get("", response_model=dict)
async def list_alerts(
    status: Optional[str] = Query(None, description="Filter by status (Active, Resolved)"),
    level: Optional[str] = Query(None, description="Filter by severity level (Info, Warning, Critical)"),
    type: Optional[str] = Query(None, description="Filter by type (Overcrowding, Train Delay, etc.)"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    db = db_instance.db
    if db is None:
        return {"data": [], "total": 0}
        
    query = {}
    if status:
        query["status"] = status
    if level:
        query["level"] = level
    if type:
        query["type"] = type
        
    total = await db.alerts.count_documents(query)
    skip = (page - 1) * limit
    
    cursor = db.alerts.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    alerts_list = []
    
    async for a in cursor:
        a["id"] = str(a["_id"])
        a["_id"] = str(a["_id"])
        alerts_list.append(a)
        
    # Populate referenced names
    for a in alerts_list:
        try:
            if a["target_type"] == "Station":
                st = await db.stations.find_one({"_id": ObjectId(a["target_id"])})
                if st:
                    a["target_name"] = st["name"]
            elif a["target_type"] == "Train":
                t = await db.trains.find_one({"_id": ObjectId(a["target_id"])})
                if t:
                    a["target_name"] = t["train_number"]
        except Exception:
            pass
            
    return {
        "data": alerts_list,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }

@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: str):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    try:
        oid = ObjectId(alert_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid alert ID")
        
    alert = await db.alerts.find_one({"_id": oid})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    alert["id"] = str(alert["_id"])
    alert["_id"] = str(alert["_id"])
    
    try:
        if alert["target_type"] == "Station":
            st = await db.stations.find_one({"_id": ObjectId(alert["target_id"])})
            if st:
                alert["target_name"] = st["name"]
        elif alert["target_type"] == "Train":
            t = await db.trains.find_one({"_id": ObjectId(alert["target_id"])})
            if t:
                alert["target_name"] = t["train_number"]
    except Exception:
        pass
        
    return alert

@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(alert_in: AlertCreate, current_user: dict = Depends(staff_only)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    alert_doc = alert_in.dict()
    alert_doc["timestamp"] = datetime.utcnow()
    alert_doc["status"] = "Active"
    alert_doc["resolution_notes"] = None
    
    result = await db.alerts.insert_one(alert_doc)
    alert_doc["id"] = str(result.inserted_id)
    alert_doc["_id"] = str(result.inserted_id)
    
    # Broadcast the new alert immediately via WebSockets
    await manager.broadcast({
        "type": "new_alert",
        "data": {
            "id": alert_doc["id"],
            "type": alert_doc["type"],
            "message": alert_doc["message"],
            "level": alert_doc["level"],
            "timestamp": alert_doc["timestamp"].isoformat(),
            "status": alert_doc["status"]
        }
    })
    
    return alert_doc

@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(alert_id: str, alert_in: AlertUpdate, current_user: dict = Depends(staff_only)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    try:
        oid = ObjectId(alert_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid alert ID")
        
    existing = await db.alerts.find_one({"_id": oid})
    if not existing:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    await db.alerts.update_one(
        {"_id": oid},
        {"$set": {
            "status": alert_in.status,
            "resolution_notes": alert_in.resolution_notes
        }}
    )
    
    updated = await db.alerts.find_one({"_id": oid})
    updated["id"] = str(updated["_id"])
    updated["_id"] = str(updated["_id"])
    return updated

@router.delete("/{alert_id}")
async def delete_alert(alert_id: str, current_user: dict = Depends(admin_only)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    try:
        oid = ObjectId(alert_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid alert ID")
        
    result = await db.alerts.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    return {"message": "Alert deleted successfully", "id": alert_id}
