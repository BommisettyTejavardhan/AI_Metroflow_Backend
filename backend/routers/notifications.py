from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from backend.database import db_instance
from backend.auth import get_current_user, RoleChecker
from backend.models.notification import NotificationCreate, NotificationResponse
from backend.routers.crowd import manager

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])
admin_only = RoleChecker(["Admin"])

@router.get("", response_model=dict)
async def list_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    db = db_instance.db
    if db is None:
        return {"data": [], "total": 0}
        
    # Get notifications targeting this user or broadcast (user_id = None)
    query = {
        "$or": [
            {"user_id": str(current_user["_id"])},
            {"user_id": None}
        ]
    }
    
    total = await db.notifications.count_documents(query)
    skip = (page - 1) * limit
    
    cursor = db.notifications.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    notifications_list = []
    
    async for n in cursor:
        n["id"] = str(n["_id"])
        n["_id"] = str(n["_id"])
        notifications_list.append(n)
        
    return {
        "data": notifications_list,
        "total": total,
        "page": page,
        "limit": limit
    }

@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(notif_in: NotificationCreate, current_user: dict = Depends(admin_only)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    notif_doc = notif_in.dict()
    notif_doc["timestamp"] = datetime.utcnow()
    notif_doc["is_read"] = False
    
    result = await db.notifications.insert_one(notif_doc)
    notif_doc["id"] = str(result.inserted_id)
    notif_doc["_id"] = str(result.inserted_id)
    
    # Broadcast to connected clients
    await manager.broadcast({
        "type": "new_notification",
        "data": {
            "id": notif_doc["id"],
            "title": notif_doc["title"],
            "message": notif_doc["message"],
            "type": notif_doc["type"],
            "level": notif_doc["level"],
            "timestamp": notif_doc["timestamp"].isoformat()
        }
    })
    
    return notif_doc

@router.put("/{notif_id}/read")
async def mark_notification_read(notif_id: str, current_user: dict = Depends(get_current_user)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    try:
        oid = ObjectId(notif_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")
        
    result = await db.notifications.update_one(
        {"_id": oid},
        {"$set": {"is_read": True}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found or already read")
        
    return {"message": "Notification marked as read", "id": notif_id}

@router.delete("/{notif_id}")
async def delete_notification(notif_id: str, current_user: dict = Depends(get_current_user)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    try:
        oid = ObjectId(notif_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")
        
    result = await db.notifications.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
        
    return {"message": "Notification deleted successfully"}
