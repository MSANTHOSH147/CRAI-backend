from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SensorAcquisitionRequestCreate(BaseModel):
    farm_id: Optional[int] = None
    zone_id: Optional[str] = None
    device_id: Optional[str] = None

    requested_evidence: str = "FRESH_SENSOR"
    source: str = "ESP32"

    reason: Optional[str] = None
    priority: str = "MEDIUM"


class SensorAcquisitionRequestResponse(
    SensorAcquisitionRequestCreate
):
    request_id: str
    status: str

    created_at: datetime
    claimed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    fulfilled_reading_id: Optional[str] = None