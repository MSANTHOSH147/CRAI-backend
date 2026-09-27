from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SensorInput(BaseModel):
    device_id: Optional[str] = None
    farm_id: Optional[int] = None
    zone_id: Optional[str] = None

    soil_moisture: Optional[float] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None

    timestamp: Optional[str] = None
    source: Optional[str] = None


class SpatialContext(BaseModel):
    nearby_observations: int = 0
    infected_neighbors: int = 0

    observed_zones: Optional[List[str]] = None
    scope: Optional[str] = None


class AnalysisRequest(BaseModel):
    # Visual AI
    prediction: str
    confidence: float = Field(ge=0, le=100)

    # Crop context
    crop: str = "Tomato"
    growth_stage: str = "Vegetative"

    # Environmental evidence
    temperature: float = 0.0
    humidity: float = 0.0
    thermal_anomaly: float = 0.0

    # Spatial evidence
    infected_neighbor_count: int = 0
    total_neighbor_count: int = 0
    disease_density: float = 0.0
    cluster_density: float = 0.0

    # Temporal evidence
    observation_count: int = 1

    # Sensor
    sensor: Optional[SensorInput] = None

    # Spatial context
    spatial_context: Optional[SpatialContext] = None

    # Historical observations
    history: Optional[List[Dict[str, Any]]] = None

    # Adaptive evidence
    second_image_available: bool = False
    thermal_available: bool = False

    # Image quality
    image_quality: Optional[Dict[str, Any]] = None


class AnalysisResponse(BaseModel):
    status: str

    disease: Dict[str, Any]

    evidence: Dict[str, Any]

    risk: Optional[Dict[str, Any]]

    decision: Dict[str, Any]