from pydantic import BaseModel, ConfigDict


class FarmBase(BaseModel):
    farm_code: str
    name: str
    crop: str
    area_acres: float
    latitude: float
    longitude: float


class FarmCreate(FarmBase):
    pass


class FarmResponse(FarmBase):
    id: int
    health_score: float
    risk_level: str

    model_config = ConfigDict(from_attributes=True)