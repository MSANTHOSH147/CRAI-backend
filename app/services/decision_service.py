from typing import Optional


# ============================================================
# CRAI DECISION ENGINE V2
# ============================================================
#
# Converts:
#
# Disease + Evidence + Fusion Risk
#              ↓
#       Contextual Decision
#              ↓
#       Farmer Action
#
# IMPORTANT:
# This is a decision-support layer.
# It does NOT independently diagnose disease or invent risk.
#
# The authoritative risk comes from fusion_risk_service.py.
# ============================================================


# ============================================================
# HELPERS
# ============================================================

def _safe_float(value, default=0.0):
    try:
        if value is None:
            return default

        return float(value)

    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    try:
        if value is None:
            return default

        return int(value)

    except (TypeError, ValueError):
        return default


def _upper(value, default="UNKNOWN"):
    if value is None:
        return default

    text = str(value).strip()

    return text.upper() if text else default


def _normalize_confidence(value):
    """
    Accept:

        0.91  -> 91.0
        91    -> 91.0

    Internally CRAI uses 0-100.
    """

    confidence = _safe_float(value, 0.0)

    confidence = max(
        0.0,
        confidence,
    )

    if confidence <= 1.0:
        confidence *= 100.0

    return min(
        confidence,
        100.0,
    )


def _is_disease(prediction):
    if not prediction:
        return False

    value = str(prediction).lower()

    return not any(
        token in value
        for token in (
            "healthy",
            "normal",
            "no_disease",
        )
    )


def _format_disease(prediction):
    if not prediction:
        return "Unknown crop condition"

    return (
        str(prediction)
        .replace("_", " ")
        .replace("-", " ")
        .strip()
    )


# ============================================================
# RISK BREAKDOWN HELPERS
# ============================================================

def _get_risk_breakdown(risk):
    """
    CRAI Fusion V1.5 returns:

        breakdown:
            visual: 89.18
            environmental: 43.75
            spatial: 50.0
            temporal: 10.0

    Older versions may return dictionaries.

    This helper supports both.
    """

    if not isinstance(risk, dict):
        return {}

    value = risk.get("breakdown")

    return value if isinstance(value, dict) else {}


def _get_risk_score(risk, source):
    """
    Extract the authoritative fusion score.

    IMPORTANT:
    Missing evidence is represented as None, never 0.
    A real score of 0.0 remains 0.0.
    """
    breakdown = _get_risk_breakdown(risk)
    value = breakdown.get(source)

    if isinstance(value, dict):
        value = value.get("score")

    if value is None:
        return None

    return _safe_float(value, None)


def _get_risk_source_details(
    risk,
    source,
):
    """
    Extract detailed source information when
    available.
    """

    breakdown = _get_risk_breakdown(risk)

    value = breakdown.get(source)

    if isinstance(value, dict):
        return value

    return {}


def _get_components(
    source_data,
):
    if not isinstance(
        source_data,
        dict,
    ):
        return {}

    components = source_data.get(
        "components"
    )

    if isinstance(
        components,
        dict,
    ):
        return components

    return {}


def _get_component(
    source_data,
    key,
    default=None,
):
    components = _get_components(
        source_data
    )

    if key in components:
        return components.get(key)

    return default


# ============================================================
# EVIDENCE DETAILS
# ============================================================

def _get_evidence_details(
    evidence,
    source,
):
    if not isinstance(
        evidence,
        dict,
    ):
        return {}

    details = evidence.get(
        "details"
    )

    if not isinstance(
        details,
        dict,
    ):
        return {}

    value = details.get(
        source
    )

    return (
        value
        if isinstance(value, dict)
        else {}
    )


def _derive_evidence_quality(
    evidence,
    risk,
):
    """
    Derive evidence quality without inventing data.

    Priority:

    1. Explicit evidence_quality
    2. Evidence count
    3. Fusion assessment confidence
    """

    explicit = (
        evidence.get(
            "evidence_quality"
        )
        if isinstance(
            evidence,
            dict,
        )
        else None
    )

    if explicit:
        return _upper(
            explicit
        )

    evidence_count = _safe_int(
        evidence.get(
            "evidence_count"
        )
        if isinstance(
            evidence,
            dict,
        )
        else 0
    )

    if evidence_count >= 4:
        return "HIGH"

    if evidence_count >= 2:
        return "MODERATE"

    assessment = _upper(
        risk.get(
            "assessment_confidence"
        )
        if isinstance(
            risk,
            dict,
        )
        else None
    )

    if assessment == "HIGH":
        return "HIGH"

    if assessment == "MODERATE":
        return "MODERATE"

    return "LOW"


def _derive_uncertainty(
    evidence,
    risk,
):
    explicit = (
        evidence.get(
            "uncertainty"
        )
        if isinstance(
            evidence,
            dict,
        )
        else None
    )

    if explicit:
        return _upper(
            explicit
        )

    quality = _derive_evidence_quality(
        evidence,
        risk,
    )

    if quality == "HIGH":
        return "LOW"

    if quality == "MODERATE":
        return "MODERATE"

    return "HIGH"


# ============================================================
# MAIN DECISION ENGINE
# ============================================================

def generate_decision(
    *,
    prediction: str,
    confidence: float,
    risk: Optional[dict],
    evidence: dict,
    sensor: Optional[dict] = None,
    zone_id: Optional[str] = None,
):
    """
    Generate a CRAI contextual field decision.

    IMPORTANT:

    This function NEVER recalculates field risk.

    It consumes the authoritative risk produced by
    fusion_risk_service.py.
    """

    # ========================================================
    # BASIC VALUES
    # ========================================================

    confidence = _normalize_confidence(
        confidence
    )

    risk = (
        risk
        if isinstance(
            risk,
            dict,
        )
        else {}
    )

    evidence = (
        evidence
        if isinstance(
            evidence,
            dict,
        )
        else {}
    )

    # The overall score is authoritative and must come from fusion.
    # Do not manufacture 0 when the fusion score is absent.
    risk_score = (
        _safe_float(
            risk.get("risk_score"),
            None,
        )
        if risk.get("risk_score") is not None
        else None
    )

    risk_level = _upper(
        risk.get(
            "risk_level"
        ),
        "UNKNOWN",
    )

    assessment_confidence = _upper(
        risk.get(
            "assessment_confidence"
        ),
        "UNKNOWN",
    )

    evidence_quality = (
        _derive_evidence_quality(
            evidence,
            risk,
        )
    )

    uncertainty = (
        _derive_uncertainty(
            evidence,
            risk,
        )
    )

    # ========================================================
    # ADDITIONAL EVIDENCE GATE
    # ========================================================

    additional_evidence_required = bool(
        evidence.get(
            "additional_evidence_required",
            False,
        )
    )

    requested = evidence.get(
        "requested_evidence",
        [],
    )

    if not isinstance(
        requested,
        list,
    ):
        requested = [requested]

    requested = [
        item
        for item in requested
        if item
    ]

    if additional_evidence_required:

        requested_labels = [
            str(item).replace(
                "_",
                " ",
            )
            for item in requested
        ]

        requested_text = (
            ", ".join(
                requested_labels
            )
            if requested_labels
            else "fresh field evidence"
        )

        return {
            "ready": False,

            "action":
                "COLLECT_ADDITIONAL_EVIDENCE",

            "adaptive_action":
                "REQUEST_SENSOR"
                if any(
                    "SENSOR" in str(item).upper()
                    or "ENVIRONMENT" in str(item).upper()
                    for item in requested
                )
                else "REQUEST_EVIDENCE",

            "priority":
                "HIGH",

            "title":
                "Additional field evidence required",

            "message": (
                "CRAI has detected a possible crop "
                "risk, but the available evidence is "
                "not sufficient for a complete field "
                "assessment."
            ),

            "reasons": [
                (
                    f"Visual model confidence: "
                    f"{confidence:.1f}%."
                ),
                (
                    f"Evidence quality: "
                    f"{evidence_quality}."
                ),
                (
                    f"Assessment uncertainty: "
                    f"{uncertainty}."
                ),
                (
                    f"CRAI is requesting: "
                    f"{requested_text}."
                ),
            ],

            "requested_evidence":
                requested,

            "recommended_steps": [
                (
                    f"Collect fresh "
                    f"{requested_text.lower()}."
                ),
                (
                    "Keep the evidence linked to "
                    "the same field zone."
                ),
                (
                    "Re-run CRAI analysis after "
                    "the new evidence arrives."
                ),
            ],

            "context": {
                "disease":
                    prediction,

                "disease_confidence":
                    round(
                        confidence,
                        2,
                    ),

                "risk_score":
                    round(
                        risk_score,
                        2,
                    ),

                "risk_level":
                    risk_level,

                "assessment_confidence":
                    assessment_confidence,

                "evidence_quality":
                    evidence_quality,

                "uncertainty":
                    uncertainty,
            },
        }

    # ========================================================
    # SENSOR VALUES
    # ========================================================

    soil_moisture = None
    temperature = None
    humidity = None

    if isinstance(
        sensor,
        dict,
    ):

        soil_moisture = (
            _safe_float(
                sensor.get(
                    "soil_moisture"
                ),
                None,
            )
            if sensor.get(
                "soil_moisture"
            ) is not None
            else None
        )

        temperature = (
            _safe_float(
                sensor.get(
                    "temperature"
                ),
                None,
            )
            if sensor.get(
                "temperature"
            ) is not None
            else None
        )

        humidity = (
            _safe_float(
                sensor.get(
                    "humidity"
                ),
                None,
            )
            if sensor.get(
                "humidity"
            ) is not None
            else None
        )

    # ========================================================
    # AUTHORITATIVE FUSION SCORES
    # ========================================================

    visual_score = _get_risk_score(
        risk,
        "visual",
    )

    environmental_score = _get_risk_score(
        risk,
        "environmental",
    )

    spatial_score = _get_risk_score(
        risk,
        "spatial",
    )

    temporal_score = _get_risk_score(
        risk,
        "temporal",
    )

    # ========================================================
    # ENVIRONMENT DETAILS
    # ========================================================

    environmental_risk_data = (
        _get_risk_source_details(
            risk,
            "environmental",
        )
    )

    environmental_components = (
        _get_components(
            environmental_risk_data
        )
    )

    if soil_moisture is None:

        value = environmental_components.get(
            "soil_moisture"
        )

        if value is not None:
            soil_moisture = _safe_float(
                value,
                None,
            )

    if temperature is None:

        value = environmental_components.get(
            "temperature"
        )

        if value is not None:
            temperature = _safe_float(
                value,
                None,
            )

    if humidity is None:

        value = environmental_components.get(
            "humidity"
        )

        if value is not None:
            humidity = _safe_float(
                value,
                None,
            )

    # ========================================================
    # SPATIAL DETAILS
    # ========================================================

    spatial_risk_data = (
        _get_risk_source_details(
            risk,
            "spatial",
        )
    )

    spatial_components = (
        _get_components(
            spatial_risk_data
        )
    )

    spatial_evidence = (
        _get_evidence_details(
            evidence,
            "spatial",
        )
    )

    # Current evidence_service exposes spatial evidence as
    # `spatial_evidence`, while some older versions used
    # `details.spatial`. Support both without inventing data.
    if not spatial_evidence:
        candidate = evidence.get("spatial_evidence")
        if isinstance(candidate, dict):
            spatial_evidence = candidate

    infected_value = spatial_components.get(
        "infected_neighbors"
    )
    if infected_value is None:
        infected_value = spatial_evidence.get(
            "infected_neighbors"
        )

    total_value = spatial_components.get(
        "total_neighbors"
    )
    if total_value is None:
        total_value = spatial_evidence.get(
            "nearby_observations",
            spatial_evidence.get("total_observations")
        )

    infected_observed_zones = (
        _safe_int(infected_value, 0)
        if infected_value is not None
        else 0
    )

    total_observed_zones = (
        _safe_int(total_value, 0)
        if total_value is not None
        else 0
    )

    infection_ratio = (
        spatial_components.get(
            "infection_ratio"
        )
    )

    if infection_ratio is None:

        infection_ratio = (
            spatial_evidence.get(
                "infection_ratio"
            )
        )

    infection_ratio = _safe_float(
        infection_ratio,
        0.0,
    )

    # ========================================================
    # TEMPORAL DETAILS
    # ========================================================

    temporal_risk_data = (
        _get_risk_source_details(
            risk,
            "temporal",
        )
    )

    temporal_evidence = (
        _get_evidence_details(
            evidence,
            "temporal",
        )
    )

    if not temporal_evidence:
        candidate = evidence.get("temporal_evidence")
        if isinstance(candidate, dict):
            temporal_evidence = candidate

    temporal_trend = _upper(
        temporal_risk_data.get(
            "trend",
            temporal_evidence.get(
                "trend",
                "UNKNOWN",
            ),
        ),
        "UNKNOWN",
    )

    temporal_reason = str(
        temporal_risk_data.get(
            "reason"
        )
        or temporal_evidence.get(
            "reason"
        )
        or ""
    )

    # ========================================================
    # SIGNALS
    # ========================================================

    disease_detected = _is_disease(
        prediction
    )

    disease_name = _format_disease(
        prediction
    )

    strong_visual_signal = (
        disease_detected
        and visual_score >= 85
    )

    moderate_visual_signal = (
        disease_detected
        and visual_score >= 60
    )

    very_dry_soil = (
        soil_moisture is not None
        and soil_moisture < 20
    )

    dry_soil = (
        soil_moisture is not None
        and soil_moisture < 30
    )

    elevated_temperature = (
        temperature is not None
        and temperature >= 35
    )

    extreme_temperature = (
        temperature is not None
        and temperature >= 40
    )

    high_humidity = (
        humidity is not None
        and humidity >= 80
    )

    very_high_humidity = (
        humidity is not None
        and humidity >= 90
    )

    significant_environmental_stress = (
        (
            environmental_score is not None
            and environmental_score >= 70
        )
        or very_dry_soil
        or elevated_temperature
        or high_humidity
    )

    spatial_available = (
        spatial_score is not None
        and (
            "spatial"
            in risk.get(
                "available_evidence",
                [],
            )
        )
    )

    strong_spatial_signal = (
        (
            spatial_score is not None
            and spatial_score >= 70
        )
        or (
            infection_ratio is not None
            and infection_ratio >= 50
        )
    )

    rapidly_increasing = (
        "INCREASING"
        in temporal_trend
        and temporal_score >= 70
    )

    decreasing_trend = (
        "DECREASING"
        in temporal_trend
        or "DECLINING"
        in temporal_trend
    )

    stable_trend = (
        "STABLE"
        in temporal_trend
    )

    # ========================================================
    # PRIORITY
    # ========================================================

    if risk_level == "CRITICAL":

        priority = "CRITICAL"

    elif (
        risk_level == "HIGH"
        and (
            strong_visual_signal
            or strong_spatial_signal
            or significant_environmental_stress
            or rapidly_increasing
        )
    ):

        priority = "HIGH"

    elif (
        disease_detected
        and rapidly_increasing
    ):

        priority = "HIGH"

    elif risk_level == "MODERATE":

        priority = "MEDIUM"

    elif disease_detected:

        priority = "MEDIUM"

    else:

        priority = "LOW"

    # ========================================================
    # REASONS
    # ========================================================

    reasons = []

    if disease_detected:

        if strong_visual_signal:

            reasons.append(
                f"Strong visual disease signal: "
                f"{disease_name} detected with "
                f"{confidence:.1f}% model confidence."
            )

        elif moderate_visual_signal:

            reasons.append(
                f"Visual model indicates "
                f"{disease_name} with "
                f"{confidence:.1f}% model confidence."
            )

        else:

            reasons.append(
                f"Visual model indicates "
                f"{disease_name}, but confidence "
                f"is limited ({confidence:.1f}%)."
            )

    # ========================================================
    # ENVIRONMENT REASONS
    # ========================================================

    if very_dry_soil:

        reasons.append(
            f"Soil moisture is very low "
            f"({soil_moisture:.1f}%)."
        )

    elif dry_soil:

        reasons.append(
            f"Soil moisture is relatively low "
            f"({soil_moisture:.1f}%)."
        )

    if extreme_temperature:

        reasons.append(
            f"Field temperature is very high "
            f"({temperature:.1f}°C)."
        )

    elif elevated_temperature:

        reasons.append(
            f"Field temperature is elevated "
            f"({temperature:.1f}°C)."
        )

    if very_high_humidity:

        reasons.append(
            f"Humidity is very high "
            f"({humidity:.1f}%)."
        )

    elif high_humidity:

        reasons.append(
            f"Humidity is high "
            f"({humidity:.1f}%)."
        )

    # ========================================================
    # SPATIAL REASONS
    # ========================================================

    if strong_spatial_signal:

        if total_observed_zones > 0:

            reasons.append(
                f"{infected_observed_zones} of "
                f"{total_observed_zones} observed zones "
                f"show disease signals."
            )

        else:

            reasons.append(
                "Spatial evidence indicates "
                "an elevated disease-spread signal."
            )

    # ========================================================
    # TEMPORAL REASONS
    # ========================================================

    if rapidly_increasing:

        reasons.append(
            "Recent field-risk observations "
            "indicate increasing risk."
        )

    elif decreasing_trend:

        reasons.append(
            temporal_reason
            if temporal_reason
            else
            "Recent field-risk observations "
            "indicate decreasing risk."
        )

    elif stable_trend:

        reasons.append(
            "Recent field-risk observations "
            "are relatively stable."
        )

    # ========================================================
    # OVERALL RISK
    # ========================================================

    if risk_score is not None:
        reasons.append(
            f"CRAI fused field risk is "
            f"{risk_level} at {risk_score:.2f}."
        )
    else:
        reasons.append(
            f"CRAI fused field risk level is "
            f"{risk_level}."
        )

    # ========================================================
    # ACTIONS
    # ========================================================

    actions = []

    observed_zone_label = (
        f"Zone {zone_id}"
        if zone_id
        else "the observed zone"
    )

    if priority == "CRITICAL":

        actions.append(
            f"Inspect symptomatic plants in "
            f"{observed_zone_label} as soon as possible."
        )

        if strong_spatial_signal:

            actions.append(
                "Inspect other affected observed "
                "zones for signs of spread."
            )

        if very_dry_soil:

            actions.append(
                f"Verify irrigation because soil "
                f"moisture is {soil_moisture:.1f}%."
            )

        elif dry_soil:

            actions.append(
                f"Check irrigation requirements at "
                f"{soil_moisture:.1f}% soil moisture."
            )

        if high_humidity:

            actions.append(
                "Inspect foliage for moisture-related "
                "disease progression."
            )

        if elevated_temperature:

            actions.append(
                "Inspect plants for heat or water stress."
            )

        actions.append(
            "Re-observe the zone after intervention."
        )

    elif priority == "HIGH":

        actions.append(
            f"Inspect symptomatic plants in "
            f"{observed_zone_label}."
        )

        if strong_spatial_signal:

            actions.append(
                "Inspect affected observed zones "
                "for possible disease spread."
            )

        if dry_soil:

            actions.append(
                f"Check irrigation at "
                f"{soil_moisture:.1f}% soil moisture."
            )

        if elevated_temperature:

            actions.append(
                "Monitor plants for heat or water stress."
            )

        if high_humidity:

            actions.append(
                "Inspect foliage for moisture-related "
                "disease progression."
            )

        if rapidly_increasing:

            actions.append(
                "Increase observation frequency because "
                "recent field risk is increasing."
            )

        else:

            actions.append(
                "Re-observe this zone after inspection."
            )

    elif priority == "MEDIUM":

        if disease_detected:

            actions.append(
                f"Inspect symptomatic plants in "
                f"{observed_zone_label}."
            )

        else:

            actions.append(
                "Continue routine crop inspection."
            )

        if strong_spatial_signal:

            actions.append(
                "Check other affected observed zones."
            )

        if dry_soil:

            actions.append(
                f"Check irrigation requirements at "
                f"{soil_moisture:.1f}% soil moisture."
            )

        if rapidly_increasing:

            actions.append(
                "Increase monitoring frequency."
            )

        else:

            actions.append(
                "Re-observe the zone soon."
            )

    else:

        actions.append(
            f"Continue targeted monitoring of "
            f"{observed_zone_label}."
        )

        actions.append(
            "Re-observe if crop symptoms or "
            "field conditions change."
        )

    # ========================================================
    # TITLE
    # ========================================================

    if priority == "CRITICAL":

        title = (
            "Immediate field attention recommended"
        )

    elif priority == "HIGH":

        title = (
            "High-priority field inspection"
        )

    elif priority == "MEDIUM":

        title = (
            "Monitor and re-observe"
        )

    else:

        title = (
            "Continue targeted monitoring"
        )

    # ========================================================
    # MESSAGE
    # ========================================================

    message_parts = []

    if disease_detected:

        message_parts.append(
            f"{disease_name} was detected "
            f"with {confidence:.1f}% model confidence."
        )

    environmental_summary = []

    if soil_moisture is not None:
        environmental_summary.append(
            f"soil moisture {soil_moisture:.1f}%"
        )

    if temperature is not None:
        environmental_summary.append(
            f"temperature {temperature:.1f}°C"
        )

    if humidity is not None:
        environmental_summary.append(
            f"humidity {humidity:.1f}%"
        )

    if environmental_summary:

        message_parts.append(
            "Field conditions: "
            + ", ".join(
                environmental_summary
            )
            + "."
        )

    if strong_spatial_signal:

        if total_observed_zones > 0:

            message_parts.append(
                f"{infected_observed_zones} of "
                f"{total_observed_zones} observed zones "
                f"show disease signals."
            )

    if rapidly_increasing:

        message_parts.append(
            "Recent risk observations are increasing."
        )

    elif decreasing_trend:

        message_parts.append(
            "Recent risk observations are decreasing."
        )

    elif stable_trend:

        message_parts.append(
            "Recent risk observations are relatively stable."
        )

    if risk_score is not None:
        message_parts.append(
            f"CRAI fused field risk is "
            f"{risk_level} at {risk_score:.2f}."
        )
    else:
        message_parts.append(
            f"CRAI fused field risk level is "
            f"{risk_level}."
        )

    message = " ".join(
        message_parts
    )

    # ========================================================
    # FINAL ACTION
    # ========================================================

    if priority in {
        "CRITICAL",
        "HIGH",
    }:

        action = (
            "PRIORITIZE_INSPECTION"
        )

    elif priority == "MEDIUM":

        action = (
            "MONITOR_AND_REOBSERVE"
        )

    else:

        action = (
            "CONTINUE_MONITORING"
        )

    # ========================================================
    # RETURN
    # ========================================================
    #
    # `risk` remains the single authoritative source for
    # the four fusion scores. This context is a presentation
    # projection only.
    # ========================================================

    return {

        "ready": True,

        "action": action,

        "priority": priority,

        "title": title,

        "message": message,

        "reasons": reasons,

        "recommended_steps": actions,

        "context": {

            "disease":
                prediction,

            "disease_confidence":
                round(
                    confidence,
                    2,
                ),

            "risk_score":
                round(
                    risk_score,
                    2,
                ),

            "risk_level":
                risk_level,

            "assessment_confidence":
                assessment_confidence,

            "visual_score":
                (
                    round(visual_score, 2)
                    if visual_score is not None
                    else None
                ),

            "environmental_score":
                (
                    round(environmental_score, 2)
                    if environmental_score is not None
                    else None
                ),

            "spatial_score":
                (
                    round(spatial_score, 2)
                    if spatial_score is not None
                    else None
                ),

            "temporal_score":
                (
                    round(temporal_score, 2)
                    if temporal_score is not None
                    else None
                ),

            "temporal_trend":
                temporal_trend,

            "infected_observed_zones":
                infected_observed_zones,

            "total_observed_zones":
                total_observed_zones,

            "infection_ratio":
                round(
                    infection_ratio,
                    2,
                ),

            "soil_moisture":
                soil_moisture,

            "temperature":
                temperature,

            "humidity":
                humidity,

            "evidence_quality":
                evidence_quality,

            "uncertainty":
                uncertainty,

            "zone_id":
                zone_id,
        },
    }