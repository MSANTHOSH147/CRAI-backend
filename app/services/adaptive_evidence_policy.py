"""
CRAI Adaptive Evidence Policy V1

Research basis:
    CRAI Adaptive Evidence Acquisition V1

Purpose:
    Decide whether the currently available evidence is sufficient
    for a field assessment or whether CRAI should acquire more.

This module DOES NOT:
    - diagnose disease
    - calculate field risk
    - generate agricultural treatment advice

It only controls evidence acquisition.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ================================================================
# CONFIGURATION
# ================================================================

DEFAULT_VISUAL_THRESHOLD = 0.60

VERY_LOW_CONFIDENCE = 0.40

RECENT_SENSOR_MINUTES = 60.0

STALE_SENSOR_MINUTES = 360.0


# ================================================================
# EVIDENCE TYPES
# ================================================================

class EvidenceType(str, Enum):

    SECOND_IMAGE = "SECOND_IMAGE"

    ENVIRONMENT = "ENVIRONMENT"

    THERMAL = "THERMAL"

    SPATIAL = "SPATIAL"

    TEMPORAL = "TEMPORAL"


# ================================================================
# ACTIONS
# ================================================================

class EvidenceAction(str, Enum):

    ACCEPT = "ACCEPT"

    REQUEST_IMAGE = "REQUEST_IMAGE"

    REQUEST_SENSOR = "REQUEST_SENSOR"

    REQUEST_MULTIMODAL = "REQUEST_MULTIMODAL"


# ================================================================
# RESULT
# ================================================================

@dataclass
class AdaptiveEvidenceDecision:

    action: EvidenceAction

    reason: str

    visual_confidence: float

    threshold: float

    evidence_required: Optional[EvidenceType]

    priority: str

    visual_evidence_accepted: bool

    decision_ready: bool


# ================================================================
# HELPERS
# ================================================================

def clamp_confidence(
    confidence: float
) -> float:

    confidence = float(confidence)

    return max(
        0.0,
        min(
            1.0,
            confidence
        )
    )


def sensor_is_stale(
    sensor_age_minutes: Optional[float]
) -> bool:

    if sensor_age_minutes is None:
        return True

    return (
        float(sensor_age_minutes)
        > STALE_SENSOR_MINUTES
    )


def sensor_is_recent(
    sensor_age_minutes: Optional[float]
) -> bool:

    if sensor_age_minutes is None:
        return False

    return (
        float(sensor_age_minutes)
        <= RECENT_SENSOR_MINUTES
    )


# ================================================================
# MAIN POLICY
# ================================================================

def decide_adaptive_evidence(
    visual_confidence: float,
    *,
    threshold: float = DEFAULT_VISUAL_THRESHOLD,
    sensor_available: bool = False,
    sensor_age_minutes: Optional[float] = None,
    second_image_available: bool = False,
    thermal_available: bool = False,
) -> AdaptiveEvidenceDecision:
    """
    Decide what CRAI should do with the currently available evidence.
    """

    confidence = clamp_confidence(
        visual_confidence
    )

    threshold = clamp_confidence(
        threshold
    )


    # ============================================================
    # CASE 1 — VERY LOW CONFIDENCE
    # ============================================================

    if confidence < VERY_LOW_CONFIDENCE:

        if not second_image_available:

            return AdaptiveEvidenceDecision(

                action=EvidenceAction.REQUEST_IMAGE,

                reason=(
                    "Visual confidence is very low. "
                    "CRAI should acquire another image "
                    "before making a field assessment."
                ),

                visual_confidence=confidence,

                threshold=threshold,

                evidence_required=
                    EvidenceType.SECOND_IMAGE,

                priority="HIGH",

                visual_evidence_accepted=False,

                decision_ready=False
            )


        if not sensor_available:

            return AdaptiveEvidenceDecision(

                action=EvidenceAction.REQUEST_SENSOR,

                reason=(
                    "Visual confidence remains very low. "
                    "Environmental evidence is required."
                ),

                visual_confidence=confidence,

                threshold=threshold,

                evidence_required=
                    EvidenceType.ENVIRONMENT,

                priority="HIGH",

                visual_evidence_accepted=False,

                decision_ready=False
            )


        return AdaptiveEvidenceDecision(

            action=EvidenceAction.REQUEST_MULTIMODAL,

            reason=(
                "Visual evidence remains weak. "
                "Combine visual and environmental evidence."
            ),

            visual_confidence=confidence,

            threshold=threshold,

            evidence_required=
                EvidenceType.ENVIRONMENT,

            priority="HIGH",

            visual_evidence_accepted=False,

            decision_ready=False
        )


    # ============================================================
    # CASE 2 — BELOW RESEARCH THRESHOLD
    # ============================================================

    if confidence < threshold:

        if not second_image_available:

            return AdaptiveEvidenceDecision(

                action=EvidenceAction.REQUEST_IMAGE,

                reason=(
                    "Visual confidence is below the CRAI "
                    "acceptance threshold. Acquire another image."
                ),

                visual_confidence=confidence,

                threshold=threshold,

                evidence_required=
                    EvidenceType.SECOND_IMAGE,

                priority="MEDIUM",

                visual_evidence_accepted=False,

                decision_ready=False
            )


        if not sensor_available:

            return AdaptiveEvidenceDecision(

                action=EvidenceAction.REQUEST_SENSOR,

                reason=(
                    "Visual confidence remains below threshold. "
                    "Environmental evidence is required."
                ),

                visual_confidence=confidence,

                threshold=threshold,

                evidence_required=
                    EvidenceType.ENVIRONMENT,

                priority="MEDIUM",

                visual_evidence_accepted=False,

                decision_ready=False
            )


        return AdaptiveEvidenceDecision(

            action=EvidenceAction.REQUEST_MULTIMODAL,

            reason=(
                "Visual evidence is insufficient by itself. "
                "Combine visual and environmental evidence."
            ),

            visual_confidence=confidence,

            threshold=threshold,

            evidence_required=
                EvidenceType.ENVIRONMENT,

            priority="MEDIUM",

            visual_evidence_accepted=False,

            decision_ready=False
        )


    # ============================================================
    # CASE 3 — SUFFICIENT VISUAL CONFIDENCE
    # ============================================================

    # Visual evidence itself is acceptable.
    visual_accepted = True


    # ------------------------------------------------------------
    # Missing sensor
    # ------------------------------------------------------------

    if not sensor_available:

        return AdaptiveEvidenceDecision(

            action=EvidenceAction.REQUEST_SENSOR,

            reason=(
                "Visual confidence meets the acceptance threshold, "
                "but environmental evidence is missing."
            ),

            visual_confidence=confidence,

            threshold=threshold,

            evidence_required=
                EvidenceType.ENVIRONMENT,

            priority="MEDIUM",

            visual_evidence_accepted=True,

            decision_ready=False
        )


    # ------------------------------------------------------------
    # Stale sensor
    # ------------------------------------------------------------

    if sensor_is_stale(
        sensor_age_minutes
    ):

        return AdaptiveEvidenceDecision(

            action=EvidenceAction.REQUEST_SENSOR,

            reason=(
                "Environmental evidence is stale. "
                "CRAI should acquire a fresh sensor reading."
            ),

            visual_confidence=confidence,

            threshold=threshold,

            evidence_required=
                EvidenceType.ENVIRONMENT,

            priority="MEDIUM",

            visual_evidence_accepted=True,

            decision_ready=False
        )


    # ------------------------------------------------------------
    # Fresh/recent sensor
    # ------------------------------------------------------------

    if sensor_is_recent(
        sensor_age_minutes
    ):

        return AdaptiveEvidenceDecision(

            action=EvidenceAction.ACCEPT,

            reason=(
                "Visual confidence meets the CRAI threshold "
                "and environmental evidence is recent."
            ),

            visual_confidence=confidence,

            threshold=threshold,

            evidence_required=None,

            priority="LOW",

            visual_evidence_accepted=True,

            decision_ready=True
        )


    # ============================================================
    # FALLBACK
    # ============================================================

    return AdaptiveEvidenceDecision(

        action=EvidenceAction.REQUEST_MULTIMODAL,

        reason=(
            "Available evidence is insufficient for a "
            "confident field assessment."
        ),

        visual_confidence=confidence,

        threshold=threshold,

        evidence_required=
            EvidenceType.ENVIRONMENT,

        priority="MEDIUM",

        visual_evidence_accepted=visual_accepted,

        decision_ready=False
    )


# ================================================================
# SERIALIZATION
# ================================================================

def decision_to_dict(
    decision: AdaptiveEvidenceDecision
) -> dict:

    return {

        "action":
            decision.action.value,

        "reason":
            decision.reason,

        "visual_confidence":
            round(
                decision.visual_confidence,
                4
            ),

        "threshold":
            round(
                decision.threshold,
                4
            ),

        "evidence_required":
            (
                decision.evidence_required.value
                if decision.evidence_required
                else None
            ),

        "priority":
            decision.priority,

        "visual_evidence_accepted":
            decision.visual_evidence_accepted,

        "decision_ready":
            decision.decision_ready
    }