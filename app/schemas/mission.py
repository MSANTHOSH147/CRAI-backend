from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MissionBase(BaseModel):
    mission_code: str
    farm_id: int


class MissionCreate(MissionBase):
    pass


class MissionResponse(MissionBase):
    id: int
    status: str
    battery: float
    altitude: float
    coverage: float
    start_time: datetime | None
    end_time: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MissionStatusUpdate(BaseModel):
    status: str