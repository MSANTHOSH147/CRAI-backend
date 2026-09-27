from typing import Optional
from pydantic import BaseModel, Field


class ObservationCreateRequest(BaseModel):
    farm_id: str
    zone_id: str
    source: str
    scale: str
    capture_mode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timestamp: Optional[str] = None
    event_id: Optional[str] = None
    parent_observation_id: Optional[str] = None
    observation_id: Optional[str] = None
    status: str = "PENDING"


class ObservationAssociateRequest(BaseModel):
    event_id: Optional[str] = None
    image_id: Optional[str] = None
    sensor_id: Optional[str] = None


class ObservationQueueRequest(BaseModel):
    file_reference: Optional[str] = None
