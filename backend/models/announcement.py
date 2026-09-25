from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class AnnouncementCreate(BaseModel):
    title: str = Field(..., description="Short title for the announcement")
    message: str = Field(..., description="Detailed announcement message")
    type: str = Field(..., description="Type (e.g., Emergency, Platform Change, Delay Notice, Maintenance, Weather Warning)")
    priority: str = Field("Normal", description="Priority (Normal, High, Critical)")
    target_station: Optional[str] = Field(None, description="Specific station ID or name, or None for system-wide")
    target_route: Optional[str] = Field(None, description="Specific route ID or name, or None for system-wide")
    expiry_date: Optional[datetime] = Field(None, description="When the announcement expires and should no longer be shown")

class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    type: Optional[str] = None
    priority: Optional[str] = None
    expiry_date: Optional[datetime] = None

class AnnouncementResponse(BaseModel):
    id: str
    title: str
    message: str
    type: str
    priority: str
    target_station: Optional[str]
    target_route: Optional[str]
    created_date: datetime
    expiry_date: Optional[datetime]
    created_by: str

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
