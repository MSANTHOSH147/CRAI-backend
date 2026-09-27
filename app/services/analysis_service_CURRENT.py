"""
CRAI Analysis Service V1.7

Complete field-observation pipeline:

Image / Disease AI
        ↓
Image Quality
        ↓
Evidence Evaluation
        ↓
Adaptive Evidence Gate
        ↓
Multimodal Evidence Fusion
        ↓
Field Risk
        ↓
Decision Engine
        ↓
Judge Intelligence / Provenance
        ↓
Optional Local Qwen3 Advisory
        ↓
Observation History

Important:
- Missing evidence remains missing.
- Stale environmental evidence is not treated as usable.
- Sensor timestamps are passed to the evidence engine.
- No unsupported sensor_available argument is passed.
- Risk is calculated only after the evidence gate accepts the observation.
- Judge intelligence NEVER recalculates risk.
- Judge intelligence only exposes deterministic reasoning/provenance.
- Qwen3 is advisory-only and cannot change CRAI risk or decision.
- Initial farmer-facing advisory languages:
    English
    Tamil
    Hindi
"""

from typing import Optional, Any
from datetime import datetime, timezone


from app.services.evidence_service import (
    evaluate_evidence,
)

from app.services.fusion_risk_service import (
    calculate_field_risk,
)

from app.services.decision_service import (
    generate_decision,
)

from app.services.llm_service import (
    generate_local_advisory,
)

from app.services.judge_intelligence_service import (
    build_judge_intelligence,
)


# ============================================================
# CONSTANTS
# ============================================================

SUPPORTED_ADVISORY_LANGUAGES = {
    "english": "English",
    "tamil": "Tamil",
    "hindi": "Hindi",
}


# ============================================================
# HELPERS
# ============================================================

def _safe_float(
    value: Any,
    default: Optional[float] = 0.0,
) -> float:
    """
    Safely convert a value to float.
    """

    try:

        if value is None:
            return default

        return float(value)

    except (
        TypeError,
        ValueError,
    ):

        return default


def _extract_sensor_value(
    sensor: Optional[dict],
    *keys: str,
) -> Optional[float]:
    """
    Extract a numeric sensor value using
    multiple possible field names.
    """

    if not sensor:
        return None

    for key in keys:

        value = sensor.get(key)

        if value is None:
            continue

        try:

            return float(value)

        except (
            TypeError,
            ValueError,
        ):

            continue

    return None


def _parse_sensor_timestamp(
    sensor: Optional[dict],
):
    """
    Parse sensor timestamp into a datetime.

    Supports:
        datetime
        ISO string
        Z suffix
        timezone-aware values
        timezone-naive values
    """

    if not sensor:
        return None

    value = None

    for key in (
        "timestamp",
        "recorded_at",
        "created_at",
        "sensor_timestamp",
    ):

        if sensor.get(key) is not None:

            value = sensor.get(key)

            break

    if value is None:
        return None

    if isinstance(
        value,
        datetime,
    ):

        return value

    try:

        text = str(
            value
        ).strip()

        if not text:
            return None

        if text.endswith("Z"):

            text = (
                text[:-1]
                + "+00:00"
            )

        parsed = datetime.fromisoformat(
            text
        )

        return parsed

    except (
        TypeError,
        ValueError,
    ):

        return None


def _normalize_datetime(
    value: Optional[datetime],
) -> Optional[datetime]:
    """
    Convert a datetime to timezone-aware UTC.
    """

    if value is None:
        return None

    if value.tzinfo is None:

        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def _get_evidence_detail(
    evidence: Optional[dict],
    name: str,
) -> dict:
    """
    Safely retrieve one evidence component.
    """

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
        name
    )

    if isinstance(
        value,
        dict,
    ):

        return value

    return {}


def _get_evidence_quality(
    evidence: Optional[dict],
    name: str,
) -> float:
    """
    Safely retrieve one evidence quality score.
    """

    if not isinstance(
        evidence,
        dict,
    ):

        return 0.0

    quality = evidence.get(
        "quality"
    )

    if not isinstance(
        quality,
        dict,
    ):

        return 0.0

    return _safe_float(
        quality.get(name),
        0.0,
    )


def _normalize_advisory_language(
    language: Optional[str],
) -> str:
    """
    CRAI initially supports only:

        English
        Tamil
        Hindi

    Unknown languages safely fall back to English.
    """

    if language is None:

        return "English"

    key = str(
        language
    ).strip().lower()

    return SUPPORTED_ADVISORY_LANGUAGES.get(
        key,
        "English",
    )


# ============================================================
# MAIN ANALYSIS PIPELINE
# ============================================================

def analyze_field_observation(
    *,
    prediction: str,
    confidence: float,

    crop: str = "Tomato",
    growth_stage: str = "Vegetative",

    temperature: Optional[float] = None,
    humidity: Optional[float] = None,
    thermal_anomaly: Optional[float] = None,

    infected_neighbor_count: Optional[int] = None,
    total_neighbor_count: Optional[int] = None,

    disease_density: Optional[float] = None,
    cluster_density: Optional[float] = None,

    observation_count: int = 1,

    sensor: Optional[dict] = None,
    spatial_context: Optional[dict] = None,
    history: Optional[list] = None,

    second_image_available: bool = False,
    thermal_available: bool = False,

    image_quality: Optional[dict] = None,

    advisory_language: str = "English",
):
    """
    Run the complete CRAI field-observation analysis.

    Flow:

        visual AI
            ↓
        image quality
            ↓
        evidence engine
            ↓
        adaptive evidence gate
            ↓
        fusion risk
            ↓
        decision
            ↓
        judge intelligence
            ↓
        optional Qwen3 advisory
    """

    # ========================================================
    # 1. NORMALIZE BASIC INPUTS
    # ========================================================

    prediction = (
        str(prediction)
        if prediction is not None
        else "Unknown"
    )

    confidence = _safe_float(
        confidence,
        0.0,
    )

    temperature_value = (
        _extract_sensor_value(
            sensor,
            "temperature",
            "temp",
        )
    )

    humidity_value = (
        _extract_sensor_value(
            sensor,
            "humidity",
            "relative_humidity",
            "rh",
        )
    )

    soil_moisture_value = (
        _extract_sensor_value(
            sensor,
            "soil_moisture",
            "soil_moisture_percent",
            "moisture",
        )
    )

    effective_temperature = (
        temperature_value
        if temperature_value is not None
        else (
            _safe_float(
                temperature,
                None,
            )
            if temperature is not None
            else None
        )
    )

    effective_humidity = (
        humidity_value
        if humidity_value is not None
        else (
            _safe_float(
                humidity,
                None,
            )
            if humidity is not None
            else None
        )
    )

    effective_thermal_anomaly = (
        _safe_float(
            thermal_anomaly,
            None,
        )
        if thermal_anomaly is not None
        else None
    )

    advisory_language = (
        _normalize_advisory_language(
            advisory_language
        )
    )

    # ========================================================
    # 2. SENSOR TIMESTAMP
    # ========================================================

    sensor_timestamp = (
        _parse_sensor_timestamp(
            sensor
        )
    )

    sensor_timestamp = (
        _normalize_datetime(
            sensor_timestamp
        )
    )

    # ========================================================
    # 3. EVIDENCE EVALUATION
    # ========================================================

    evidence = evaluate_evidence(

        prediction=prediction,

        confidence=confidence,

        sensor=sensor,

        sensor_timestamp=sensor_timestamp,

        spatial_context=spatial_context,

        history=history,

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

        second_image_available=(
            second_image_available
        ),

        thermal_available=(
            thermal_available
        ),
    )

    # ========================================================
    # 4. IMAGE QUALITY OVERRIDE
    # ========================================================
    #
    # Bad image must never become reliable
    # visual evidence.
    #
    # Judge intelligence is still returned because
    # the judge should be able to see WHY CRAI
    # rejected the image.
    # ========================================================

    if isinstance(
        image_quality,
        dict,
    ):

        quality_status = str(
            image_quality.get(
                "status",
                "",
            )
        ).upper()

        if quality_status == (
            "RETAKE_REQUIRED"
        ):

            messages = image_quality.get(
                "messages",
                [],
            )

            if not isinstance(
                messages,
                list,
            ):

                messages = [
                    str(messages)
                ]

            reason = (
                messages[0]
                if messages
                else (
                    "Image quality is "
                    "insufficient for reliable "
                    "visual analysis."
                )
            )

            image_decision = {

                "ready":
                    False,

                "action":
                    "REQUEST_IMAGE",

                "adaptive_action":
                    "REQUEST_IMAGE",

                "priority":
                    "HIGH",

                "title":
                    "Retake image",

                "reason":
                    reason,

                "requested_evidence":
                    [
                        "RETAKE_IMAGE"
                    ],
            }

            judge_intelligence = (
                build_judge_intelligence(

                    disease={
                        "prediction":
                            prediction,

                        "confidence":
                            round(
                                confidence,
                                2,
                            ),
                    },

                    evidence=evidence,

                    risk=None,

                    decision=image_decision,

                    context={

                        "crop":
                            crop,

                        "growth_stage":
                            growth_stage,

                        "observation_count":
                            observation_count,

                        "sensor": {

                            "available":
                                bool(sensor),

                            "device_id":
                                (
                                    sensor.get(
                                        "device_id"
                                    )
                                    if isinstance(
                                        sensor,
                                        dict,
                                    )
                                    else None
                                ),

                            "soil_moisture":
                                soil_moisture_value,

                            "temperature":
                                temperature_value,

                            "humidity":
                                humidity_value,

                            "timestamp":
                                (
                                    sensor_timestamp.isoformat()
                                    if sensor_timestamp
                                    else None
                                ),

                        },

                    },

                )
            )

            return {

                "status":
                    "ADDITIONAL_EVIDENCE_REQUIRED",

                "disease": {

                    "prediction":
                        prediction,

                    "confidence":
                        round(
                            confidence,
                            2,
                        ),
                },

                "image_quality":
                    image_quality,

                "evidence":
                    evidence,

                "risk":
                    None,

                "decision":
                    image_decision,

                "adaptive_evidence": {

                    "action":
                        "REQUEST_IMAGE",

                    "priority":
                        "HIGH",

                    "reason":
                        reason,

                    "requested_evidence":
                        [
                            "RETAKE_IMAGE"
                        ],

                    "decision_ready":
                        False,

                },

                "judge_intelligence":
                    judge_intelligence,

                "advisory":
                    None,

                "context": {

                    "crop":
                        crop,

                    "growth_stage":
                        growth_stage,

                    "observation_count":
                        observation_count,

                },

            }

    # ========================================================
    # 5. ADAPTIVE EVIDENCE GATE
    # ========================================================

    additional_required = bool(
        evidence.get(
            "additional_evidence_required",
            False,
        )
    )

    if additional_required:

        adaptive = evidence.get(
            "adaptive",
            {},
        )

        if not isinstance(
            adaptive,
            dict,
        ):

            adaptive = {}

        requested_evidence = (
            evidence.get(
                "requested_evidence",
                [],
            )
        )

        if not isinstance(
            requested_evidence,
            list,
        ):

            requested_evidence = [
                requested_evidence
            ]

        requested_evidence = [
            item
            for item in requested_evidence
            if item
        ]

        adaptive_action = (
            adaptive.get(
                "action",
                "REQUEST_ADDITIONAL_EVIDENCE",
            )
        )

        adaptive_reason = (
            adaptive.get(
                "reason"
            )
            or
            "Additional field evidence is required."
        )

        adaptive_priority = (
            adaptive.get(
                "priority",
                "MEDIUM",
            )
        )

        additional_decision = {

            "ready":
                False,

            "action":
                "COLLECT_ADDITIONAL_EVIDENCE",

            "adaptive_action":
                adaptive_action,

            "priority":
                adaptive_priority,

            "title":
                "Additional field evidence required",

            "reason":
                adaptive_reason,

            "requested_evidence":
                requested_evidence,

        }

        # ----------------------------------------------------
        # Judge intelligence MUST exist even before
        # risk calculation.
        #
        # This is important because CRAI intentionally
        # refuses to calculate risk when evidence is stale
        # or incomplete.
        # ----------------------------------------------------

        judge_intelligence = (
            build_judge_intelligence(

                disease={

                    "prediction":
                        prediction,

                    "confidence":
                        round(
                            confidence,
                            2,
                        ),

                },

                evidence=evidence,

                risk=None,

                decision=additional_decision,

                context={

                    "crop":
                        crop,

                    "growth_stage":
                        growth_stage,

                    "observation_count":
                        observation_count,

                    "sensor": {

                        "available":
                            bool(sensor),

                        "device_id":
                            (
                                sensor.get(
                                    "device_id"
                                )
                                if isinstance(
                                    sensor,
                                    dict,
                                )
                                else None
                            ),

                        "soil_moisture":
                            soil_moisture_value,

                        "temperature":
                            temperature_value,

                        "humidity":
                            humidity_value,

                        "timestamp":
                            (
                                sensor_timestamp.isoformat()
                                if sensor_timestamp
                                else None
                            ),

                        "freshness":
                            (
                                adaptive.get(
                                    "sensor_freshness"
                                )
                                or
                                evidence.get(
                                    "sensor_freshness"
                                )
                            ),

                        "age_minutes":
                            (
                                adaptive.get(
                                    "sensor_age_minutes"
                                )
                                or
                                evidence.get(
                                    "sensor_age_minutes"
                                )
                            ),

                    },

                    "spatial": {

                        "available":
                            bool(
                                spatial_context
                            ),

                        "infected_neighbors":
                            infected_neighbor_count,

                        "total_observed_zones":
                            total_neighbor_count,

                    },

                    "temporal": {

                        "available":
                            bool(history),

                        "observation_count":
                            (
                                len(history)
                                if history
                                else 0
                            ),

                    },

                },

            )
        )

        return {

            "status":
                "ADDITIONAL_EVIDENCE_REQUIRED",

            "disease": {

                "prediction":
                    prediction,

                "confidence":
                    round(
                        confidence,
                        2,
                    ),

            },

            "image_quality":
                image_quality,

            "evidence":
                evidence,

            "risk":
                None,

            "decision":
                additional_decision,

            "adaptive_evidence": {

                "action":
                    adaptive_action,

                "priority":
                    adaptive_priority,

                "reason":
                    adaptive_reason,

                "requested_evidence":
                    requested_evidence,

                "decision_ready":
                    False,

            },

            "judge_intelligence":
                judge_intelligence,

            "advisory":
                None,

            "context": {

                "crop":
                    crop,

                "growth_stage":
                    growth_stage,

                "observation_count":
                    observation_count,

            },

        }

    # ========================================================
    # 6. EXTRACT FUSION INPUTS
    # ========================================================

    spatial_infected = (
        infected_neighbor_count
    )

    spatial_total = (
        total_neighbor_count
    )

    if isinstance(
        spatial_context,
        dict,
    ):

        if spatial_context.get(
            "infected_neighbors"
        ) is not None:

            spatial_infected = (
                spatial_context.get(
                    "infected_neighbors"
                )
            )

        if spatial_context.get(
            "nearby_observations"
        ) is not None:

            spatial_total = (
                spatial_context.get(
                    "nearby_observations"
                )
            )

    # --------------------------------------------------------
    # Sensor values
    # --------------------------------------------------------

    soil_moisture = (
        soil_moisture_value
    )

    temperature_for_fusion = (
        temperature_value
    )

    humidity_for_fusion = (
        humidity_value
    )

    # --------------------------------------------------------
    # Missing sensor evidence remains None.
    # --------------------------------------------------------

    if sensor is None:

        temperature_for_fusion = None
        humidity_for_fusion = None
        soil_moisture = None

    # ========================================================
    # 7. SENSOR FRESHNESS
    # ========================================================

    environmental_detail = (
        _get_evidence_detail(
            evidence,
            "environmental",
        )
    )

    sensor_age_minutes = (
        environmental_detail.get(
            "age_minutes"
        )
    )

    sensor_freshness = (
        environmental_detail.get(
            "status"
        )
    )

    sensor_usable = (
        environmental_detail.get(
            "usable"
        )
    )

    # ========================================================
    # 8. IMAGE QUALITY SCORE
    # ========================================================

    image_quality_score = None

    if isinstance(
        image_quality,
        dict,
    ):

        image_quality_score = (
            _safe_float(
                image_quality.get(
                    "quality_score"
                ),
                0.0,
            )
        )

    # ========================================================
    # 9. FIELD RISK FUSION
    # ========================================================

    risk = calculate_field_risk(

        prediction=prediction,

        confidence=confidence,

        soil_moisture=soil_moisture,

        temperature=temperature_for_fusion,

        humidity=humidity_for_fusion,

        thermal_anomaly=(
            effective_thermal_anomaly
        ),

        infected_neighbor_count=(
            spatial_infected
        ),

        total_neighbor_count=(
            spatial_total
        ),

        disease_density=(
            disease_density
        ),

        cluster_density=(
            cluster_density
        ),

        observation_count=(
            observation_count
        ),

        history=(
            history
        ),

        image_quality_score=(
            image_quality_score
        ),

        sensor_age_minutes=(
            sensor_age_minutes
        ),

        sensor_freshness=(
            sensor_freshness
        ),

        sensor_usable=(
            sensor_usable
        ),
    )

    # ========================================================
    # 10. DECISION ENGINE
    # ========================================================

    decision = generate_decision(

        prediction=prediction,

        confidence=confidence,

        risk=risk,

        evidence=evidence,

        sensor=sensor,

        zone_id=(
            spatial_context.get(
                "zone_id"
            )
            if isinstance(
                spatial_context,
                dict,
            )
            else None
        ),
    )

    # ========================================================
    # 11. FINAL EVIDENCE SUMMARY
    # ========================================================

    available = evidence.get(
        "available",
        {},
    )

    if not isinstance(
        available,
        dict,
    ):

        available = {}

    evidence_count = sum(
        1
        for value in available.values()
        if bool(value)
    )

    evidence_quality = (
        evidence.get(
            "evidence_quality"
        )
    )

    if evidence_quality is None:

        quality_values = [

            _get_evidence_quality(
                evidence,
                name,
            )

            for name in (
                "visual",
                "environmental",
                "spatial",
                "temporal",
            )

            if available.get(
                name
            )

        ]

        if quality_values:

            average_quality = (
                sum(
                    quality_values
                )
                /
                len(
                    quality_values
                )
            )

            if average_quality >= 0.85:

                evidence_quality = (
                    "HIGH"
                )

            elif average_quality >= 0.60:

                evidence_quality = (
                    "MODERATE"
                )

            else:

                evidence_quality = (
                    "LOW"
                )

        else:

            evidence_quality = "LOW"

    # ========================================================
    # 12. JUDGE INTELLIGENCE
    # ========================================================
    #
    # This layer ONLY exposes the reasoning already
    # produced by CRAI.
    #
    # It does NOT calculate a new risk.
    # ========================================================

    judge_intelligence = (
        build_judge_intelligence(

            disease={

                "prediction":
                    prediction,

                "confidence":
                    round(
                        confidence,
                        2,
                    ),

            },

            evidence=evidence,

            risk=risk,

            decision=decision,

            context={

                "crop":
                    crop,

                "growth_stage":
                    growth_stage,

                "observation_count":
                    observation_count,

                "sensor": {

                    "available":
                        bool(sensor),

                    "device_id":
                        (
                            sensor.get(
                                "device_id"
                            )
                            if isinstance(
                                sensor,
                                dict,
                            )
                            else None
                        ),

                    "soil_moisture":
                        soil_moisture,

                    "temperature":
                        temperature_for_fusion,

                    "humidity":
                        humidity_for_fusion,

                    "timestamp":
                        (
                            sensor_timestamp.isoformat()
                            if sensor_timestamp
                            else None
                        ),

                    "freshness":
                        sensor_freshness,

                    "age_minutes":
                        sensor_age_minutes,

                    "usable":
                        sensor_usable,

                },

                "spatial": {

                    "available":
                        bool(
                            spatial_context
                        ),

                    "infected_neighbors":
                        spatial_infected,

                    "total_observed_zones":
                        spatial_total,

                },

                "temporal": {

                    "available":
                        bool(
                            history
                        ),

                    "observation_count":
                        (
                            len(history)
                            if history
                            else 0
                        ),

                },

                "evidence_count":
                    evidence_count,

                "evidence_quality":
                    evidence_quality,

            },

        )
    )

    # ========================================================
    # 13. LOCAL QWEN3 ADVISORY
    # ========================================================
    #
    # IMPORTANT:
    #
    # Qwen3 is explanation-only.
    #
    # It NEVER changes:
    #
    #   risk_score
    #   risk_level
    #   assessment_confidence
    #   decision.action
    #   decision.priority
    #
    # Qwen3 is called only after the deterministic
    # CRAI pipeline has accepted the evidence.
    # ========================================================

    advisory = None

    decision_ready = (
        isinstance(
            decision,
            dict,
        )
        and bool(
            decision.get(
                "ready",
                True,
            )
        )
    )

    if decision_ready:

        try:

            advisory_input = {

                "crop":
                    crop,

                "growth_stage":
                    growth_stage,

                "disease": {

                    "prediction":
                        prediction,

                    "confidence":
                        round(
                            confidence,
                            2,
                        ),

                },

                "risk":
                    risk,

                "decision":
                    decision,

                "context": {

                    "sensor": {

                        "available":
                            bool(sensor),

                        "soil_moisture":
                            soil_moisture,

                        "temperature":
                            temperature_for_fusion,

                        "humidity":
                            humidity_for_fusion,

                        "timestamp":
                            (
                                sensor_timestamp.isoformat()
                                if sensor_timestamp
                                else None
                            ),

                        "freshness":
                            sensor_freshness,

                        "age_minutes":
                            sensor_age_minutes,

                        "usable":
                            sensor_usable,

                    },

                    "spatial": {

                        "available":
                            bool(
                                spatial_context
                            ),

                        "infected_neighbors":
                            spatial_infected,

                        "total_observed_zones":
                            spatial_total,

                    },

                    "temporal": {

                        "available":
                            bool(history),

                        "observation_count":
                            (
                                len(history)
                                if history
                                else 0
                            ),

                        "history":
                            history,

                    },

                    "crop":
                        crop,

                    "growth_stage":
                        growth_stage,

                    "observation_count":
                        observation_count,

                },

                "evidence":
                    evidence,

                "judge_intelligence":
                    judge_intelligence,

            }

            advisory = (
                generate_local_advisory(

                    field_data=
                        advisory_input,

                    language=
                        advisory_language,

                )
            )

        except Exception as exc:

            # ------------------------------------------------
            # LLM failure must NEVER break deterministic CRAI.
            # ------------------------------------------------

            advisory = {

                "available":
                    False,

                "provider":
                    "OLLAMA",

                "model":
                    "qwen3:1.7b",

                "language":
                    advisory_language,

                "advisory":
                    (
                        "Local advisory is "
                        "temporarily unavailable. "
                        "Follow the CRAI decision "
                        "and recommended steps."
                    ),

                "grounded_evidence":
                    None,

                "offline":
                    True,

                "fallback":
                    True,

                "error":
                    str(exc),

            }

    # ========================================================
    # 14. FINAL RESPONSE
    # ========================================================

    return {

        "status":
            "ANALYSIS_COMPLETE",

        "disease": {

            "prediction":
                prediction,

            "confidence":
                round(
                    confidence,
                    2,
                ),

        },

        "image_quality":
            image_quality,

        "evidence":
            evidence,

        # ----------------------------------------------------
        # AUTHORITATIVE DETERMINISTIC RISK
        # ----------------------------------------------------

        "risk":
            risk,

        # ----------------------------------------------------
        # AUTHORITATIVE DETERMINISTIC DECISION
        # ----------------------------------------------------

        "decision":
            decision,

        # ----------------------------------------------------
        # JUDGE TRANSPARENCY
        # ----------------------------------------------------

        "judge_intelligence":
            judge_intelligence,

        # ----------------------------------------------------
        # QWEN3 INFORMATIONAL ADVISORY ONLY
        # ----------------------------------------------------

        "advisory":
            advisory,

        "context": {

            "crop":
                crop,

            "growth_stage":
                growth_stage,

            "observation_count":
                observation_count,

            "sensor": {

                "available":
                    bool(sensor),

                "device_id":
                    (
                        sensor.get(
                            "device_id"
                        )
                        if isinstance(
                            sensor,
                            dict,
                        )
                        else None
                    ),

                "soil_moisture":
                    soil_moisture,

                "temperature":
                    temperature_for_fusion,

                "humidity":
                    humidity_for_fusion,

                "timestamp":
                    (
                        sensor_timestamp.isoformat()
                        if sensor_timestamp
                        else None
                    ),

                "freshness":
                    sensor_freshness,

                "age_minutes":
                    sensor_age_minutes,

                "usable":
                    sensor_usable,

            },

            "spatial": {

                "available":
                    bool(
                        spatial_context
                    ),

                "infected_neighbors":
                    spatial_infected,

                "total_observed_zones":
                    spatial_total,

            },

            "temporal": {

                "available":
                    bool(
                        history
                    ),

                "observation_count":
                    (
                        len(history)
                        if history
                        else 0
                    ),

            },

            "evidence_count":
                evidence_count,

            "evidence_quality":
                evidence_quality,

        },

    }
