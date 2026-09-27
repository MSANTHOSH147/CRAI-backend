
from typing import Optional

from pydantic import BaseModel, Field


class VisualEvidenceMetadata(BaseModel):

    farm_id: Optional[int] = None
    zone_id: Optional[str] = None
    event_id: Optional[str] = None

    source: str = Field(
        ...,
        description="PHONE or UAV"
    )

    phase: str = Field(
        ...,
        description="BEFORE, DURING or AFTER"
    )

    capture_mode: str = Field(
        ...,
        description="ROUTINE, TARGETED_INSPECTION, EVENT_EVIDENCE or FIELD_SCAN"
    )

    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None

    sequence: Optional[int] = None

    parent_observation_id: Optional[str] = None

    quality_score: Optional[float] = None
    quality_status: Optional[str] = None

    visual_confidence: Optional[float] = None


class VisualEvidenceResponse(BaseModel):

    image_id: str
    farm_id: Optional[int] = None
    zone_id: Optional[str] = None
    event_id: Optional[str] = None

    source: str
    scale: str
    phase: str
    capture_mode: str

    filename: str
    stored_path: str

    timestamp: str

    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None

    sequence: Optional[int] = None
    parent_observation_id: Optional[str] = None

    quality_score: Optional[float] = None
    quality_status: Optional[str] = None

    visual_confidence: Optional[float] = None

    integrity: dict
