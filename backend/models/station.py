from pydantic import BaseModel, Field
from typing import List, Optional

class StationCreate(BaseModel):
    station_code: str = Field(..., pattern="^[A-Z0-9-]{3,10}$")
    name: str = Field(..., min_length=2, max_length=100)
    line: str = Field(..., min_length=2, max_length=50)
    zone: str = Field("Delhi NCR", min_length=2, max_length=50)
    platforms: List[int] = Field(default=[1, 2])
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    status: str = Field("Active", pattern="^(Active|Inactive|Under Maintenance)$")

class StationUpdate(BaseModel):
    name: Optional[str] = None
    line: Optional[str] = None
    zone: Optional[str] = None
    platforms: Optional[List[int]] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    status: Optional[str] = None

class StationResponse(BaseModel):
    id: str
    station_code: str
    name: str
    line: str
    zone: str
    platforms: List[int]
    latitude: float
    longitude: float
    status: str

    class Config:
        from_attributes = True
        populate_by_name = True
