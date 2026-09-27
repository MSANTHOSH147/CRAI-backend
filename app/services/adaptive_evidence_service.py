"""
CRAI Adaptive Evidence Service V3

Single authoritative adaptive gate for the backend.

Responsibilities:
- validate visual confidence and image quality state
- distinguish fresh/recent/stale environmental evidence
- build cost-aware evidence candidates
- select the next useful acquisition path
- expose a deterministic stopping policy

This is an engineering policy, not a scientifically proven optimizer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from app.services.adaptive_evidence_intelligence import (
    EvidenceCandidate,
    build_adaptive_intelligence,
    evidence_reliability,
)


LOW_MODEL_CONFIDENCE = 60.0
MEDIUM_MODEL_CONFIDENCE = 85.0
FRESH_SENSOR_MINUTES = 15
RECENT_SENSOR_MINUTES = 15
STALE_SENSOR_MINUTES = 360
DEFAULT_VISUAL_ACCEPTANCE = 0.60


def normalize_visual_confidence(confidence: Any) -> Optional[float]:
    if confidence is None:
        return None
    try:
        value = float(confidence)
    except (TypeError, ValueError):
        return None
    if value > 1.0:
        value /= 100.0
    return max(0.0, min(1.0, value))


def calculate_sensor_freshness(timestamp: Optional[Any]) -> str:
    if timestamp is None:
        return "UNAVAILABLE"

    try:
        if isinstance(timestamp, str):
            sensor_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        elif isinstance(timestamp, datetime):
            sensor_time = timestamp
        else:
            return "UNAVAILABLE"

        if sensor_time.tzinfo is None:
            sensor_time = sensor_time.replace(tzinfo=timezone.utc)

        age_minutes = max(
            0.0,
            (datetime.now(timezone.utc) - sensor_time.astimezone(timezone.utc)).total_seconds() / 60.0,
        )

        if age_minutes <= FRESH_SENSOR_MINUTES:
            return "FRESH"
        if age_minutes <= RECENT_SENSOR_MINUTES:
            return "RECENT"
        if age_minutes <= STALE_SENSOR_MINUTES:
            return "STALE"
        return "VERY_STALE"
    except Exception:
        return "UNAVAILABLE"


def sensor_age_from_timestamp(timestamp: Optional[Any]) -> Optional[float]:
    if timestamp is None:
        return None
    try:
        if isinstance(timestamp, str):
            value = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        elif isinstance(timestamp, datetime):
            value = timestamp
        else:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return max(
            0.0,
            (datetime.now(timezone.utc) - value.astimezone(timezone.utc)).total_seconds() / 60.0,
        )
    except Exception:
        return None


def evaluate_sensor_evidence(sensor: Optional[dict]) -> dict:
    if not sensor:
        return {
            "available": False,
            "freshness": "UNAVAILABLE",
            "age_minutes": None,
            "values_available": [],
            "usable_for_current_decision": False,
        }

    values_available = [
        field
        for field in ("soil_moisture", "temperature", "humidity")
        if sensor.get(field) is not None
    ]

    freshness = calculate_sensor_freshness(sensor.get("timestamp"))
    age_minutes = sensor_age_from_timestamp(sensor.get("timestamp"))
    usable = bool(values_available) and freshness in {"FRESH", "RECENT"}

    return {
        "available": bool(values_available),
        "freshness": freshness,
        "age_minutes": age_minutes,
        "values_available": values_available,
        "usable_for_current_decision": usable,
    }


def evaluate_model_evidence(prediction: Optional[str], confidence: Any) -> dict:
    normalized = normalize_visual_confidence(confidence)
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
        "accepted": normalized >= DEFAULT_VISUAL_ACCEPTANCE,
        "uncertainty": 1.0 - normalized,
    }


def _candidate(
    *,
    evidence: str,
    source: str,
    model: Optional[str],
    information_value: float,
    decision_impact: float,
    reliability: float,
    cost: float,
    time: float,
    reason: str,
) -> EvidenceCandidate:
    return EvidenceCandidate(
        evidence=evidence,
        source=source,
        model=model,
        available=True,
        reliability=reliability,
        information_value=information_value,
        decision_impact=decision_impact,
        acquisition_cost=cost,
        acquisition_time=time,
        reason=reason,
    )


def _build_candidates(
    *,
    confidence: Optional[float],
    sensor_info: dict,
    second_image_available: bool,
    thermal_available: bool,
    spatial_available: bool,
    temporal_available: bool,
    uav_available: bool,
    manual_review_available: bool,
) -> list[EvidenceCandidate]:
    candidates: list[EvidenceCandidate] = []

    freshness = sensor_info.get("freshness")
    sensor_present = bool(sensor_info.get("available"))
    sensor_usable = bool(sensor_info.get("usable_for_current_decision"))

    # Visual uncertainty: another smartphone image is the cheapest path
    # because it directly addresses the uncertainty produced by V3.
    if confidence is None or confidence < 0.85:
        if not second_image_available:
            visual_impact = 0.95 if confidence is not None and confidence < 0.60 else 0.88
            candidates.append(
                _candidate(
                    evidence="SECOND_IMAGE",
                    source="SMARTPHONE",
                    model="CRAI_V3",
                    information_value=0.90,
                    decision_impact=visual_impact,
                    reliability=0.90,
                    cost=0.08,
                    time=0.12,
                    reason="A second field image directly reduces visual uncertainty at very low acquisition burden.",
                )
            )

    # Environmental gap or stale data: fresh ESP32 is the preferred low-cost
    # physical acquisition path.
    if not sensor_present or not sensor_usable:
        stale_context = freshness in {"STALE", "VERY_STALE"}
        freshness_factor = 0.98 if stale_context else 0.95
        candidates.append(
            _candidate(
                evidence="FRESH_SENSOR_READING",
                source="ESP32",
                model=None,
                information_value=0.95 if stale_context else 0.82,
                decision_impact=0.95 if stale_context else (0.92 if confidence is not None and confidence >= 0.60 else 0.35),
                reliability=freshness_factor,
                cost=0.15,
                time=0.10,
                reason="A fresh environmental reading can validate field conditions without activating a higher-cost sensing path.",
            )
        )

    # UAV is selectable only when an actual UAV acquisition path is available.
    # A loaded model alone does not mean a drone is in the field.
    if uav_available and not spatial_available:
        candidates.append(
            _candidate(
                evidence="UAV_OBSERVATION",
                source="UAV",
                model="UAV_V1",
                information_value=0.90,
                decision_impact=0.88,
                reliability=0.90,
                cost=0.55,
                time=0.45,
                reason="Aerial evidence can add spatial context when local image and sensor evidence remain insufficient.",
            )
        )

    if thermal_available:
        candidates.append(
            _candidate(
                evidence="THERMAL",
                source="THERMAL_CAMERA",
                model=None,
                information_value=0.72,
                decision_impact=0.70,
                reliability=0.92,
                cost=0.75,
                time=0.60,
                reason="Thermal evidence is reserved for cases where lower-burden evidence cannot resolve the decision.",
            )
        )

    if manual_review_available and confidence is not None and confidence < 0.60 and second_image_available:
        candidates.append(
            _candidate(
                evidence="MANUAL_REVIEW",
                source="EXPERT",
                model=None,
                information_value=0.95,
                decision_impact=0.95,
                reliability=0.95,
                cost=0.95,
                time=0.90,
                reason="Human verification is the high-burden fallback when visual uncertainty remains unresolved.",
            )
        )

    return candidates


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
    uav_available: bool = False,
    manual_review_available: bool = True,
) -> dict:
    confidence = normalize_visual_confidence(visual_confidence)

    if image_quality_status == "RETAKE_REQUIRED":
        selected = _candidate(
            evidence="RETAKE_IMAGE",
            source="SMARTPHONE",
            model="CRAI_V3",
            information_value=0.95,
            decision_impact=1.0,
            reliability=0.95,
            cost=0.05,
            time=0.10,
            reason="Image quality must be corrected before model evidence is trusted.",
        )
        selected.utility = 1.0
        intelligence = build_adaptive_intelligence(
            decision_readiness=0.0,
            evidence_states={"visual": "UNKNOWN"},
            candidates=[selected],
        )
        return _format_result(
            action="REQUEST_IMAGE",
            adaptive_action="RETAKE_IMAGE",
            priority="HIGH",
            evidence_required="RETAKE_IMAGE",
            selected=selected,
            decision_ready=False,
            visual_accepted=False,
            evidence_gap="IMAGE_QUALITY",
            reason="Image quality is insufficient. CRAI should acquire a clearer image before inference is trusted.",
            intelligence=intelligence,
        )

    if confidence is None:
        selected = _candidate(
            evidence="IMAGE",
            source="SMARTPHONE",
            model="CRAI_V3",
            information_value=1.0,
            decision_impact=1.0,
            reliability=0.95,
            cost=0.05,
            time=0.10,
            reason="A visual observation is required before any field decision can begin.",
        )
        intelligence = build_adaptive_intelligence(
            decision_readiness=0.0,
            evidence_states={"visual": "UNKNOWN"},
            candidates=[selected],
        )
        return _format_result(
            action="REQUEST_IMAGE",
            adaptive_action="REQUEST_IMAGE",
            priority="HIGH",
            evidence_required="IMAGE",
            selected=selected,
            decision_ready=False,
            visual_accepted=False,
            evidence_gap="VISUAL",
            reason="No usable visual prediction is available. CRAI requires an image observation.",
            intelligence=intelligence,
        )

    sensor_info = {
        "available": sensor_available,
        "freshness": sensor_freshness,
        "age_minutes": sensor_age_minutes,
        "usable_for_current_decision": sensor_available and sensor_freshness in {"FRESH", "RECENT"},
    }

    if sensor_freshness is None and sensor_age_minutes is not None:
        if sensor_age_minutes <= FRESH_SENSOR_MINUTES:
            sensor_info["freshness"] = "FRESH"
        elif sensor_age_minutes <= RECENT_SENSOR_MINUTES:
            sensor_info["freshness"] = "RECENT"
        elif sensor_age_minutes <= STALE_SENSOR_MINUTES:
            sensor_info["freshness"] = "STALE"
        else:
            sensor_info["freshness"] = "VERY_STALE"
        sensor_info["usable_for_current_decision"] = sensor_info["freshness"] in {"FRESH", "RECENT"}

    # Existing current behavior remains conservative: visual confidence below
    # 60% cannot be rescued by environmental data alone.
    if confidence < DEFAULT_VISUAL_ACCEPTANCE and not second_image_available:
        candidates = _build_candidates(
            confidence=confidence,
            sensor_info=sensor_info,
            second_image_available=False,
            thermal_available=False,
            spatial_available=spatial_available,
            temporal_available=temporal_available,
            uav_available=False,
            manual_review_available=False,
        )
        intelligence = build_adaptive_intelligence(
            decision_readiness=confidence,
            evidence_states={"visual": "UNKNOWN", "environmental": "UNKNOWN"},
            candidates=candidates,
        )
        selected_dict = intelligence["next_best_evidence"]
        selected = next(c for c in candidates if c.evidence == selected_dict["evidence"])
        return _format_result(
            action="REQUEST_IMAGE",
            adaptive_action="SECOND_IMAGE",
            priority="HIGH",
            evidence_required="SECOND_IMAGE",
            selected=selected,
            decision_ready=False,
            visual_accepted=False,
            evidence_gap="VISUAL_UNCERTAINTY",
            reason="Visual confidence is below the CRAI operating threshold. Acquire another image before making a field assessment.",
            intelligence=intelligence,
        )

    candidates = _build_candidates(
        confidence=confidence,
        sensor_info=sensor_info,
        second_image_available=second_image_available,
        thermal_available=thermal_available,
        spatial_available=spatial_available,
        temporal_available=temporal_available,
        uav_available=uav_available,
        manual_review_available=manual_review_available,
    )

    # If the current image is moderate and environmental data is absent,
    # the cheap second image is preferred. If a known sensor reading is
    # stale, refreshing that explicit gap is more decision-relevant.
    if 0.60 <= confidence < 0.85 and not second_image_available and sensor_info.get("freshness") not in {"STALE", "VERY_STALE"}:
        selected = next(
            (c for c in candidates if c.evidence == "SECOND_IMAGE"),
            None,
        )
        if selected:
            intelligence = build_adaptive_intelligence(
                decision_readiness=confidence,
                evidence_states={"visual": "UNKNOWN", "environmental": "UNKNOWN"},
                candidates=candidates,
            )
            return _format_result(
                action="REQUEST_IMAGE",
                adaptive_action="SECOND_IMAGE",
                priority="MEDIUM",
                evidence_required="SECOND_IMAGE",
                selected=selected,
                decision_ready=False,
                visual_accepted=False,
                evidence_gap="VISUAL_UNCERTAINTY",
                reason="Visual confidence is acceptable for screening but remains below the stronger CRAI evidence threshold. Acquire another image if available.",
                intelligence=intelligence,
            )

    if confidence >= DEFAULT_VISUAL_ACCEPTANCE and sensor_info["usable_for_current_decision"]:
        intelligence = build_adaptive_intelligence(
            decision_readiness=min(1.0, confidence + 0.20),
            evidence_states={"visual": "SUPPORTING", "environmental": "SUPPORTING"},
            candidates=candidates,
        )
        return _format_result(
            action="ACCEPT",
            adaptive_action="DECISION_READY",
            priority="LOW",
            evidence_required="NONE",
            selected=None,
            decision_ready=True,
            visual_accepted=True,
            evidence_gap=None,
            reason="Available visual and fresh environmental evidence is sufficient for the current CRAI decision.",
            intelligence=intelligence,
        )

    if not candidates:
        intelligence = build_adaptive_intelligence(
            decision_readiness=confidence,
            evidence_states={"visual": "SUPPORTING", "environmental": "UNKNOWN"},
            candidates=[],
        )
        return _format_result(
            action="REQUEST_MANUAL_REVIEW",
            adaptive_action="MANUAL_REVIEW",
            priority="HIGH",
            evidence_required="MANUAL_REVIEW",
            selected=None,
            decision_ready=False,
            visual_accepted=confidence >= DEFAULT_VISUAL_ACCEPTANCE,
            evidence_gap="UNRESOLVED_EVIDENCE",
            reason="CRAI could not identify an available low-burden evidence source that resolves the current uncertainty.",
            intelligence=intelligence,
        )

    intelligence = build_adaptive_intelligence(
        decision_readiness=confidence,
        evidence_states={
            "visual": "SUPPORTING" if confidence >= DEFAULT_VISUAL_ACCEPTANCE else "UNKNOWN",
            "environmental": "SUPPORTING" if sensor_info["usable_for_current_decision"] else "UNKNOWN",
            "spatial": "SUPPORTING" if spatial_available else "UNKNOWN",
            "temporal": "SUPPORTING" if temporal_available else "UNKNOWN",
        },
        candidates=candidates,
    )

    selected_dict = intelligence["next_best_evidence"]
    selected = next(c for c in candidates if c.evidence == selected_dict["evidence"])

    if selected.evidence == "FRESH_SENSOR_READING":
        return _format_result(
            action="REQUEST_SENSOR",
            adaptive_action="REFRESH_SENSOR",
            priority="HIGH" if sensor_info.get("freshness") in {"STALE", "VERY_STALE"} else "MEDIUM",
            evidence_required="ENVIRONMENT",
            selected=selected,
            decision_ready=False,
            visual_accepted=confidence >= DEFAULT_VISUAL_ACCEPTANCE,
            evidence_gap="STALE_ENVIRONMENT" if sensor_info.get("available") else "ENVIRONMENT",
            reason=(
                "Environmental evidence is stale. CRAI should acquire a fresh sensor reading."
                if sensor_info.get("available")
                else "Visual evidence requires fresh environmental context before CRAI finalizes the field assessment."
            ),
            intelligence=intelligence,
        )

    if selected.evidence == "UAV_OBSERVATION":
        return _format_result(
            action="REQUEST_UAV",
            adaptive_action="UAV_OBSERVATION",
            priority="MEDIUM",
            evidence_required="UAV_OBSERVATION",
            selected=selected,
            decision_ready=False,
            visual_accepted=confidence >= DEFAULT_VISUAL_ACCEPTANCE,
            evidence_gap="SPATIAL",
            reason=selected.reason,
            intelligence=intelligence,
        )

    if selected.evidence == "THERMAL":
        return _format_result(
            action="REQUEST_THERMAL",
            adaptive_action="THERMAL",
            priority="MEDIUM",
            evidence_required="THERMAL",
            selected=selected,
            decision_ready=False,
            visual_accepted=confidence >= DEFAULT_VISUAL_ACCEPTANCE,
            evidence_gap="THERMAL",
            reason=selected.reason,
            intelligence=intelligence,
        )

    return _format_result(
        action="REQUEST_MANUAL_REVIEW",
        adaptive_action="MANUAL_REVIEW",
        priority="HIGH",
        evidence_required="MANUAL_REVIEW",
        selected=selected,
        decision_ready=False,
        visual_accepted=confidence >= DEFAULT_VISUAL_ACCEPTANCE,
        evidence_gap="UNRESOLVED_EVIDENCE",
        reason=selected.reason,
        intelligence=intelligence,
    )


def _format_result(
    *,
    action: str,
    adaptive_action: str,
    priority: str,
    evidence_required: str,
    selected: Optional[EvidenceCandidate],
    decision_ready: bool,
    visual_accepted: bool,
    evidence_gap: Optional[str],
    reason: str,
    intelligence: dict,
) -> dict:
    requested = [] if decision_ready else [evidence_required]
    if evidence_required == "ENVIRONMENT":
        requested = ["FRESH_SENSOR_READING"]

    selected_dict = selected.to_dict() if selected else None

    return {
        "action": action,
        "adaptive_action": adaptive_action,
        "priority": priority,
        "evidence_required": evidence_required,
        "requested_evidence": requested,
        "next_best_source": selected.source if selected else None,
        "source": selected.source if selected else None,
        "model": selected.model if selected else None,
        "decision_ready": decision_ready,
        "visual_evidence_accepted": visual_accepted,
        "evidence_gap": evidence_gap,
        "reason": reason,
        "cost_aware_selection": {
            "selected": selected_dict,
            "ranked_candidates": intelligence.get("ranked_candidates", []),
            "stopping_policy": intelligence.get("stopping_policy"),
            "policy": intelligence.get("policy"),
        },
    }


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
    uav_available: bool = False,
    manual_review_available: bool = True,
) -> dict:
    if image_quality is not None and image_quality_status is None:
        image_quality_status = image_quality.get("status")

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
        uav_available=uav_available,
        manual_review_available=manual_review_available,
    )

    if result.get("action") == "ACCEPT":
        result["action"] = "ACCEPT_AND_FUSE"
        result["adaptive_action"] = "DECISION_READY"

    result["accepted"] = result["visual_evidence_accepted"]
    return result


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
    sensor_info = evaluate_sensor_evidence(sensor)
    return evaluate_adaptive_evidence(
        visual_confidence=confidence,
        sensor_available=sensor_info["available"],
        sensor_age_minutes=sensor_info["age_minutes"],
        sensor_freshness=sensor_info["freshness"],
        second_image_available=second_image_available,
        thermal_available=thermal_available,
        spatial_available=spatial_available,
        temporal_available=temporal_available,
        image_quality_status=image_quality_status,
    )


def second_image_instruction() -> dict:
    return {
        "action": "REQUEST_IMAGE",
        "source": "SMARTPHONE",
        "model": "CRAI_V3",
        "instruction": "Capture another image of the same leaf from a slightly different angle with the leaf filling most of the frame.",
        "reason": "A second observation can reduce visual uncertainty.",
    }
