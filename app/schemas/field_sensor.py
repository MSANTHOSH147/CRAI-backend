from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class FieldSensorReadingCreate(BaseModel):
    device_id: str = Field(min_length=1, max_length=100)

    farm_id: Optional[int] = None
    zone_id: Optional[str] = Field(default=None, max_length=50)

    source: Literal[
        "REAL",
        "SIMULATED",
        "ESTIMATED",
        "USER_ENTERED",
    ] = "REAL"

    soil_moisture: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
    )

    temperature: Optional[float] = Field(
        default=None,
        ge=-20,
        le=80,
    )

    humidity: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
    )

    # Production-capable optional field evidence. These fields are
    # backward compatible with the original CRAI sensor payload.
    soil_temperature: Optional[float] = Field(default=None, ge=-20, le=80)
    soil_ph: Optional[float] = Field(default=None, ge=0, le=14)
    soil_ec: Optional[float] = Field(default=None, ge=0)
    leaf_wetness: Optional[float] = Field(default=None, ge=0, le=100)

    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    altitude: Optional[float] = None
    battery: Optional[float] = Field(default=None, ge=0, le=100)
    signal_strength: Optional[float] = None
    gateway_id: Optional[str] = Field(default=None, max_length=100)
    sequence_number: Optional[int] = Field(default=None, ge=0)

    timestamp: Optional[datetime] = None


class FieldSensorReadingResponse(BaseModel):
    reading_id: str
    status: str
    device_id: str

    farm_id: Optional[int]
    zone_id: Optional[str]

    source: str

    soil_moisture: Optional[float]
    temperature: Optional[float]
    humidity: Optional[float]
    soil_temperature: Optional[float] = None
    soil_ph: Optional[float] = None
    soil_ec: Optional[float] = None
    leaf_wetness: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    battery: Optional[float] = None
    signal_strength: Optional[float] = None
    gateway_id: Optional[str] = None
    sequence_number: Optional[int] = None

    timestamp: datetime

    adaptive_acquisition: Optional[Dict[str, Any]] = None
