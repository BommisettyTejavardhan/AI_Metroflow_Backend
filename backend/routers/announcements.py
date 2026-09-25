from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from backend.database import db_instance
from backend.auth import get_current_user, RoleChecker
from backend.models.announcement import AnnouncementCreate, AnnouncementUpdate, AnnouncementResponse
from backend.routers.crowd import manager

router = APIRouter(prefix="/api/announcements", tags=["Announcements"])

admin_only = RoleChecker(["Admin"])

@router.get("", response_model=dict)
async def list_announcements(
    active_only: bool = Query(True, description="Only fetch announcements that have not expired"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    db = db_instance.db
    if db is None:
        return {"data": [], "total": 0}
        
    query = {}
    if active_only:
        query["$or"] = [
            {"expiry_date": None},
            {"expiry_date": {"$gt": datetime.utcnow()}}
        ]
        
    total = await db.announcements.count_documents(query)
    skip = (page - 1) * limit
    
    cursor = db.announcements.find(query).sort("created_date", -1).skip(skip).limit(limit)
    announcements_list = []
    
    async for a in cursor:
        a["id"] = str(a["_id"])
        a["_id"] = str(a["_id"])
        announcements_list.append(a)
        
    return {
        "data": announcements_list,
        "total": total,
        "page": page,
        "limit": limit
    }

@router.post("", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
async def create_announcement(ann_in: AnnouncementCreate, current_user: dict = Depends(admin_only)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    ann_doc = ann_in.dict()
    if ann_doc.get("expiry_date"):
        # Motor requires naive datetimes. Pydantic parses ISO strings with 'Z' as tz-aware.
        ann_doc["expiry_date"] = ann_doc["expiry_date"].replace(tzinfo=None)
        
    ann_doc["created_date"] = datetime.utcnow()
    ann_doc["created_by"] = current_user["email"]
    
    result = await db.announcements.insert_one(ann_doc)
    ann_doc["id"] = str(result.inserted_id)
    ann_doc["_id"] = str(result.inserted_id)
    
    # Broadcast to all connected clients immediately
    await manager.broadcast({
        "type": "emergency_announcement",
        "data": {
            "id": ann_doc["id"],
            "title": ann_doc["title"],
            "message": ann_doc["message"],
            "priority": ann_doc["priority"],
            "type": ann_doc["type"]
        }
    })
    
    return ann_doc

@router.put("/{ann_id}", response_model=AnnouncementResponse)
async def update_announcement(ann_id: str, ann_in: AnnouncementUpdate, current_user: dict = Depends(admin_only)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    try:
        oid = ObjectId(ann_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")
        
    update_data = {k: v for k, v in ann_in.dict().items() if v is not None}
    
    if update_data.get("expiry_date"):
        update_data["expiry_date"] = update_data["expiry_date"].replace(tzinfo=None)
        
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
        
    result = await db.announcements.update_one(
        {"_id": oid},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
        
    updated = await db.announcements.find_one({"_id": oid})
    updated["id"] = str(updated["_id"])
    updated["_id"] = str(updated["_id"])
    return updated

@router.delete("/{ann_id}")
async def delete_announcement(ann_id: str, current_user: dict = Depends(admin_only)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    try:
        oid = ObjectId(ann_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID")
        
    result = await db.announcements.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
        
    return {"message": "Announcement deleted successfully"}
