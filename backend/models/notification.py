from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class NotificationCreate(BaseModel):
    title: str = Field(..., description="Short title for the notification")
    message: str = Field(..., description="Detailed notification message")
    type: str = Field(..., description="Type (e.g., Crowd Alert, Delay Notification, Schedule Update, Emergency Alert)")
    level: str = Field("Info", description="Severity level (Info, Warning, Critical)")
    user_id: Optional[str] = Field(None, description="Target specific user (None for broadcast to all)")

class NotificationResponse(BaseModel):
    id: str
    title: str
    message: str
    type: str
    level: str
    is_read: bool
    user_id: Optional[str]
    timestamp: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
