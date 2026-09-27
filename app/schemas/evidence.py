"""
CRAI Evidence Schemas
Hardware/model agnostic structures used by the adaptive evidence layer.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EvidenceQuality:
    status: str
    score: float
    reasons: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "score": round(float(self.score), 3),
            "reasons": list(self.reasons),
            "missing": list(self.missing),
        }


@dataclass
class NormalizedEvidence:
    visual_confidence: Optional[float] = None
    image_quality_score: Optional[float] = None
    sensor_available: bool = False
    sensor_age_minutes: Optional[float] = None
    sensor_freshness: str = "UNKNOWN"
    thermal_available: bool = False
    spatial_available: bool = False
    temporal_available: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "visual_confidence": self.visual_confidence,
            "image_quality_score": self.image_quality_score,
            "sensor_available": self.sensor_available,
            "sensor_age_minutes": self.sensor_age_minutes,
            "sensor_freshness": self.sensor_freshness,
            "thermal_available": self.thermal_available,
            "spatial_available": self.spatial_available,
            "temporal_available": self.temporal_available,
            "metadata": self.metadata,
        }
