from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


SimulatorScenario = Literal[
    "NORMAL",
    "DEVELOPING_STRESS",
    "DISEASE_RISK",
    "SEVERE_EVENT",
    "RECOVERY",
]


class SimulatorConfig(BaseModel):
    device_id: str = Field(default="CRAI-SIM-001", min_length=1, max_length=100)
    farm_id: Optional[int] = None
    zone_id: str = Field(default="A1", min_length=1, max_length=50)
    scenario: SimulatorScenario = "NORMAL"
    interval: float = Field(default=15.0, ge=0.1, le=3600.0)
    seed: int = 42


class SimulatorScenarioRequest(SimulatorConfig):
    reset_step: bool = True


class SimulatorStepRequest(BaseModel):
    device_id: Optional[str] = None
    farm_id: Optional[int] = None
    zone_id: Optional[str] = None
    steps: int = Field(default=1, ge=1, le=100)


class SimulatorEvaluationRequest(BaseModel):
    device_id: str = Field(default="CRAI-SIM-001", min_length=1, max_length=100)
    farm_id: Optional[int] = None
    zone_id: str = Field(default="A1", min_length=1, max_length=50)
    prediction: str = Field(min_length=1, max_length=150)
    confidence: float = Field(ge=0.0, le=100.0)
    crop: str = Field(default="Tomato", min_length=1, max_length=100)
    growth_stage: str = Field(default="Vegetative", min_length=1, max_length=100)
    thermal_anomaly: Optional[float] = None
    advisory_language: str = Field(default="English", min_length=2, max_length=20)


class SimulatorStatusResponse(BaseModel):
    running: bool
    device_id: str
    farm_id: Optional[int]
    zone_id: str
    scenario: SimulatorScenario
    step: int
    interval: float
    seed: int
    last_reading_id: Optional[str] = None
    last_timestamp: Optional[datetime] = None
