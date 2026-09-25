from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class CrowdDataCreate(BaseModel):
    station_id: str
    passenger_count: int
    inflow: int
    outflow: int
    waiting_passengers: int
    crowd_percentage: int
    crowd_level: str  # Green, Yellow, Orange, Red

class CrowdResponse(BaseModel):
    id: str
    station_id: str
    station_name: Optional[str] = None
    station_code: Optional[str] = None
    line: Optional[str] = None
    timestamp: datetime
    passenger_count: int
    inflow: int
    outflow: int
    waiting_passengers: int
    crowd_level: str  # Green, Yellow, Orange, Red
    crowd_percentage: int

    class Config:
        from_attributes = True
        populate_by_name = True

class HeatmapNode(BaseModel):
    latitude: float
    longitude: float
    intensity: float
    station_name: str
    crowd_level: str

class StationCrowdSummary(BaseModel):
    station_id: str
    name: str
    line: str
    latitude: float
    longitude: float
    passenger_count: int
    crowd_level: str
    crowd_percentage: int
    inflow: int
    outflow: int
    waiting_passengers: int
