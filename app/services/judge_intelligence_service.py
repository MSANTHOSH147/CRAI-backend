"""
CRAI Judge Intelligence Layer
--------------------------------

Presentation/explanation layer built on top of the
authoritative CRAI deterministic pipeline.

IMPORTANT:
This service NEVER recalculates or changes:
    - risk_score
    - risk_level
    - assessment_confidence
    - decision.action
    - decision.priority

It only explains existing CRAI outputs.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


FRESHNESS_POLICY_MINUTES = 15


def _safe_float(
    value: Any,
) -> Optional[float]:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_dict(
    value: Any,
) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(
    value: Any,
) -> list:
    return value if isinstance(value, list) else []


# ============================================================
# WHY SENSOR?
# ============================================================

def build_why_sensor(
    *,
    evidence: Optional[dict] = None,
    context: Optional[dict] = None,
    adaptive_evidence: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Explain why CRAI requested environmental evidence.

    This uses the adaptive evidence engine's existing decision.
    No new risk calculation is performed.
    """

    evidence = _safe_dict(evidence)
    context = _safe_dict(context)
    adaptive = _safe_dict(adaptive_evidence)

    sensor = _safe_dict(
        context.get("sensor")
    )

    environmental = _safe_dict(
        evidence.get("details", {}).get(
            "environmental"
        )
    )

    action = str(
        adaptive.get(
            "action",
            ""
        )
    ).upper()

    adaptive_action = str(
        adaptive.get(
            "adaptive_action",
            ""
        )
    ).upper()

    evidence_gap = (
        adaptive.get(
            "evidence_gap"
        )
        or environmental.get(
            "evidence_gap"
        )
    )

    reason = (
        adaptive.get("reason")
        or environmental.get("reason")
    )

    freshness = (
        sensor.get("freshness")
        or environmental.get("status")
        or environmental.get("freshness")
    )

    age_minutes = (
        sensor.get("age_minutes")
        if sensor.get("age_minutes") is not None
        else environmental.get("age_minutes")
    )

    sensor_available = bool(
        sensor.get("available")
    )

    requested = (
        adaptive.get("requested_evidence")
        or evidence.get("requested_evidence")
        or []
    )

    requested = _safe_list(requested)

    sensor_requested = (
        action == "REQUEST_SENSOR"
        or adaptive_action in {
            "REFRESH_SENSOR",
            "REQUEST_SENSOR",
        }
        or "STALE_ENVIRONMENT" in str(evidence_gap)
        or "ENVIRONMENT" in str(evidence_gap)
    )

    # --------------------------------------------------------
    # Construct a clean judge-facing reason.
    # --------------------------------------------------------

    if sensor_requested:

        if (
            freshness in {
                "STALE",
                "UNAVAILABLE",
                "VERY_STALE",
            }
        ):

            trigger = "ENVIRONMENTAL_EVIDENCE_STALE"

            explanation = (
                "Environmental evidence is outside "
                "CRAI's freshness policy, so a fresh "
                "sensor reading is required before "
                "finalizing the field assessment."
            )

        elif not sensor_available:

            trigger = "ENVIRONMENTAL_EVIDENCE_MISSING"

            explanation = (
                "Visual evidence is available, but "
                "environmental evidence is missing. "
                "CRAI requests a sensor reading before "
                "making a stronger field-level assessment."
            )

        else:

            trigger = (
                evidence_gap
                or "ENVIRONMENTAL_EVIDENCE_REQUIRED"
            )

            explanation = (
                reason
                or
                "CRAI requires environmental evidence "
                "for the current field assessment."
            )

    else:

        trigger = None

        explanation = (
            "No additional environmental evidence "
            "was required for the current decision."
        )

    return {
        "needed": bool(sensor_requested),

        "trigger": trigger,

        "reason": explanation,

        "engine_reason": reason,

        "required_evidence": (
            "FRESH_ENVIRONMENTAL"
            if sensor_requested
            else None
        ),

        "requested_evidence": requested,

        "requested_source": (
            adaptive.get("next_best_source")
            or adaptive.get("source")
            or "ESP32"
            if sensor_requested
            else None
        ),

        "policy": {
            "freshness_limit_minutes":
                FRESHNESS_POLICY_MINUTES,

            "rule":
                "Environmental evidence must be fresh "
                "within the CRAI decision policy.",
        },

        "current_sensor": {
            "available":
                sensor_available,

            "freshness":
                freshness,

            "age_minutes":
                age_minutes,

            "usable":
                sensor.get("usable"),
        },

        "adaptive_action":
            adaptive_action or None,

        "decision_ready":
            bool(
                adaptive.get(
                    "decision_ready",
                    False,
                )
            ),
    }


# ============================================================
# WHY RISK?
# ============================================================

def build_why_risk(
    *,
    risk: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Explain the authoritative deterministic CRAI risk result.

    Contributions are taken directly from FUSION_V1_5.
    """

    risk = _safe_dict(risk)

    risk_score = _safe_float(
        risk.get("risk_score")
    )

    risk_level = risk.get(
        "risk_level"
    )

    assessment_confidence = risk.get(
        "assessment_confidence"
    )

    breakdown = _safe_dict(
        risk.get("breakdown")
    )

    contributions = _safe_dict(
        risk.get("contributions")
    )

    weights = _safe_dict(
        risk.get("weights")
    )

    evidence_summary = _safe_dict(
        risk.get("evidence_summary")
    )

    available_evidence = _safe_list(
        risk.get("available_evidence")
    )

    missing_evidence = _safe_list(
        risk.get("missing_evidence")
    )

    # --------------------------------------------------------
    # Sort contributions for presentation only.
    # --------------------------------------------------------

    contribution_items = []

    for source, value in contributions.items():

        numeric_value = _safe_float(value)

        if numeric_value is None:
            continue

        contribution_items.append(
            {
                "source": source,
                "contribution": round(
                    numeric_value,
                    2,
                ),
                "evidence_score": (
                    round(
                        _safe_float(
                            breakdown.get(source)
                        ),
                        2,
                    )
                    if _safe_float(
                        breakdown.get(source)
                    ) is not None
                    else None
                ),
                "effective_weight": (
                    round(
                        _safe_float(
                            weights.get(source)
                        ),
                        2,
                    )
                    if _safe_float(
                        weights.get(source)
                    ) is not None
                    else None
                ),
            }
        )

    contribution_items.sort(
        key=lambda item:
            item["contribution"],
        reverse=True,
    )

    strongest = (
        contribution_items[0]
        if contribution_items
        else None
    )

    if strongest:

        strongest_explanation = (
            f"{strongest['source'].capitalize()} "
            f"evidence contributed "
            f"{strongest['contribution']:.1f} "
            f"risk points."
        )

    else:

        strongest_explanation = (
            "No evidence contribution is available."
        )

    return {
        "risk_score":
            risk_score,

        "risk_level":
            risk_level,

        "assessment_confidence":
            assessment_confidence,

        "formula": {
            "description":
                "CRAI combines available evidence "
                "sources using the deterministic "
                "FUSION_V1_5 weighting policy.",

            "weights":
                weights,
        },

        "contributions":
            contribution_items,

        "total_contribution":
            round(
                sum(
                    item["contribution"]
                    for item in contribution_items
                ),
                2,
            ),

        "strongest_contributor":
            strongest,

        "explanation":
            strongest_explanation,

        "available_evidence":
            available_evidence,

        "missing_evidence":
            missing_evidence,

        "evidence_summary":
            evidence_summary,
    }


# ============================================================
# EVIDENCE PROVENANCE
# ============================================================

def build_evidence_provenance(
    *,
    disease: Optional[dict] = None,
    evidence: Optional[dict] = None,
    context: Optional[dict] = None,
    risk: Optional[dict] = None,
) -> list:
    """
    Build judge-facing provenance records.

    These records describe where the evidence came from
    and whether it was available to the deterministic
    assessment.
    """

    disease = _safe_dict(disease)
    evidence = _safe_dict(evidence)
    context = _safe_dict(context)
    risk = _safe_dict(risk)

    sensor = _safe_dict(
        context.get("sensor")
    )

    spatial = _safe_dict(
        context.get("spatial")
    )

    temporal = _safe_dict(
        context.get("temporal")
    )

    available = _safe_dict(
        evidence.get("available")
    )

    quality = _safe_dict(
        evidence.get("quality")
    )

    risk_available = set(
        _safe_list(
            risk.get("available_evidence")
        )
    )

    records = []

    # --------------------------------------------------------
    # VISUAL
    # --------------------------------------------------------

    visual_available = bool(
        available.get(
            "visual",
            True
        )
    )

    records.append(
        {
            "type":
                "visual",

            "source":
                "SMARTPHONE",

            "value":
                disease.get(
                    "prediction"
                ),

            "confidence":
                disease.get(
                    "confidence"
                ),

            "quality":
                quality.get("visual"),

            "status":
                "AVAILABLE"
                if visual_available
                else "MISSING",

            "used_in_decision":
                "visual" in risk_available,
        }
    )

    # --------------------------------------------------------
    # ENVIRONMENTAL
    # --------------------------------------------------------

    environmental_available = bool(
        available.get(
            "environmental",
            sensor.get("available", False)
        )
    )

    records.append(
        {
            "type":
                "environmental",

            "source":
                sensor.get(
                    "device_id",
                    "CRAI-ESP32"
                ),

            "values": {
                "soil_moisture":
                    sensor.get(
                        "soil_moisture"
                    ),

                "temperature":
                    sensor.get(
                        "temperature"
                    ),

                "humidity":
                    sensor.get(
                        "humidity"
                    ),
            },

            "timestamp":
                sensor.get(
                    "timestamp"
                ),

            "age_minutes":
                sensor.get(
                    "age_minutes"
                ),

            "freshness":
                sensor.get(
                    "freshness"
                ),

            "quality":
                quality.get(
                    "environmental"
                ),

            "status":
                "AVAILABLE"
                if environmental_available
                else "MISSING",

            "used_in_decision":
                "environmental"
                in risk_available,
        }
    )

    # --------------------------------------------------------
    # SPATIAL
    # --------------------------------------------------------

    spatial_available = bool(
        available.get(
            "spatial",
            spatial.get("available", False)
        )
    )

    records.append(
        {
            "type":
                "spatial",

            "source":
                "FIELD_OBSERVATIONS",

            "values": {
                "infected_neighbors":
                    spatial.get(
                        "infected_neighbors"
                    ),

                "total_observed_zones":
                    spatial.get(
                        "total_observed_zones"
                    ),
            },

            "quality":
                quality.get("spatial"),

            "status":
                "AVAILABLE"
                if spatial_available
                else "MISSING",

            "used_in_decision":
                "spatial" in risk_available,
        }
    )

    # --------------------------------------------------------
    # TEMPORAL
    # --------------------------------------------------------

    temporal_available = bool(
        available.get(
            "temporal",
            temporal.get("available", False)
        )
    )

    records.append(
        {
            "type":
                "temporal",

            "source":
                "CRAI_FIELD_MEMORY",

            "observation_count":
                temporal.get(
                    "observation_count"
                ),

            "quality":
                quality.get("temporal"),

            "status":
                "AVAILABLE"
                if temporal_available
                else "MISSING",

            "used_in_decision":
                "temporal" in risk_available,
        }
    )

    return records


# ============================================================
# DECISION TRACE
# ============================================================

def build_decision_trace(
    *,
    evidence: Optional[dict] = None,
    risk: Optional[dict] = None,
    decision: Optional[dict] = None,
) -> Dict[str, Any]:

    evidence = _safe_dict(evidence)
    risk = _safe_dict(risk)
    decision = _safe_dict(decision)

    available = _safe_dict(
        evidence.get("available")
    )

    evidence_count = sum(
        1
        for value in available.values()
        if bool(value)
    )

    adaptive = _safe_dict(
        evidence.get("adaptive")
    )

    return {
        "stages": [
            {
                "stage": "EVIDENCE_EVALUATION",
                "status": "COMPLETE",
                "evidence_count":
                    evidence_count,
            },
            {
                "stage": "ADAPTIVE_EVIDENCE_GATE",
                "status":
                    "DECISION_READY"
                    if adaptive.get(
                        "decision_ready",
                        True
                    )
                    else "ADDITIONAL_EVIDENCE_REQUIRED",
                "action":
                    adaptive.get(
                        "action"
                    ),
            },
            {
                "stage": "FUSION_V1_5",
                "status":
                    "COMPLETE"
                    if risk.get(
                        "risk_score"
                    ) is not None
                    else "NOT_READY",
                "risk_score":
                    risk.get(
                        "risk_score"
                    ),
                "risk_level":
                    risk.get(
                        "risk_level"
                    ),
            },
            {
                "stage": "DETERMINISTIC_DECISION",
                "status":
                    "READY"
                    if decision.get(
                        "ready",
                        True
                    )
                    else "NOT_READY",
                "action":
                    decision.get(
                        "action"
                    ),
                "priority":
                    decision.get(
                        "priority"
                    ),
            },
        ],

        "authoritative_outputs": {
            "risk_score":
                risk.get("risk_score"),

            "risk_level":
                risk.get("risk_level"),

            "assessment_confidence":
                risk.get(
                    "assessment_confidence"
                ),

            "decision_action":
                decision.get("action"),

            "decision_priority":
                decision.get("priority"),
        },
    }


# ============================================================
# PUBLIC API
# ============================================================

def build_judge_intelligence(
    *,
    disease: Optional[dict] = None,
    evidence: Optional[dict] = None,
    risk: Optional[dict] = None,
    decision: Optional[dict] = None,
    context: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Build the complete judge-facing intelligence payload.
    """

    evidence = _safe_dict(evidence)
    risk = _safe_dict(risk)
    decision = _safe_dict(decision)
    context = _safe_dict(context)
    disease = _safe_dict(disease)

    adaptive = _safe_dict(
        evidence.get("adaptive")
    )

    why_sensor = build_why_sensor(
        evidence=evidence,
        context=context,
        adaptive_evidence=adaptive,
    )

    why_risk = build_why_risk(
        risk=risk,
    )

    provenance = build_evidence_provenance(
        disease=disease,
        evidence=evidence,
        context=context,
        risk=risk,
    )

    decision_trace = build_decision_trace(
        evidence=evidence,
        risk=risk,
        decision=decision,
    )

    return {
        "version":
            "JUDGE_INTELLIGENCE_V1",

        "why_sensor":
            why_sensor,

        "why_risk":
            why_risk,

        "evidence_provenance":
            provenance,

        "decision_trace":
            decision_trace,

        "deterministic_source":
            "CRAI_FUSION_V1_5",

        "llm_role":
            "EXPLANATION_ONLY",
    }