from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class FarmEventResponse(BaseModel):
    event_id: str
    farm_id: Optional[int]
    zone_id: str
    device_id: Optional[str]
    status: str
    started_at: datetime
    detected_at: datetime
    resolved_at: Optional[datetime]
    crop: Optional[str]
    crop_stage: Optional[str]
    risk_level: Optional[str]
    risk_score: Optional[float]
    decision: Optional[Dict[str, Any]]
    action: Optional[str]
    before_state: Optional[Dict[str, Any]]
    during_state: Optional[Dict[str, Any]]
    after_state: Optional[Dict[str, Any]]
    evidence_sources: Optional[List[str]]
    image_references: Optional[List[Dict[str, Any]]]
    sensor_references: Optional[List[Dict[str, Any]]]
    temporal_context: Optional[Dict[str, Any]]
    spatial_context: Optional[Dict[str, Any]]
    evidence_package: Optional[Dict[str, Any]]
    integrity_hash: Optional[str]
    created_at: datetime
    updated_at: datetime


class EvidenceVerifyResponse(BaseModel):
    event_id: str
    valid: bool
    stored_hash: Optional[str]
    computed_hash: Optional[str]
    reason: str
