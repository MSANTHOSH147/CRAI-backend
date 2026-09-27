from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SensorDataCreate(BaseModel):
    mission_id: int
    sensor_type: str

    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None

    temperature: float | None = None
    min_temperature: float | None = None
    max_temperature: float | None = None

    humidity: float | None = None

    image_path: str | None = None

    device_id: str | None = None


class SensorDataResponse(SensorDataCreate):
    id: int
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)