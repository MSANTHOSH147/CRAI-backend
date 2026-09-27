from app.services.adaptive_evidence_intelligence import (
    EvidenceCandidate,
    build_adaptive_intelligence,
)

candidates = [
    EvidenceCandidate(
        evidence="FRESH_SENSOR",
        source="ESP32",
        available=True,
        reliability=0.95,
        information_value=0.85,
        decision_impact=0.90,
        acquisition_cost=0.15,
        acquisition_time=0.10,
        reason="Environmental evidence can materially change the field assessment.",
    ),
    EvidenceCandidate(
        evidence="SECOND_IMAGE",
        source="SMARTPHONE",
        available=True,
        reliability=0.90,
        information_value=0.65,
        decision_impact=0.70,
        acquisition_cost=0.10,
        acquisition_time=0.15,
        reason="A second view can reduce visual uncertainty.",
    ),
    EvidenceCandidate(
        evidence="THERMAL",
        source="THERMAL_CAMERA",
        available=False,
        reliability=0.95,
        information_value=0.70,
        decision_impact=0.65,
        acquisition_cost=0.80,
        acquisition_time=0.60,
        reason="Higher-cost evidence reserved for unresolved cases.",
    ),
]

result = build_adaptive_intelligence(
    decision_readiness=0.55,
    evidence_states={
        "visual": "SUPPORTING",
        "environmental": "UNKNOWN",
        "spatial": "UNKNOWN",
        "temporal": "UNKNOWN",
    },
    candidates=candidates,
)

print("NEXT:", result["next_best_evidence"]["evidence"])
print("UTILITY:", result["next_best_evidence"]["utility"])
print("AGREEMENT:", result["evidence_agreement"]["status"])
print("STOP:", result["stopping_policy"]["action"])
