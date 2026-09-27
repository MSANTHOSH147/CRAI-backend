"""
CRAI Evidence Service V1.5

Unified evidence layer used by:
    - adaptive_evidence_service.py
    - analysis_service.py
    - future sensor/drone/thermal adapters

Responsibilities:
    1. Evaluate visual evidence.
    2. Evaluate environmental evidence.
    3. Evaluate spatial evidence.
    4. Evaluate temporal evidence.
    5. Decide whether enough evidence exists for fusion.
    6. Request the most useful next evidence when it does not.

Model confidence is evidence strength, NOT field accuracy.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


LOW_MODEL_CONFIDENCE = 60.0
MEDIUM_MODEL_CONFIDENCE = 85.0

FRESH_SENSOR_MINUTES = 15
RECENT_SENSOR_MINUTES = 15
STALE_SENSOR_MINUTES = 360

DEFAULT_VISUAL_THRESHOLD = 0.60


def clamp(
    value: float,
    low: float = 0.0,
    high: float = 1.0,
) -> float:

    return max(
        low,
        min(high, float(value)),
    )


# ============================================================
# SENSOR FRESHNESS
# ============================================================

def calculate_sensor_freshness(
    timestamp: Optional[datetime],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:

    if timestamp is None:

        return {
            "status": "UNKNOWN",
            "age_minutes": None,
            "quality": 0.60,
            "usable": True,
        }

    now = now or datetime.now(timezone.utc)

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(
            tzinfo=timezone.utc
        )

    if now.tzinfo is None:
        now = now.replace(
            tzinfo=timezone.utc
        )

    age_minutes = max(
        0.0,
        (
            now
            - timestamp.astimezone(
                timezone.utc
            )
        ).total_seconds() / 60.0,
    )

    if age_minutes <= FRESH_SENSOR_MINUTES:

        status = "FRESH"
        quality = 1.0
        usable = True

    elif age_minutes <= RECENT_SENSOR_MINUTES:

        status = "RECENT"
        quality = 0.85
        usable = True

    elif age_minutes <= STALE_SENSOR_MINUTES:

        status = "STALE"
        quality = 0.45
        usable = False

    else:

        status = "VERY_STALE"
        quality = 0.15
        usable = False

    return {
        "status": status,
        "age_minutes": round(
            age_minutes,
            2,
        ),
        "quality": quality,
        "usable": usable,
    }


def _parse_timestamp(
    value: Any,
) -> Optional[datetime]:

    if value is None:
        return None

    if isinstance(
        value,
        datetime,
    ):
        return value

    text = str(value).strip()

    if text.endswith("Z"):
        text = (
            text[:-1]
            + "+00:00"
        )

    try:

        return datetime.fromisoformat(
            text
        )

    except ValueError:

        return None


# ============================================================
# VISUAL EVIDENCE
# ============================================================

def evaluate_model_evidence(
    prediction: Optional[Any],
    confidence: Optional[float] = None,
) -> Dict[str, Any]:

    if (
        prediction is None
        and confidence is None
    ):

        return {
            "available": False,
            "quality": 0.0,
            "confidence": None,
            "status": "MISSING",
            "reason": (
                "No visual prediction is available."
            ),
        }

    if confidence is None:

        if isinstance(
            prediction,
            dict,
        ):

            confidence = prediction.get(
                "confidence"
            )

    if confidence is None:

        return {
            "available": False,
            "quality": 0.0,
            "confidence": None,
            "status": "UNKNOWN",
            "reason": (
                "Visual prediction exists but "
                "confidence is unavailable."
            ),
        }

    value = float(
        confidence
    )

    if value <= 1.0:
        value *= 100.0

    value = max(
        0.0,
        min(
            100.0,
            value,
        ),
    )

    if value < LOW_MODEL_CONFIDENCE:

        status = "LOW"

    elif value < MEDIUM_MODEL_CONFIDENCE:

        status = "MODERATE"

    else:

        status = "STRONG"

    return {
        "available": True,
        "quality": value / 100.0,
        "confidence": round(
            value,
            2,
        ),
        "status": status,
        "prediction": (
            prediction
            if not isinstance(
                prediction,
                dict,
            )
            else prediction.get(
                "prediction"
            )
        ),
        "reason": (
            f"Visual model confidence is "
            f"{value:.1f}%."
        ),
    }


# ============================================================
# SENSOR EVIDENCE
# ============================================================

def evaluate_sensor_evidence(
    sensor: Optional[Dict[str, Any]],
    timestamp: Optional[datetime] = None,
) -> Dict[str, Any]:

    if not sensor:

        return {
            "available": False,
            "status": "MISSING",
            "quality": 0.0,
            "usable": False,
            "age_minutes": None,
            "reason": (
                "No environmental sensor "
                "evidence is available."
            ),
        }

    if timestamp is None:

        for key in (
            "timestamp",
            "recorded_at",
            "created_at",
            "sensor_timestamp",
        ):

            if sensor.get(key) is not None:

                timestamp = _parse_timestamp(
                    sensor.get(key)
                )

                if timestamp is not None:
                    break

    freshness = (
        calculate_sensor_freshness(
            timestamp
        )
    )

    return {
        "available": True,
        "status": freshness["status"],
        "quality": freshness["quality"],
        "usable": freshness["usable"],
        "age_minutes": freshness["age_minutes"],
        "reason": (
            "Environmental evidence is "
            "available and usable."
            if freshness["usable"]
            else
            "Environmental evidence exists "
            "but is stale."
        ),
    }


# ============================================================
# SPATIAL EVIDENCE
# ============================================================

def evaluate_spatial_evidence(
    infected_neighbor_count: Optional[int] = None,
    total_neighbor_count: Optional[int] = None,
    density: Optional[float] = None,
    spatial_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    spatial_context = (
        spatial_context or {}
    )

    if infected_neighbor_count is None:

        infected_neighbor_count = spatial_context.get(
            "infected_neighbors",
            spatial_context.get(
                "infected_neighbor_count"
            ),
        )

    if total_neighbor_count is None:

        total_neighbor_count = spatial_context.get(
            "nearby_observations",
            spatial_context.get(
                "total_neighbor_count"
            ),
        )

    if density is None:

        density = spatial_context.get(
            "cluster_density",
            spatial_context.get(
                "disease_density"
            ),
        )

    if (
        total_neighbor_count is not None
        and int(total_neighbor_count) > 0
    ):

        infected = max(
            0,
            int(
                infected_neighbor_count
                or 0
            ),
        )

        total = max(
            1,
            int(
                total_neighbor_count
            ),
        )

        ratio = (
            infected / total
        )

        return {
            "available": True,
            "quality": 1.0,
            "infection_ratio": round(
                ratio,
                3,
            ),
            "infected_neighbors": infected,
            "total_observations": total,
            "reason": (
                "Spatial evidence is available "
                "from observed zones."
            ),
        }

    if density is not None:

        value = float(
            density
        )

        return {
            "available": True,
            "quality": 0.75,
            "density": value,
            "reason": (
                "Spatial density evidence "
                "is available."
            ),
        }

    return {
        "available": False,
        "quality": 0.0,
        "reason": (
            "No spatial history is available."
        ),
    }


# ============================================================
# TEMPORAL EVIDENCE
# ============================================================

def evaluate_temporal_evidence(
    risk_history: Optional[List[float]] = None,
    disease_history: Optional[List[Any]] = None,
    history: Optional[List[Any]] = None,
) -> Dict[str, Any]:

    if history is not None:

        if risk_history is None:

            extracted = []

            for item in history:

                if isinstance(
                    item,
                    dict,
                ):

                    value = item.get(
                        "risk_score",
                        item.get(
                            "risk"
                        ),
                    )

                    if value is not None:

                        try:
                            extracted.append(
                                float(value)
                            )
                        except (
                            TypeError,
                            ValueError,
                        ):
                            pass

                else:

                    try:
                        extracted.append(
                            float(item)
                        )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        pass

            risk_history = extracted

        if disease_history is None:

            disease_history = history

    risk_history = (
        risk_history or []
    )

    disease_history = (
        disease_history or []
    )

    if len(risk_history) >= 2:

        delta = (
            float(
                risk_history[-1]
            )
            - float(
                risk_history[0]
            )
        )

        if delta >= 20:

            trend = "RAPIDLY_INCREASING"
            quality = 1.0

        elif delta >= 8:

            trend = "INCREASING"
            quality = 0.90

        elif delta <= -20:

            trend = "STRONGLY_DECREASING"
            quality = 1.0

        elif delta <= -8:

            trend = "DECREASING"
            quality = 0.90

        else:

            trend = "STABLE"
            quality = 0.75

        return {
            "available": True,
            "quality": quality,
            "trend": trend,
            "delta": round(
                delta,
                2,
            ),
            "history_length": len(
                risk_history
            ),
            "reason": (
                "Risk history indicates a "
                f"{trend.lower().replace('_', ' ')} trend."
            ),
        }

    if len(disease_history) >= 2:

        return {
            "available": True,
            "quality": 0.60,
            "trend": "CHANGING",
            "delta": None,
            "history_length": len(
                disease_history
            ),
            "reason": (
                "Disease observations "
                "changed over time."
            ),
        }

    return {
        "available": False,
        "quality": 0.0,
        "trend": "UNKNOWN",
        "history_length": len(
            disease_history
        ),
        "reason": (
            "Insufficient temporal history."
        ),
    }


# ============================================================
# COMPLETE EVIDENCE EVALUATION
# ============================================================

def evaluate_evidence(
    *,
    prediction: Optional[Any] = None,
    confidence: Optional[float] = None,

    sensor: Optional[Dict[str, Any]] = None,

    sensor_timestamp: Optional[datetime] = None,

    spatial_context: Optional[Dict[str, Any]] = None,

    history: Optional[List[Any]] = None,

    infected_neighbor_count: Optional[int] = None,
    total_neighbor_count: Optional[int] = None,

    disease_density: Optional[float] = None,
    cluster_density: Optional[float] = None,

    second_image_available: bool = False,
    thermal_available: bool = False,

) -> Dict[str, Any]:

    visual = evaluate_model_evidence(
        prediction=prediction,
        confidence=confidence,
    )

    environmental = (
        evaluate_sensor_evidence(
            sensor=sensor,
            timestamp=sensor_timestamp,
        )
    )

    spatial = evaluate_spatial_evidence(
        infected_neighbor_count=(
            infected_neighbor_count
        ),
        total_neighbor_count=(
            total_neighbor_count
        ),
        density=(
            cluster_density
            if cluster_density
            else disease_density
        ),
        spatial_context=spatial_context,
    )

    temporal = evaluate_temporal_evidence(
        history=history,
    )

    available = {
        "visual": visual["available"],
        "environmental": environmental["available"],
        "spatial": spatial["available"],
        "temporal": temporal["available"],
    }

    quality = {
        "visual": visual["quality"],
        "environmental": environmental["quality"],
        "spatial": spatial["quality"],
        "temporal": temporal["quality"],
    }

    # --------------------------------------------------------
    # Adaptive next-evidence decision
    # --------------------------------------------------------

    requested_evidence = []
    action = "ACCEPT_AND_FUSE"
    priority = "LOW"
    reason = (
        "Available evidence is sufficient "
        "for multimodal fusion."
    )

    visual_confidence = (
        visual.get(
            "confidence"
        )
    )

    normalized_confidence = None

    if visual_confidence is not None:

        normalized_confidence = (
            float(
                visual_confidence
            ) / 100.0
        )

    if not visual["available"]:

        action = "REQUEST_IMAGE"

        requested_evidence = [
            "SECOND_IMAGE"
        ]

        priority = "HIGH"

        reason = (
            "No usable visual evidence "
            "is available."
        )

    elif (
        normalized_confidence is not None
        and normalized_confidence
        < DEFAULT_VISUAL_THRESHOLD
    ):

        if second_image_available:

            action = "REQUEST_MANUAL_REVIEW"

            requested_evidence = [
                "MANUAL_REVIEW"
            ]

            priority = "MEDIUM"

            reason = (
                "Visual evidence remains uncertain "
                "after an additional image."
            )

        else:

            action = "REQUEST_IMAGE"

            requested_evidence = [
                "SECOND_IMAGE"
            ]

            priority = "HIGH"

            reason = (
                "Visual confidence is below "
                "the adaptive acceptance threshold."
            )

    elif (
        normalized_confidence is not None
        and normalized_confidence >= 0.85
        and not environmental["available"]
    ):

        action = "REQUEST_SENSOR"

        requested_evidence = [
            "SOIL_MOISTURE"
        ]

        priority = "HIGH"

        reason = (
            "Visual evidence is strong, but "
            "environmental evidence is missing."
        )

    elif (
        environmental["available"]
        and not environmental["usable"]
    ):

        action = "REQUEST_SENSOR"

        requested_evidence = [
            "FRESH_SENSOR_READING"
        ]

        priority = "HIGH"

        reason = (
            "Environmental evidence is stale "
            "and should be refreshed."
        )

    elif (
        normalized_confidence is not None
        and normalized_confidence < 0.85
        and not environmental["available"]
    ):

        action = "REQUEST_SENSOR"

        requested_evidence = [
            "SOIL_MOISTURE"
        ]

        priority = "MEDIUM"

        reason = (
            "Visual evidence is acceptable but "
            "needs environmental evidence."
        )

    additional_required = (
        action
        != "ACCEPT_AND_FUSE"
    )

    return {
        "engine": "CRAI_EVIDENCE_V1_5",

        "available": available,

        "quality": {
            key: round(
                float(value),
                3,
            )
            for key, value in quality.items()
        },

        "evidence_count": sum(
            available.values()
        ),

        "details": {
            "visual": visual,
            "environmental": environmental,
            "spatial": spatial,
            "temporal": temporal,
        },

        "adaptive": {
            "action": action,
            "priority": priority,
            "reason": reason,
        },

        # Backward-compatible fields
        # required by analysis_service.py
        "additional_evidence_required": (
            additional_required
        ),

        "requested_evidence": (
            requested_evidence
        ),

        "decision_ready": (
            not additional_required
        ),
    }


# ============================================================
# SECOND IMAGE INSTRUCTION
# ============================================================

def second_image_instruction(
    prediction: Optional[Dict[str, Any]] = None,
    confidence: Optional[float] = None,
    quality: Optional[Dict[str, Any]] = None,
) -> str:

    if quality:

        failed = quality.get(
            "failed_checks",
            [],
        )

        if "sharpness" in failed:

            return (
                "Hold the phone steady and "
                "capture a sharper image."
            )

        if "brightness" in failed:

            return (
                "Capture the leaf in even lighting "
                "without direct glare."
            )

        if "resolution" in failed:

            return (
                "Move closer and capture the "
                "visible symptom or lesion area."
            )

    if confidence is None:

        return (
            "Capture another clear image "
            "of the affected leaf."
        )

    if confidence < 45:

        return (
            "Capture another affected leaf "
            "from the same field zone."
        )

    if confidence < 60:

        return (
            "Move closer and capture the "
            "visible symptom or lesion area."
        )

    return (
        "Capture another affected leaf "
        "from a slightly different angle."
    )


# ============================================================
# ADAPTIVE POLICY
# ============================================================

def adaptive_evidence_decision(
    *,
    visual_confidence: Optional[float],
    sensor_available: bool = False,
    sensor_age_minutes: Optional[float] = None,
    second_image_available: bool = False,
    thermal_available: bool = False,
    threshold: float = DEFAULT_VISUAL_THRESHOLD,
    image_quality: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    if visual_confidence is not None:

        vc = float(
            visual_confidence
        )

        if vc > 1.0:
            vc /= 100.0

        vc = clamp(vc)

    else:

        vc = None

    if (
        image_quality
        and image_quality.get(
            "status"
        )
        == "RETAKE_REQUIRED"
    ):

        return {
            "action": "REQUEST_IMAGE",
            "reason": (
                "The captured image quality is "
                "insufficient for reliable "
                "visual inference."
            ),
            "evidence_required": (
                "RETAKE_IMAGE"
            ),
            "priority": "HIGH",
            "visual_evidence_accepted": False,
            "decision_ready": False,
            "visual_confidence": vc,
            "threshold": threshold,
            "next_instruction": (
                second_image_instruction(
                    confidence=(
                        vc * 100
                        if vc is not None
                        else None
                    ),
                    quality=image_quality,
                )
            ),
        }

    if vc is None:

        return {
            "action": "REQUEST_IMAGE",
            "reason": (
                "No visual prediction is available."
            ),
            "evidence_required": (
                "SECOND_IMAGE"
            ),
            "priority": "HIGH",
            "visual_evidence_accepted": False,
            "decision_ready": False,
            "visual_confidence": None,
            "threshold": threshold,
        }

    if vc < threshold:

        if second_image_available:

            return {
                "action": "REQUEST_MANUAL_REVIEW",
                "reason": (
                    "Visual evidence remains "
                    "uncertain after an additional image."
                ),
                "evidence_required": (
                    "MANUAL_REVIEW"
                ),
                "priority": "MEDIUM",
                "visual_evidence_accepted": False,
                "decision_ready": False,
                "visual_confidence": vc,
                "threshold": threshold,
            }

        return {
            "action": "REQUEST_IMAGE",
            "reason": (
                "Visual confidence is below "
                "the adaptive acceptance threshold."
            ),
            "evidence_required": (
                "SECOND_IMAGE"
            ),
            "priority": "HIGH",
            "visual_evidence_accepted": False,
            "decision_ready": False,
            "visual_confidence": vc,
            "threshold": threshold,
            "next_instruction": (
                second_image_instruction(
                    confidence=vc * 100,
                    quality=image_quality,
                )
            ),
        }

    sensor_recent = (
        sensor_available
        and (
            sensor_age_minutes is None
            or sensor_age_minutes
            <= RECENT_SENSOR_MINUTES
        )
    )

    sensor_fresh = (
        sensor_available
        and (
            sensor_age_minutes is None
            or sensor_age_minutes
            <= FRESH_SENSOR_MINUTES
        )
    )

    if vc >= 0.85:

        if not sensor_available:

            return {
                "action": "REQUEST_SENSOR",
                "reason": (
                    "Visual evidence is strong, "
                    "but environmental evidence is missing."
                ),
                "evidence_required": (
                    "SOIL_MOISTURE"
                ),
                "priority": "HIGH",
                "visual_evidence_accepted": True,
                "decision_ready": False,
                "visual_confidence": vc,
                "threshold": threshold,
            }

        if not sensor_recent:

            return {
                "action": "REQUEST_SENSOR",
                "reason": (
                    "Visual evidence is strong, "
                    "but environmental evidence is stale."
                ),
                "evidence_required": (
                    "FRESH_SENSOR_READING"
                ),
                "priority": "HIGH",
                "visual_evidence_accepted": True,
                "decision_ready": False,
                "visual_confidence": vc,
                "threshold": threshold,
            }

        return {
            "action": "ACCEPT_AND_FUSE",
            "reason": (
                "Strong visual evidence is supported "
                "by fresh environmental evidence."
                if sensor_fresh
                else
                "Strong visual evidence is supported "
                "by recent environmental evidence."
            ),
            "evidence_required": None,
            "priority": "LOW",
            "visual_evidence_accepted": True,
            "decision_ready": True,
            "visual_confidence": vc,
            "threshold": threshold,
        }

    if sensor_recent:

        return {
            "action": "ACCEPT_AND_FUSE",
            "reason": (
                "Moderate visual evidence is supported "
                "by usable environmental evidence."
            ),
            "evidence_required": None,
            "priority": "MEDIUM",
            "visual_evidence_accepted": True,
            "decision_ready": True,
            "visual_confidence": vc,
            "threshold": threshold,
        }

    return {
        "action": "REQUEST_SENSOR",
        "reason": (
            "Visual evidence is acceptable but "
            "needs environmental evidence."
        ),
        "evidence_required": (
            "SOIL_MOISTURE"
        ),
        "priority": "MEDIUM",
        "visual_evidence_accepted": True,
        "decision_ready": False,
        "visual_confidence": vc,
        "threshold": threshold,
    }
