from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class AlertCreate(BaseModel):
    type: str = Field(..., pattern="^(Overcrowding|Train Delay|Platform Congestion|Emergency)$")
    target_type: str = Field(..., pattern="^(Station|Train|Platform)$")
    target_id: str = Field(..., description="ID reference of the station, train or schedule")
    message: str = Field(..., min_length=5, max_length=250)
    level: str = Field("Info", pattern="^(Info|Warning|Critical)$")

class AlertUpdate(BaseModel):
    status: str = Field(..., pattern="^(Active|Resolved)$")
    resolution_notes: Optional[str] = None

class AlertResponse(BaseModel):
    id: str
    type: str
    target_type: str
    target_id: str
    target_name: Optional[str] = None  # Helper to display station name or train number
    message: str
    level: str
    timestamp: datetime
    status: str
    resolution_notes: Optional[str] = None

    class Config:
        from_attributes = True
        populate_by_name = True
