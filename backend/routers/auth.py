from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from bson import ObjectId
from backend.config import settings
from backend.database import db_instance
from backend.auth import (
    hash_password, verify_password, create_access_token, get_current_user, RoleChecker
)

from google.oauth2 import id_token
from google.auth.transport import requests
from fastapi.concurrency import run_in_threadpool
import secrets
from backend.models.user import (
    UserRegister, UserLogin, UserResponse, UserProfileUpdate, PasswordChange,
    PasswordResetRequest, PasswordResetConfirm, GoogleToken
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserRegister):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not available")
        
    # Check if user already exists
    existing_user = await db.users.find_one({"email": user_in.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
        
    user_doc = {
        "name": user_in.name,
        "email": user_in.email,
        "password_hash": hash_password(user_in.password),
        "role": user_in.role,
        "status": "Active",
        "settings": {
            "theme": "dark",
            "language": "en",
            "notifications": True
        }
    }
    
    result = await db.users.insert_one(user_doc)
    user_doc["id"] = str(result.inserted_id)
    return user_doc

@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    role: str = Form(...)
):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not available")
        
    user = await db.users.find_one({"email": form_data.username})
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if user.get("status") != "Active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is inactive. Contact Administrator."
        )
        
    if user.get("role") != role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Selected role does not match account role."
        )
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"], "role": user["role"]},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user["_id"]),
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "settings": user.get("settings", {"theme": "dark", "language": "en", "notifications": True})
        }
    }

@router.get("/profile", response_model=UserResponse)
async def get_profile(current_user: dict = Depends(get_current_user)):
    return current_user

@router.put("/profile", response_model=UserResponse)
async def update_profile(profile_in: UserProfileUpdate, current_user: dict = Depends(get_current_user)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not available")
        
    update_data = {}
    if profile_in.name is not None:
        update_data["name"] = profile_in.name
    if profile_in.email is not None and profile_in.email != current_user["email"]:
        # Check if email is already taken
        taken = await db.users.find_one({"email": profile_in.email})
        if taken:
            raise HTTPException(status_code=400, detail="Email is already taken")
        update_data["email"] = profile_in.email
    if profile_in.settings is not None:
        update_data["settings"] = profile_in.settings.dict()
        
    if not update_data:
        return current_user
        
    await db.users.update_one(
        {"_id": ObjectId(current_user["id"])},
        {"$set": update_data}
    )
    
    updated_user = await db.users.find_one({"_id": ObjectId(current_user["id"])})
    updated_user["id"] = str(updated_user["_id"])
    return updated_user

@router.post("/change-password")
async def change_password(pass_in: PasswordChange, current_user: dict = Depends(get_current_user)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not available")
        
    if not verify_password(pass_in.old_password, current_user["password_hash"]):
        raise HTTPException(status_code=400, detail="Incorrect old password")
        
    await db.users.update_one(
        {"_id": ObjectId(current_user["id"])},
        {"$set": {"password_hash": hash_password(pass_in.new_password)}}
    )
    return {"message": "Password changed successfully"}

@router.post("/forgot-password")
async def forgot_password(req: PasswordResetRequest):
    # Mock implementation - in production this would send an email with a reset link
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not available")
        
    user = await db.users.find_one({"email": req.email})
    if not user:
        # Avoid user enumeration by returning a success message anyway
        return {"message": "If this email exists, password reset instructions have been sent."}
        
    # Return mock token for implementation convenience (the frontend can use it to reset)
    mock_token = f"reset-token-{str(user['_id'])}"
    return {
        "message": "Password reset instructions sent.",
        "debug_token": mock_token # returned for easy testing
    }

@router.post("/reset-password")
async def reset_password(req: PasswordResetConfirm):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not available")
        
    # Mock verify: token has the format reset-token-<user_id>
    if not req.token.startswith("reset-token-"):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
        
    user_id_str = req.token.replace("reset-token-", "")
    try:
        user_id = ObjectId(user_id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid token format")
        
    user = await db.users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    await db.users.update_one(
        {"_id": user_id},
        {"$set": {"password_hash": hash_password(req.new_password)}}
    )
    return {"message": "Password reset successful"}

# Admin User Management Routes
admin_only = RoleChecker(["Admin"])

@router.get("/users")
async def list_users(current_user: dict = Depends(admin_only)):
    db = db_instance.db
    if db is None:
        return []
        
    cursor = db.users.find({}, {"password_hash": 0})
    users_list = []
    async for u in cursor:
        u["id"] = str(u["_id"])
        u["_id"] = str(u["_id"])
        users_list.append(u)
    return users_list

@router.put("/users/{user_id}/status")
async def toggle_user_status(user_id: str, status_payload: dict, current_user: dict = Depends(admin_only)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID")
        
    new_status = status_payload.get("status")
    if new_status not in ["Active", "Inactive"]:
        raise HTTPException(status_code=400, detail="Invalid status. Must be Active or Inactive")
        
    await db.users.update_one({"_id": oid}, {"$set": {"status": new_status}})
    return {"message": f"User status set to {new_status}"}

@router.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(admin_only)):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")
        
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID")
        
    # Prevent admin from deleting themselves
    if str(oid) == current_user["id"]:
        raise HTTPException(status_code=400, detail="Admin cannot delete their own account")
        
    result = await db.users.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
        
    return {"message": "User deleted successfully", "id": user_id}



@router.post("/google")
async def google_login(token_data: GoogleToken):
    db = db_instance.db
    if db is None:
        raise HTTPException(status_code=500, detail="Database is not available")
        
    try:
        client_id = settings.GOOGLE_CLIENT_ID
        
        idinfo = await run_in_threadpool(
            id_token.verify_oauth2_token,
            token_data.token, 
            requests.Request(), 
            client_id,
            clock_skew_in_seconds=60
        )
        
        email = idinfo['email']
        name = idinfo.get('name', 'Google User')
        
        user = await db.users.find_one({"email": email})
        
        if not user:
            user_doc = {
                "email": email,
                "name": name,
                "role": token_data.role,
                "status": "Active",
                "password_hash": hash_password(secrets.token_urlsafe(32)),
                "settings": {
                    "theme": "dark",
                    "language": "en",
                    "notifications": True
                }
            }
            result = await db.users.insert_one(user_doc)
            user = await db.users.find_one({"_id": result.inserted_id})
            
        if user.get("status") != "Active":
            raise HTTPException(status_code=400, detail="Account is inactive. Contact Administrator.")
            
        if user.get("role") != token_data.role:
            # User wants to switch roles, update their role in the database
            await db.users.update_one({"_id": user["_id"]}, {"$set": {"role": token_data.role}})
            user["role"] = token_data.role
            
        user["id"] = str(user["_id"])
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["email"], "role": user["role"]}, expires_delta=access_token_expires
        )
        
        return {"access_token": access_token, "token_type": "bearer", "user": UserResponse(**user)}
        
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {str(e)}")
