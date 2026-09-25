from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any

class UserSettings(BaseModel):
    theme: str = "dark"
    language: str = "en"
    notifications: bool = True

class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: str = Field("Operator", pattern="^(Admin|Operator|Analyst)$")

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class GoogleToken(BaseModel):
    token: str
    role: str = Field("Analyst")

class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    settings: Optional[UserSettings] = None

class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)

class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    status: str
    settings: UserSettings

    class Config:
        from_attributes = True
