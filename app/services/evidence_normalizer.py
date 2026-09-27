"""
CRAI Evidence Normalizer

Converts evidence arriving from different models, sensor boards,
APIs, or future drone/thermal adapters into one hardware-agnostic structure.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.schemas.evidence import NormalizedEvidence


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _first(payload: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


def _age_minutes(timestamp: Any) -> Optional[float]:
    if timestamp is None:
        return None

    if isinstance(timestamp, datetime):
        dt = timestamp
    else:
        text = str(timestamp).strip()

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    age = (
        datetime.now(timezone.utc)
        - dt.astimezone(timezone.utc)
    ).total_seconds() / 60.0

    return max(0.0, age)


def sensor_freshness(age_minutes: Optional[float]) -> str:
    if age_minutes is None:
        return "UNKNOWN"

    if age_minutes <= 15:
        return "FRESH"

    if age_minutes <= 60:
        return "RECENT"

    if age_minutes <= 360:
        return "STALE"

    return "VERY_STALE"


def normalize_evidence(
    payload: Optional[Dict[str, Any]]
) -> NormalizedEvidence:

    payload = payload or {}

    confidence = _to_float(
        _first(
            payload,
            "visual_confidence",
            "confidence",
            "model_confidence",
        )
    )

    if confidence is not None and confidence > 1.0:
        confidence /= 100.0

    if confidence is not None:
        confidence = min(1.0, max(0.0, confidence))

    image_quality = _to_float(
        _first(
            payload,
            "image_quality_score",
            "quality_score",
        )
    )

    if image_quality is not None and image_quality > 1.0:
        image_quality /= 100.0

    if image_quality is not None:
        image_quality = min(1.0, max(0.0, image_quality))

    explicit_sensor = _first(
        payload,
        "sensor_available",
        "environmental_sensor_available",
    )

    sensor_values_present = any(
        payload.get(key) is not None
        for key in (
            "soil_moisture",
            "soil_temperature",
            "temperature",
            "humidity",
            "relative_humidity",
            "soil_ec",
            "ph",
        )
    )

    sensor_available = (
        bool(explicit_sensor)
        if explicit_sensor is not None
        else sensor_values_present
    )

    timestamp = _first(
        payload,
        "sensor_timestamp",
        "timestamp",
        "recorded_at",
        "created_at",
    )

    age = _age_minutes(timestamp)

    freshness = sensor_freshness(age)

    thermal_available = bool(
        _first(payload, "thermal_available") is True
        or payload.get("thermal_anomaly") is not None
        or payload.get("leaf_temperature") is not None
    )

    spatial_available = bool(
        _first(payload, "spatial_available") is True
        or payload.get("infected_neighbor_count") is not None
        or payload.get("total_neighbor_count") is not None
    )

    temporal_available = bool(
        _first(payload, "temporal_available") is True
        or payload.get("history_length", 0) not in (None, 0)
        or payload.get("risk_history")
        or payload.get("disease_history")
    )

    return NormalizedEvidence(
        visual_confidence=confidence,
        image_quality_score=image_quality,
        sensor_available=sensor_available,
        sensor_age_minutes=age,
        sensor_freshness=freshness,
        thermal_available=thermal_available,
        spatial_available=spatial_available,
        temporal_available=temporal_available,
        metadata=dict(payload),
    )
