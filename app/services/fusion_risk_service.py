"""
CRAI Explainable Evidence Fusion Risk Service
Version: FUSION_V1_5

Core principle:
    Missing evidence is UNKNOWN, not zero-risk evidence.

This service intentionally preserves the V1.5 response schema because
existing backend services/tests depend on it.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


MODEL_TYPE = "CRAI_EXPLAINABLE_EVIDENCE_FUSION"
MODEL_VERSION = "FUSION_V1_5"

# Backward-compatible public aliases.
VERSION = MODEL_VERSION


BASE_WEIGHTS = {
    "visual": 35.0,
    "environmental": 25.0,
    "spatial": 25.0,
    "temporal": 15.0,
}


LOW_THRESHOLD = 30.0
MODERATE_THRESHOLD = 50.0
HIGH_THRESHOLD = 70.0


def _safe_float(
    value: Any,
    default: Optional[float] = None,
) -> Optional[float]:
    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(
        minimum,
        min(
            maximum,
            float(value),
        ),
    )


def _normalize_confidence(
    value: Any,
) -> Optional[float]:
    """
    Normalize confidence to 0-100.

    Accepts:
        0.91
        91
    """

    confidence = _safe_float(value)

    if confidence is None:
        return None

    if 0.0 <= confidence <= 1.0:
        confidence *= 100.0

    return _clamp(confidence)


def _healthy(
    disease: Any,
) -> bool:
    if disease is None:
        return False

    text = str(disease).lower()

    return (
        "healthy" in text
        or "normal" in text
        or "no disease" in text
        or "no_disease" in text
    )


# ============================================================
# VISUAL
# ============================================================

def _visual_risk(
    disease: Any,
    visual_confidence: Any,
) -> Optional[float]:

    confidence = _normalize_confidence(
        visual_confidence
    )

    if confidence is None:
        return None

    if disease is None:
        return None

    # A highly confident healthy prediction should produce
    # very low disease-risk signal.
    if _healthy(disease):

        return _clamp(
            100.0 - confidence
        )

    return confidence


# ============================================================
# ENVIRONMENTAL
# ============================================================

def _environmental_risk(
    soil_moisture: Any = None,
    temperature: Any = None,
    humidity: Any = None,
    thermal_anomaly: Any = None,
) -> Optional[float]:

    signals = []

    soil = _safe_float(
        soil_moisture
    )

    temp = _safe_float(
        temperature
    )

    hum = _safe_float(
        humidity
    )

    thermal = _safe_float(
        thermal_anomaly
    )

    # ----------------------------
    # Soil moisture
    # ----------------------------

    if soil is not None:

        if soil < 20:
            risk = 100.0

        elif soil < 30:
            risk = 75.0

        elif soil < 40:
            risk = 45.0

        else:
            risk = 10.0

        signals.append(risk)

    # ----------------------------
    # Temperature
    # ----------------------------

    if temp is not None:

        if temp >= 40:
            risk = 100.0

        elif temp >= 35:
            risk = 80.0

        elif temp >= 32:
            risk = 55.0

        elif temp <= 10:
            risk = 70.0

        else:
            risk = 10.0

        signals.append(risk)

    # ----------------------------
    # Humidity
    # ----------------------------

    if hum is not None:

        if hum >= 90:
            risk = 100.0

        elif hum >= 80:
            risk = 75.0

        elif hum >= 70:
            risk = 45.0

        else:
            risk = 10.0

        signals.append(risk)

    # ----------------------------
    # Thermal anomaly
    # ----------------------------

    if thermal is not None:

        signals.append(
            _clamp(
                thermal * 20.0
            )
        )

    if not signals:
        return None

    return (
        sum(signals)
        / len(signals)
    )


# ============================================================
# SPATIAL
# ============================================================

def _spatial_risk(
    infected_neighbor_count: Any = None,
    total_neighbor_count: Any = None,
    disease_density: Any = None,
    cluster_density: Any = None,
) -> Optional[float]:
    """
    Spatial evidence semantics:

        None
            = no observation

        0 with actual denominator/data
            = observed zero

    Therefore:

        _spatial_risk()
            -> None

        _spatial_risk(0, 10)
            -> 0
    """

    signals = []

    infected = _safe_float(
        infected_neighbor_count
    )

    total = _safe_float(
        total_neighbor_count
    )

    density = _safe_float(
        disease_density
    )

    cluster = _safe_float(
        cluster_density
    )

    # ----------------------------
    # Infection ratio
    # ----------------------------

    if (
        infected is not None
        and total is not None
        and total > 0
    ):

        ratio = (
            infected
            / total
        )

        signals.append(
            _clamp(
                ratio * 100.0
            )
        )

    # ----------------------------
    # Disease density
    # ----------------------------

    if density is not None:

        if 0.0 <= density <= 1.0:
            density *= 100.0

        signals.append(
            _clamp(density)
        )

    # ----------------------------
    # Cluster density
    # ----------------------------

    if cluster is not None:

        if 0.0 <= cluster <= 1.0:
            cluster *= 100.0

        signals.append(
            _clamp(cluster)
        )

    if not signals:
        return None

    return (
        sum(signals)
        / len(signals)
    )


# ============================================================
# TEMPORAL
# ============================================================

def _temporal_risk(
    risk_history: Any = None,
) -> Optional[float]:

    if not risk_history:
        return None

    values = []

    for item in risk_history:

        # History may contain raw numbers.
        if isinstance(
            item,
            (int, float),
        ):

            values.append(
                float(item)
            )

            continue

        if not isinstance(
            item,
            dict,
        ):
            continue

        value = (
            item.get("risk")
            if item.get("risk") is not None
            else item.get("risk_score")
        )

        value = _safe_float(
            value
        )

        if value is not None:
            values.append(value)

    if len(values) >= 2:

        delta = (
            values[-1]
            - values[0]
        )

        if delta >= 20:
            return 90.0

        if delta >= 8:
            return 70.0

        if delta <= -20:
            return 10.0

        if delta <= -8:
            return 25.0

        return 45.0

    if len(values) == 1:
        return 45.0

    return None


# ============================================================
# SENSOR FRESHNESS
# ============================================================

def _sensor_quality(
    sensor_freshness: Any,
) -> float:
    """
    Convert sensor freshness to quality.

    Supported:

        FRESH
        RECENT
        STALE

    or:

        numeric age in minutes
        numeric 0-1 quality
        numeric 0-100 quality
    """

    if sensor_freshness is None:
        return 1.0

    if isinstance(
        sensor_freshness,
        str,
    ):

        value = (
            sensor_freshness
            .strip()
            .upper()
        )

        if value == "FRESH":
            return 1.0

        if value == "RECENT":
            return 0.8

        if value == "STALE":
            return 0.5

        if value in {
            "VERY_STALE",
            "EXPIRED",
        }:
            return 0.2

        numeric = _safe_float(
            sensor_freshness
        )

        if numeric is None:
            return 1.0

        sensor_freshness = numeric

    value = _safe_float(
        sensor_freshness
    )

    if value is None:
        return 1.0

    # 0-1 quality
    if 0.0 <= value <= 1.0:
        return value

    # 0-100 quality
    if 1.0 < value <= 100.0:
        return value / 100.0

    # Otherwise treat as age in minutes.
    if value <= 15:
        return 1.0

    if value <= 60:
        return 0.8

    if value <= 360:
        return 0.5

    return 0.2


# ============================================================
# MAIN FUSION
# ============================================================

def calculate_field_risk(
    disease: Any = None,
    visual_confidence: Any = None,

    # Newer aliases also supported.
    prediction: Any = None,
    confidence: Any = None,

    soil_moisture: Any = None,
    temperature: Any = None,
    humidity: Any = None,
    thermal_anomaly: Any = None,

    infected_neighbor_count: Any = None,
    total_neighbor_count: Any = None,
    disease_density: Any = None,
    cluster_density: Any = None,

    risk_history: Any = None,
    history: Any = None,

    sensor_freshness: Any = None,
    image_quality_score: Any = None,

    spatial_context: Any = None,

    observation_count: Any = None,

    **kwargs: Any,
) -> Dict[str, Any]:

    # ========================================================
    # COMPATIBILITY ALIASES
    # ========================================================

    if disease is None:
        disease = prediction

    if visual_confidence is None:
        visual_confidence = confidence

    if risk_history is None:
        risk_history = history

    # ========================================================
    # SPATIAL CONTEXT
    # ========================================================

    if spatial_context is not None:

        if isinstance(
            spatial_context,
            dict,
        ):

            # Only overwrite when a value actually exists.
            if (
                spatial_context.get(
                    "infected_neighbor_count"
                )
                is not None
            ):

                infected_neighbor_count = (
                    spatial_context[
                        "infected_neighbor_count"
                    ]
                )

            if (
                spatial_context.get(
                    "total_neighbor_count"
                )
                is not None
            ):

                total_neighbor_count = (
                    spatial_context[
                        "total_neighbor_count"
                    ]
                )

            if (
                spatial_context.get(
                    "disease_density"
                )
                is not None
            ):

                disease_density = (
                    spatial_context[
                        "disease_density"
                    ]
                )

            if (
                spatial_context.get(
                    "cluster_density"
                )
                is not None
            ):

                cluster_density = (
                    spatial_context[
                        "cluster_density"
                    ]
                )

    # ========================================================
    # CALCULATE EACH EVIDENCE SOURCE
    # ========================================================

    visual = _visual_risk(
        disease,
        visual_confidence,
    )

    environmental = _environmental_risk(
        soil_moisture=soil_moisture,
        temperature=temperature,
        humidity=humidity,
        thermal_anomaly=thermal_anomaly,
    )

    spatial = _spatial_risk(
        infected_neighbor_count=(
            infected_neighbor_count
        ),
        total_neighbor_count=(
            total_neighbor_count
        ),
        disease_density=(
            disease_density
        ),
        cluster_density=(
            cluster_density
        ),
    )

    temporal = _temporal_risk(
        risk_history
    )

    # ========================================================
    # QUALITY
    # ========================================================

    visual_quality = 1.0

    if image_quality_score is not None:

        visual_quality = _clamp(
            _safe_float(
                image_quality_score,
                100.0,
            )
            / 100.0,
            0.0,
            1.0,
        )

    environmental_quality = (
        _sensor_quality(
            sensor_freshness
        )
    )

    # ========================================================
    # EVIDENCE MAP
    # ========================================================

    evidence_values = {

        "visual":
            visual,

        "environmental":
            environmental,

        "spatial":
            spatial,

        "temporal":
            temporal,
    }

    evidence_quality = {

        "visual":
            visual_quality,

        "environmental":
            environmental_quality,

        "spatial":
            1.0,

        "temporal":
            1.0,
    }

    # ========================================================
    # WEIGHT ONLY AVAILABLE EVIDENCE
    # ========================================================

    weights = {}

    weighted_sum = 0.0
    total_weight = 0.0

    for source, value in (
        evidence_values.items()
    ):

        if value is None:
            continue

        base_weight = (
            BASE_WEIGHTS[
                source
            ]
        )

        quality = _clamp(
            evidence_quality[
                source
            ],
            0.0,
            1.0,
        )

        effective_weight = (
            base_weight
            * quality
        )

        if effective_weight <= 0:
            continue

        weights[
            source
        ] = round(
            effective_weight,
            2,
        )

        weighted_sum += (
            value
            * effective_weight
        )

        total_weight += (
            effective_weight
        )

    # ========================================================
    # NO EVIDENCE
    # ========================================================

    if total_weight <= 0:

        return {

            "model_type":
                MODEL_TYPE,

            "version":
                MODEL_VERSION,

            "model_version":
                MODEL_VERSION,

            "risk_score":
                None,

            "risk_level":
                "UNKNOWN",

            "assessment_confidence":
                "LOW",

            "weights":
                {},

            "breakdown":
                {},

            "evidence_summary": {

                "available":
                    [],

                "missing":
                    [
                        "visual",
                        "environmental",
                        "spatial",
                        "temporal",
                    ],

                "quality":
                    evidence_quality,
            },

            "available_evidence":
                [],

            "missing_evidence":
                [
                    "visual",
                    "environmental",
                    "spatial",
                    "temporal",
                ],

            "contributions":
                {},

            "explanation":
                "Insufficient evidence for field-risk assessment.",
        }

    # ========================================================
    # FINAL RISK
    # ========================================================

    risk_score = (
        weighted_sum
        / total_weight
    )

    risk_score = _clamp(
        risk_score
    )

    # ========================================================
    # BREAKDOWN
    #
    # This preserves the V1.5 API expected by tests/UI.
    # ========================================================

    breakdown = {}

    contributions = {}

    for source, value in (
        evidence_values.items()
    ):

        if value is None:
            continue

        contribution = (
            value
            * weights[source]
            / total_weight
        )

        breakdown[
            source
        ] = round(
            value,
            2,
        )

        contributions[
            source
        ] = round(
            contribution,
            2,
        )

    # ========================================================
    # RISK LEVEL
    # ========================================================

    if risk_score < LOW_THRESHOLD:

        risk_level = "LOW"

    elif risk_score < MODERATE_THRESHOLD:

        risk_level = "MODERATE"

    elif risk_score < HIGH_THRESHOLD:

        risk_level = "HIGH"

    else:

        risk_level = "CRITICAL"

    # ========================================================
    # ASSESSMENT CONFIDENCE
    #
    # V1.5 semantics:
    #
    # 4 evidence sources -> HIGH
    # 2-3 -> MODERATE
    # 1 -> LOW
    # ========================================================

    available_sources = [
        source
        for source, value
        in evidence_values.items()
        if value is not None
    ]

    evidence_count = len(
        available_sources
    )

    if evidence_count >= 4:

        assessment_confidence = "HIGH"

    elif evidence_count >= 2:

        assessment_confidence = "MODERATE"

    else:

        assessment_confidence = "LOW"

    missing_sources = [
        source
        for source in BASE_WEIGHTS
        if source not in available_sources
    ]

    # ========================================================
    # EVIDENCE SUMMARY
    # ========================================================

    evidence_summary = {

        "available":
            available_sources,

        "missing":
            missing_sources,

        "quality":
            {
                source: round(
                    evidence_quality[
                        source
                    ],
                    3,
                )
                for source in BASE_WEIGHTS
            },
    }

    # ========================================================
    # EXPLANATION
    # ========================================================

    if contributions:

        strongest_source = max(
            contributions,
            key=contributions.get,
        )

        explanation = (
            f"CRAI estimated field risk at "
            f"{risk_score:.2f} ({risk_level}) "
            f"using {evidence_count} available "
            f"evidence source(s). The strongest "
            f"contribution came from "
            f"{strongest_source} evidence."
        )

    else:

        explanation = (
            "CRAI does not have enough evidence "
            "to produce a reliable field-risk assessment."
        )

    # ========================================================
    # FINAL V1.5-COMPATIBLE RESPONSE
    # ========================================================

    return {

        "model_type":
            MODEL_TYPE,

        "version":
            MODEL_VERSION,

        "model_version":
            MODEL_VERSION,

        "risk_score":
            round(
                risk_score,
                2,
            ),

        "risk_level":
            risk_level,

        "assessment_confidence":
            assessment_confidence,

        # Existing API contract.
        "weights":
            weights,

        # Existing API contract.
        "breakdown":
            breakdown,

        # Existing API contract.
        "evidence_summary":
            evidence_summary,

        # New/explicit evidence representation.
        "evidence":
            {
                source: {
                    "risk":
                        round(
                            value,
                            2,
                        ),
                    "available":
                        True,
                    "quality":
                        round(
                            evidence_quality[
                                source
                            ],
                            3,
                        ),
                }
                for source, value
                in evidence_values.items()
                if value is not None
            },

        "available_evidence":
            available_sources,

        "missing_evidence":
            missing_sources,

        "contributions":
            contributions,

        "explanation":
            explanation,
    }


# ============================================================
# PUBLIC HELPERS
# ============================================================

def calculate_visual_risk(
    prediction: Any = None,
    confidence: Any = None,
    disease: Any = None,
    visual_confidence: Any = None,
) -> Optional[float]:

    if disease is None:
        disease = prediction

    if visual_confidence is None:
        visual_confidence = confidence

    return _visual_risk(
        disease,
        visual_confidence,
    )


def calculate_environmental_risk(
    temperature: Any = None,
    humidity: Any = None,
    soil_moisture: Any = None,
    thermal_anomaly: Any = None,
) -> Optional[float]:

    return _environmental_risk(
        soil_moisture=soil_moisture,
        temperature=temperature,
        humidity=humidity,
        thermal_anomaly=thermal_anomaly,
    )


def calculate_spatial_risk(
    infected_neighbor_count: Any = None,
    total_neighbor_count: Any = None,
    disease_density: Any = None,
    cluster_density: Any = None,
) -> Optional[float]:

    return _spatial_risk(
        infected_neighbor_count=(
            infected_neighbor_count
        ),
        total_neighbor_count=(
            total_neighbor_count
        ),
        disease_density=(
            disease_density
        ),
        cluster_density=(
            cluster_density
        ),
    )


def calculate_temporal_risk(
    history: Any = None,
    risk_history: Any = None,
) -> Optional[float]:

    if risk_history is None:
        risk_history = history

    return _temporal_risk(
        risk_history
    )