from pydantic import BaseModel, Field
from typing import Optional

class TrainCreate(BaseModel):
    train_number: str = Field(..., pattern="^[A-Z0-9-]{3,15}$")
    train_name: str = Field(..., min_length=2, max_length=100)
    route_id: str = Field(..., description="MongoDB ObjectId reference as string")
    capacity: int = Field(1200, ge=100)
    current_occupancy: int = Field(0, ge=0)
    status: str = Field("Standing By", pattern="^(In Service|Standing By|Out of Service|Maintenance)$")
    arrival_time: str = Field("06:00", pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    departure_time: str = Field("23:00", pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")

class TrainUpdate(BaseModel):
    train_name: Optional[str] = None
    route_id: Optional[str] = None
    capacity: Optional[int] = None
    current_occupancy: Optional[int] = None
    status: Optional[str] = None
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None

class TrainResponse(BaseModel):
    id: str
    train_number: str
    train_name: str
    route_id: str
    capacity: int
    current_occupancy: int
    status: str
    arrival_time: str
    departure_time: str

    class Config:
        from_attributes = True
        populate_by_name = True
