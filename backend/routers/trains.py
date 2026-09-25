from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from bson import ObjectId
from backend.database import db_instance
from backend.auth import RoleChecker
from backend.models.train import TrainCreate, TrainUpdate, TrainResponse

router = APIRouter(prefix="/api/trains", tags=["Trains"])

admin_only = RoleChecker(["Admin"])
staff_only = RoleChecker(["Admin", "Operator"])

@router.get("", response_model=dict)
async def list_trains(
    route_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Search by train number or name"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100)
):
    db = db_instance.db
    if db is None:
        return {"data": [], "total": 0}
        
    query = {}
    if route_id:
        try:
            query["route_id"] = ObjectId(route_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid route ID format")
            
    if status:
        query["status"] = status
        
    if search:
        query["$or"] = [
            {"train_number": {"$regex": search, "$options": "i"}},
            {"train_name": {"$regex": search, "$options": "i"}}
        ]
        
    total = await db.trains.count_documents(query)
    skip = (page - 1) * limit
    
    cursor = db.trains.find(query).skip(skip).limit(limit)
    trains_list = []
    
    async for t in cursor:
        t["id"] = str(t["_id"])
        t["_id"] = str(t["_id"])
        t["route_id"] = str(t["route_id"])
        trains_list.append(t)
        
    # Join with routes to add route name
    for train in trains_list:
        try:
            route = await db.routes.find_one({"_id": ObjectId(train["route_id"])})
            if route:
                train["route_name"] = route["name"]
        except Exception:
            pass
            
    return {
        "data": trains_list,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }

@router.get("/{train_id}", response_model=TrainResponse)
async def get_train(train_id: str):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    try:
        oid = ObjectId(train_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid train ID format")
        
    train = await db.trains.find_one({"_id": oid})
    if not train:
        raise HTTPException(status_code=404, detail="Train not found")
        
    train["id"] = str(train["_id"])
    train["_id"] = str(train["_id"])
    train["route_id"] = str(train["route_id"])
    return train

@router.post("", response_model=TrainResponse, status_code=status.HTTP_201_CREATED)
async def create_train(train_in: TrainCreate, current_user: dict = Depends(admin_only)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    # Check duplicate train number
    existing = await db.trains.find_one({"train_number": train_in.train_number})
    if existing:
        raise HTTPException(status_code=400, detail="Train number already exists")
        
    # Verify route exists
    try:
        r_oid = ObjectId(train_in.route_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid route ID format")
        
    route = await db.routes.find_one({"_id": r_oid})
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
        
    train_doc = train_in.dict()
    train_doc["route_id"] = r_oid
    
    result = await db.trains.insert_one(train_doc)
    train_doc["id"] = str(result.inserted_id)
    train_doc["_id"] = str(result.inserted_id)
    train_doc["route_id"] = str(train_doc["route_id"])
    return train_doc

@router.put("/{train_id}", response_model=TrainResponse)
async def update_train(train_id: str, train_in: TrainUpdate, current_user: dict = Depends(staff_only)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    try:
        oid = ObjectId(train_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid train ID format")
        
    existing = await db.trains.find_one({"_id": oid})
    if not existing:
        raise HTTPException(status_code=404, detail="Train not found")
        
    update_data = {k: v for k, v in train_in.dict().items() if v is not None}
    
    if "route_id" in update_data:
        try:
            update_data["route_id"] = ObjectId(update_data["route_id"])
            # Verify route exists
            route = await db.routes.find_one({"_id": update_data["route_id"]})
            if not route:
                raise HTTPException(status_code=404, detail="Route not found")
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid route ID format")
            
    if update_data:
        await db.trains.update_one({"_id": oid}, {"$set": update_data})
        
    updated = await db.trains.find_one({"_id": oid})
    updated["id"] = str(updated["_id"])
    updated["_id"] = str(updated["_id"])
    updated["route_id"] = str(updated["route_id"])
    return updated

@router.delete("/{train_id}")
async def delete_train(train_id: str, current_user: dict = Depends(admin_only)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    try:
        oid = ObjectId(train_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid train ID format")
        
    result = await db.trains.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Train not found")
        
    # Also delete associated schedules
    await db.schedules.delete_many({"train_id": oid})
    
    return {"message": "Train and its schedules deleted successfully", "id": train_id}
