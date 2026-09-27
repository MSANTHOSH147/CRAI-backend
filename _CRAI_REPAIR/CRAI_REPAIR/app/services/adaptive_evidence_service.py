# ============================================================
# CRAI ADAPTIVE EVIDENCE SERVICE V2
# ============================================================

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


# ============================================================
# CONFIGURATION
# ============================================================

LOW_MODEL_CONFIDENCE = 60.0
MEDIUM_MODEL_CONFIDENCE = 85.0

FRESH_SENSOR_MINUTES = 15
RECENT_SENSOR_MINUTES = 15
STALE_SENSOR_MINUTES = 360

DEFAULT_VISUAL_ACCEPTANCE = 0.60


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_visual_confidence(
    confidence: Any,
) -> Optional[float]:

    if confidence is None:
        return None

    try:
        value = float(confidence)
    except (TypeError, ValueError):
        return None

    if value > 1.0:
        value /= 100.0

    return max(
        0.0,
        min(1.0, value),
    )


# ============================================================
# SENSOR FRESHNESS
# ============================================================

def calculate_sensor_freshness(
    timestamp: Optional[Any],
) -> str:

    if timestamp is None:
        return "UNAVAILABLE"

    try:

        if isinstance(timestamp, str):

            sensor_time = datetime.fromisoformat(
                timestamp.replace(
                    "Z",
                    "+00:00",
                )
            )

        elif isinstance(timestamp, datetime):

            sensor_time = timestamp

        else:

            return "UNAVAILABLE"

        if sensor_time.tzinfo is None:

            sensor_time = sensor_time.replace(
                tzinfo=timezone.utc
            )

        now = datetime.now(
            timezone.utc
        )

        age_minutes = (
            now - sensor_time
        ).total_seconds() / 60.0

        if age_minutes < 0:
            age_minutes = 0.0

        if age_minutes <= FRESH_SENSOR_MINUTES:
            return "FRESH"

        if age_minutes <= RECENT_SENSOR_MINUTES:
            return "RECENT"

        if age_minutes <= STALE_SENSOR_MINUTES:
            return "STALE"

        return "UNAVAILABLE"

    except Exception:

        return "UNAVAILABLE"


# ============================================================
# SENSOR EVIDENCE
# ============================================================

def evaluate_sensor_evidence(
    sensor: Optional[dict],
) -> dict:

    if not sensor:

        return {
            "available": False,
            "freshness": "UNAVAILABLE",
            "values_available": [],
        }

    available_values = []

    for field in (
        "soil_moisture",
        "temperature",
        "humidity",
    ):

        if sensor.get(field) is not None:
            available_values.append(field)

    freshness = calculate_sensor_freshness(
        sensor.get("timestamp")
    )

    return {
        "available": len(available_values) > 0,
        "freshness": freshness,
        "values_available": available_values,
    }


# ============================================================
# MODEL EVIDENCE
# ============================================================

def evaluate_model_evidence(
    prediction: Optional[str],
    confidence: Any,
) -> dict:

    normalized = normalize_visual_confidence(
        confidence
    )

    if prediction is None:

        return {
            "available": False,
            "confidence": normalized,
            "accepted": False,
            "uncertainty": 1.0,
        }

    if normalized is None:

        return {
            "available": True,
            "confidence": None,
            "accepted": False,
            "uncertainty": 1.0,
        }

    return {
        "available": True,
        "confidence": normalized,
        "accepted": (
            normalized
            >= DEFAULT_VISUAL_ACCEPTANCE
        ),
        "uncertainty": 1.0 - normalized,
    }


# ============================================================
# GENERIC EVIDENCE FLAGS
# ============================================================

def _has_spatial_evidence(
    spatial_available: Any,
) -> bool:

    return bool(spatial_available)


def _has_temporal_evidence(
    temporal_available: Any,
) -> bool:

    return bool(temporal_available)


# ============================================================
# NEXT-BEST-EVIDENCE CONTROLLER
# ============================================================

def select_next_evidence(
    *,
    visual_confidence: Any = None,
    sensor_available: bool = False,
    sensor_age_minutes: Optional[float] = None,
    sensor_freshness: Optional[str] = None,
    second_image_available: bool = False,
    thermal_available: bool = False,
    spatial_available: bool = False,
    temporal_available: bool = False,
    image_quality_status: Optional[str] = None,
) -> dict:

    confidence = normalize_visual_confidence(
        visual_confidence
    )

    # ========================================================
    # 1. IMAGE QUALITY FAILURE
    # ========================================================

    if image_quality_status == "RETAKE_REQUIRED":

        return {
            "action": "REQUEST_IMAGE",

            "adaptive_action":
                "RETAKE_IMAGE",

            "priority":
                "HIGH",

            # IMPORTANT:
            # This is the exact V1/V2 contract expected
            # by the test suite.
            "evidence_required":
                "RETAKE_IMAGE",

            "requested_evidence":
                [
                    "RETAKE_IMAGE"
                ],

            "next_best_source":
                "SMARTPHONE",

            "source":
                "SMARTPHONE",

            "decision_ready":
                False,

            "visual_evidence_accepted":
                False,

            "evidence_gap":
                "IMAGE_QUALITY",

            "reason":
                (
                    "Image quality is insufficient. "
                    "CRAI should acquire a clearer image "
                    "before inference is trusted."
                ),
        }

    # ========================================================
    # 2. NO VISUAL PREDICTION
    # ========================================================

    if confidence is None:

        return {
            "action":
                "REQUEST_IMAGE",

            "adaptive_action":
                "REQUEST_IMAGE",

            "priority":
                "HIGH",

            "evidence_required":
                "SECOND_IMAGE",

            "requested_evidence":
                [
                    "IMAGE"
                ],

            "next_best_source":
                "SMARTPHONE",

            "source":
                "SMARTPHONE",

            "decision_ready":
                False,

            "visual_evidence_accepted":
                False,

            "evidence_gap":
                "VISUAL",

            "reason":
                (
                    "No usable visual prediction is "
                    "available. CRAI requires an image "
                    "observation."
                ),
        }

    # ========================================================
    # 3. VERY LOW VISUAL CONFIDENCE
    # ========================================================

    if confidence < 0.60:

        if not second_image_available:

            return {
                "action":
                    "REQUEST_IMAGE",

                "adaptive_action":
                    "SECOND_IMAGE",

                "priority":
                    "HIGH",

                "evidence_required":
                    "SECOND_IMAGE",

                "requested_evidence":
                    [
                        "SECOND_IMAGE"
                    ],

                "next_best_source":
                    "SMARTPHONE",

                "source":
                    "SMARTPHONE",

                "decision_ready":
                    False,

                "visual_evidence_accepted":
                    False,

                "evidence_gap":
                    "VISUAL_UNCERTAINTY",

                "reason":
                    (
                        "Visual confidence is below "
                        "the CRAI operating threshold. "
                        "Acquire another image before "
                        "making a field assessment."
                    ),
            }

    # ========================================================
    # 4. MODERATE VISUAL CONFIDENCE
    # ========================================================

    if 0.60 <= confidence < 0.85:

        if not second_image_available:

            return {
                "action":
                    "REQUEST_IMAGE",

                "adaptive_action":
                    "SECOND_IMAGE",

                "priority":
                    "MEDIUM",

                "evidence_required":
                    "SECOND_IMAGE",

                "requested_evidence":
                    [
                        "SECOND_IMAGE"
                    ],

                "next_best_source":
                    "SMARTPHONE",

                "source":
                    "SMARTPHONE",

                "decision_ready":
                    False,

                "visual_evidence_accepted":
                    False,

                "evidence_gap":
                    "VISUAL_UNCERTAINTY",

                "reason":
                    (
                        "Visual confidence is acceptable "
                        "for screening but remains below "
                        "the stronger CRAI evidence threshold. "
                        "Acquire another image if available."
                    ),
            }

    # ========================================================
    # 5. STRONG VISUAL + MISSING SENSOR
    # ========================================================

    if (
        confidence >= 0.85
        and not sensor_available
    ):

        return {
            "action":
                "REQUEST_SENSOR",

            "adaptive_action":
                "REFRESH_SENSOR",

            "priority":
                "MEDIUM",

            "evidence_required":
                "ENVIRONMENT",

            "requested_evidence":
                [
                    "ENVIRONMENT"
                ],

            "next_best_source":
                "ESP32",

            "source":
                "ESP32",

            "decision_ready":
                False,

            "visual_evidence_accepted":
                True,

            "evidence_gap":
                "ENVIRONMENT",

            "reason":
                (
                    "Visual evidence is strong, but "
                    "environmental evidence is missing. "
                    "CRAI should acquire a sensor reading "
                    "before a stronger field-level decision."
                ),
        }

    # ========================================================
    # 6. SENSOR FRESHNESS
    # ========================================================

    freshness = sensor_freshness

    if freshness is None:

        if sensor_age_minutes is not None:

            if sensor_age_minutes <= FRESH_SENSOR_MINUTES:
                freshness = "FRESH"

            elif sensor_age_minutes <= RECENT_SENSOR_MINUTES:
                freshness = "RECENT"

            elif sensor_age_minutes <= STALE_SENSOR_MINUTES:
                freshness = "STALE"

            else:
                freshness = "UNAVAILABLE"

    if (
        sensor_available
        and freshness in {
            "STALE",
            "UNAVAILABLE",
        }
    ):

        return {
            "action":
                "REQUEST_SENSOR",

            "adaptive_action":
                "REFRESH_SENSOR",

            "priority":
                "MEDIUM",

            "evidence_required":
                "ENVIRONMENT",

            "requested_evidence":
                [
                    "FRESH_SENSOR"
                ],

            "next_best_source":
                "ESP32",

            "source":
                "ESP32",

            "decision_ready":
                False,

            "visual_evidence_accepted":
                confidence >= 0.60,

            "evidence_gap":
                "STALE_ENVIRONMENT",

            "reason":
                (
                    "Environmental evidence is stale. "
                    "CRAI should acquire a fresh sensor reading."
                ),
        }

    # ========================================================
    # 7. THERMAL EVIDENCE
    # ========================================================

    if (
        confidence >= 0.85
        and thermal_available
        and not spatial_available
        and not temporal_available
    ):
        pass

    # ========================================================
    # 8. STRONG MULTIMODAL EVIDENCE
    # ========================================================

    if (
        confidence >= 0.60
        and sensor_available
        and freshness in {
            "FRESH",
            "RECENT",
        }
    ):

        return {
            "action":
                "ACCEPT",

            "adaptive_action":
                "DECISION_READY",

            "priority":
                "LOW",

            "evidence_required":
                "NONE",

            "requested_evidence":
                [],

            "next_best_source":
                None,

            "source":
                None,

            "decision_ready":
                True,

            "visual_evidence_accepted":
                True,

            "evidence_gap":
                None,

            "reason":
                (
                    "Available visual and environmental "
                    "evidence is sufficient for the current "
                    "CRAI decision."
                ),
        }

    # ========================================================
    # 9. FALLBACK
    # ========================================================

    return {
        "action":
            "REQUEST_SENSOR",

        "adaptive_action":
            "REFRESH_SENSOR",

        "priority":
            "MEDIUM",

        "evidence_required":
            "ENVIRONMENT",

        "requested_evidence":
            [
                "ENVIRONMENT"
            ],

        "next_best_source":
            "ESP32",

        "source":
            "ESP32",

        "decision_ready":
            False,

        "visual_evidence_accepted":
            confidence >= 0.60,

        "evidence_gap":
            "ENVIRONMENT",

        "reason":
            (
                "CRAI requires additional environmental "
                "evidence before finalizing the field assessment."
            ),
    }


# ============================================================
# BACKWARD-COMPATIBLE PUBLIC API
# ============================================================

def evaluate_adaptive_evidence(
    visual_confidence: Any = None,
    sensor_available: bool = False,
    sensor_age_minutes: Optional[float] = None,
    second_image_available: bool = False,
    thermal_available: bool = False,
    spatial_available: bool = False,
    temporal_available: bool = False,
    image_quality_status: Optional[str] = None,
    sensor_freshness: Optional[str] = None,
    image_quality: Optional[dict] = None,
) -> dict:

    # --------------------------------------------------------
    # Preserve image_quality object contract
    # --------------------------------------------------------

    if image_quality is not None:

        if image_quality_status is None:

            image_quality_status = image_quality.get(
                "status"
            )

    result = select_next_evidence(

        visual_confidence=visual_confidence,

        sensor_available=sensor_available,

        sensor_age_minutes=sensor_age_minutes,

        sensor_freshness=sensor_freshness,

        second_image_available=second_image_available,

        thermal_available=thermal_available,

        spatial_available=spatial_available,

        temporal_available=temporal_available,

        image_quality_status=image_quality_status,
    )

    # --------------------------------------------------------
    # Preserve V1 action contract
    # --------------------------------------------------------

    if result.get("action") == "ACCEPT":

        result["action"] = "ACCEPT_AND_FUSE"

        result["adaptive_action"] = (
            "DECISION_READY"
        )

    # --------------------------------------------------------
    # Backward compatibility
    # --------------------------------------------------------

    result["accepted"] = result[
        "visual_evidence_accepted"
    ]

    return result


# ============================================================
# HIGHER-LEVEL ADAPTER
# ============================================================

def adaptive_evidence_decision(
    *,
    prediction: Optional[str] = None,
    confidence: Any = None,
    sensor: Optional[dict] = None,
    second_image_available: bool = False,
    thermal_available: bool = False,
    spatial_available: bool = False,
    temporal_available: bool = False,
    image_quality_status: Optional[str] = None,
) -> dict:

    sensor_info = evaluate_sensor_evidence(
        sensor
    )

    return evaluate_adaptive_evidence(

        visual_confidence=confidence,

        sensor_available=(
            sensor_info["available"]
        ),

        sensor_freshness=(
            sensor_info["freshness"]
        ),

        second_image_available=(
            second_image_available
        ),

        thermal_available=(
            thermal_available
        ),

        spatial_available=(
            spatial_available
        ),

        temporal_available=(
            temporal_available
        ),

        image_quality_status=(
            image_quality_status
        ),
    )


# ============================================================
# SECOND IMAGE INSTRUCTION
# ============================================================

def second_image_instruction() -> dict:

    return {
        "action":
            "REQUEST_IMAGE",

        "source":
            "SMARTPHONE",

        "instruction":
            (
                "Capture another image of the same leaf "
                "from a slightly different angle with "
                "the leaf filling most of the frame."
            ),

        "reason":
            "A second observation can reduce visual uncertainty.",
    }
