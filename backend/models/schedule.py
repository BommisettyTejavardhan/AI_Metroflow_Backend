from pydantic import BaseModel, Field
from typing import Optional

class ScheduleCreate(BaseModel):
    train_id: str = Field(..., description="Train ObjectId reference")
    route_id: str = Field(..., description="Route ObjectId reference")
    station_id: str = Field(..., description="Station ObjectId reference")
    platform: int = Field(1, ge=1)
    scheduled_arrival: str = Field(..., pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    scheduled_departure: str = Field(..., pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    actual_arrival: Optional[str] = None
    actual_departure: Optional[str] = None
    delay_min: int = Field(0)
    status: str = Field("On Time", pattern="^(On Time|Delayed|Cancelled|Completed)$")

class ScheduleUpdate(BaseModel):
    platform: Optional[int] = None
    scheduled_arrival: Optional[str] = None
    scheduled_departure: Optional[str] = None
    actual_arrival: Optional[str] = None
    actual_departure: Optional[str] = None
    delay_min: Optional[int] = None
    status: Optional[str] = None

class ScheduleResponse(BaseModel):
    id: str
    train_id: str
    route_id: str
    station_id: str
    platform: int
    scheduled_arrival: str
    scheduled_departure: str
    actual_arrival: Optional[str]
    actual_departure: Optional[str]
    delay_min: int
    status: str

    # Joined fields for convenience in lists
    train_number: Optional[str] = None
    train_name: Optional[str] = None
    station_name: Optional[str] = None
    route_name: Optional[str] = None

    class Config:
        from_attributes = True
        populate_by_name = True
        arbitrary_types_allowed = True
class OptimizeFrequencyRequest(BaseModel):
    route_id: str
    target_interval_minutes: int = Field(5, ge=2, le=30)
    peak_factor: float = Field(1.5, ge=1.0, le=3.0)
