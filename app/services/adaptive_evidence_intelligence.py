"""
CRAI Adaptive Evidence Intelligence V2

Cost-aware next-best-evidence policy.

This module is a deterministic engineering policy layer. It does NOT claim
scientific optimality. Its purpose is to make CRAI choose among available
acquisition paths using observable evidence value, decision impact, source
reliability and relative acquisition burden.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


DEFAULT_STOP_UTILITY = 0.20
DEFAULT_READY_SCORE = 0.80
DEFAULT_MAX_ACTIONS = 3


@dataclass
class EvidenceCandidate:
    evidence: str
    source: str
    available: bool
    reliability: float
    information_value: float
    decision_impact: float
    acquisition_cost: float
    acquisition_time: float
    model: Optional[str] = None
    reason: str = ""
    utility: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def _clamp(value: Any, low: float = 0.0, high: float = 1.0) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return low
    return max(low, min(high, value))


def evidence_reliability(
    *,
    available: bool,
    freshness: Optional[str] = None,
    quality: Any = None,
    source: Optional[str] = None,
    valid: bool = True,
) -> float:
    """Estimate reliability from observable metadata only."""

    if not available or not valid:
        return 0.0

    freshness_factor = {
        "FRESH": 1.00,
        "RECENT": 0.85,
        "STALE": 0.35,
        "VERY_STALE": 0.15,
        "UNAVAILABLE": 0.0,
        "UNKNOWN": 0.60,
        None: 0.60,
    }.get(str(freshness).upper() if freshness else None, 0.60)

    quality_factor = 1.0 if quality is None else _clamp(quality)

    provenance_factor = 1.0
    source_upper = str(source or "").upper()
    if source_upper in {"SIMULATED", "SYNTHETIC", "DEMO"}:
        provenance_factor = 0.70

    return round(_clamp(freshness_factor * quality_factor * provenance_factor), 3)


def candidate_utility(
    *,
    information_value: Any,
    decision_impact: Any,
    reliability: Any,
    acquisition_cost: Any,
    acquisition_time: Any,
) -> float:
    """
    Relative utility of acquiring evidence.

    numerator = information value × decision impact × reliability
    burden    = 70% relative acquisition cost + 30% relative time

    A small fixed acquisition floor prevents a very cheap source from
    dominating solely because its normalized burden approaches zero.
    """

    iv = _clamp(information_value)
    impact = _clamp(decision_impact)
    rel = _clamp(reliability)
    cost = max(0.0, _clamp(acquisition_cost))
    time = max(0.0, _clamp(acquisition_time))

    burden = 0.70 * cost + 0.30 * time
    effective_burden = 0.20 + burden

    return round(
        (iv * impact * rel) / effective_burden,
        3,
    )


def rank_next_best_evidence(
    candidates: List[EvidenceCandidate],
) -> List[dict]:
    """Rank only actually acquirable candidates."""

    ranked_candidates: List[EvidenceCandidate] = []

    for item in candidates:
        if not item.available:
            continue

        item.utility = candidate_utility(
            information_value=item.information_value,
            decision_impact=item.decision_impact,
            reliability=item.reliability,
            acquisition_cost=item.acquisition_cost,
            acquisition_time=item.acquisition_time,
        )
        ranked_candidates.append(item)

    ranked_candidates.sort(
        key=lambda x: (
            x.utility,
            x.decision_impact,
            x.reliability,
            -x.acquisition_cost,
        ),
        reverse=True,
    )

    return [item.to_dict() for item in ranked_candidates]


def evidence_agreement(
    evidence_states: Dict[str, str],
) -> dict:
    normalized = {}
    supporting = []
    conflicting = []
    unknown = []

    for source, state in evidence_states.items():
        value = str(state or "UNKNOWN").upper()
        if value not in {"SUPPORTING", "CONFLICTING", "UNKNOWN"}:
            value = "UNKNOWN"

        normalized[source] = value

        if value == "SUPPORTING":
            supporting.append(source)
        elif value == "CONFLICTING":
            conflicting.append(source)
        else:
            unknown.append(source)

    known = len(supporting) + len(conflicting)

    if conflicting:
        status = "CONFLICTING"
    elif known == 0:
        status = "UNKNOWN"
    elif len(supporting) == known:
        status = "AGREEING"
    else:
        status = "MIXED"

    agreement_ratio = len(supporting) / known if known else None

    return {
        "status": status,
        "agreement_ratio": round(agreement_ratio, 3) if agreement_ratio is not None else None,
        "supporting": supporting,
        "conflicting": conflicting,
        "unknown": unknown,
        "states": normalized,
    }


def should_stop_acquisition(
    *,
    decision_readiness: Any,
    best_candidate_utility: Any,
    actions_taken: int = 0,
    max_actions: int = DEFAULT_MAX_ACTIONS,
    conflict_present: bool = False,
) -> dict:
    """Conservative stopping rule; it never declares readiness by itself."""

    readiness = _clamp(decision_readiness)
    utility = max(0.0, float(best_candidate_utility or 0.0))

    if conflict_present:
        return {
            "action": "CONTINUE",
            "reason": "Conflicting evidence requires targeted verification.",
            "stop": False,
        }

    if actions_taken >= max_actions:
        return {
            "action": "STOP",
            "reason": "Evidence acquisition budget reached.",
            "stop": True,
        }

    if readiness >= DEFAULT_READY_SCORE and utility < DEFAULT_STOP_UTILITY:
        return {
            "action": "STOP",
            "reason": "Expected value of additional evidence is low relative to current decision readiness.",
            "stop": True,
        }

    return {
        "action": "CONTINUE",
        "reason": "Additional evidence may materially improve the decision.",
        "stop": False,
    }


def build_adaptive_intelligence(
    *,
    decision_readiness: Any,
    evidence_states: Dict[str, str],
    candidates: List[EvidenceCandidate],
    actions_taken: int = 0,
    max_actions: int = DEFAULT_MAX_ACTIONS,
) -> dict:
    agreement = evidence_agreement(evidence_states)
    ranked = rank_next_best_evidence(candidates)

    best_utility = ranked[0]["utility"] if ranked else 0.0

    stop = should_stop_acquisition(
        decision_readiness=decision_readiness,
        best_candidate_utility=best_utility,
        actions_taken=actions_taken,
        max_actions=max_actions,
        conflict_present=bool(agreement["conflicting"]),
    )

    return {
        "version": "ADAPTIVE_EVIDENCE_INTELLIGENCE_V2",
        "decision_readiness": round(_clamp(decision_readiness), 3),
        "evidence_agreement": agreement,
        "ranked_candidates": ranked,
        "next_best_evidence": ranked[0] if ranked else None,
        "stopping_policy": stop,
        "policy": {
            "utility_formula": "information_value * decision_impact * reliability / (0.20 + 0.70*cost + 0.30*time)",
            "cost_weight": 0.70,
            "time_weight": 0.30,
            "stop_utility_threshold": DEFAULT_STOP_UTILITY,
            "ready_score_threshold": DEFAULT_READY_SCORE,
            "max_acquisition_actions": max_actions,
            "status": "ENGINEERING_POLICY_NOT_SCIENTIFICALLY_VALIDATED",
        },
    }
