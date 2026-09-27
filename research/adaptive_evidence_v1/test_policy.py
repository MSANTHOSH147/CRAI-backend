"""
CRAI Adaptive Evidence Policy V1
Integration behavior tests.
"""

import sys
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__).resolve().parents[2]
)

sys.path.insert(
    0,
    str(PROJECT_ROOT)
)


from app.services.adaptive_evidence_policy import (
    decide_adaptive_evidence,
)


print("=" * 75)
print("🧠 CRAI ADAPTIVE EVIDENCE POLICY V1")
print("=" * 75)


# ================================================================
# TEST CASES
# ================================================================

cases = [

    {
        "name":
            "Very low confidence",

        "confidence":
            0.28,

        "sensor_available":
            False,
    },

    {
        "name":
            "Moderate confidence",

        "confidence":
            0.45,

        "sensor_available":
            False,
    },

    {
        "name":
            "Below threshold + sensor",

        "confidence":
            0.55,

        "sensor_available":
            True,

        "sensor_age_minutes":
            10,
    },

    {
        "name":
            "Accepted + fresh sensor",

        "confidence":
            0.72,

        "sensor_available":
            True,

        "sensor_age_minutes":
            10,
    },

    {
        "name":
            "Strong visual + missing sensor",

        "confidence":
            0.91,

        "sensor_available":
            False,
    },

    {
        "name":
            "Strong visual + stale sensor",

        "confidence":
            0.91,

        "sensor_available":
            True,

        "sensor_age_minutes":
            500,
    },
]


# ================================================================
# RUN
# ================================================================

for case in cases:

    decision = decide_adaptive_evidence(

        case["confidence"],

        sensor_available=
            case.get(
                "sensor_available",
                False
            ),

        sensor_age_minutes=
            case.get(
                "sensor_age_minutes"
            )
    )


    print("\n" + "-" * 75)

    print(
        "CASE:",
        case["name"]
    )

    print(
        "Confidence:",
        f"{case['confidence'] * 100:.1f}%"
    )

    print(
        "Action:",
        decision.action.value
    )

    print(
        "Priority:",
        decision.priority
    )

    print(
        "Evidence required:",
        (
            decision.evidence_required.value
            if decision.evidence_required
            else "NONE"
        )
    )

    print(
        "Visual evidence accepted:",
        decision.visual_evidence_accepted
    )

    print(
        "Decision ready:",
        decision.decision_ready
    )

    print(
        "Reason:",
        decision.reason
    )


# ================================================================
# ASSERTIONS
# ================================================================

print("\n" + "=" * 75)
print("🧪 ASSERTION TESTS")
print("=" * 75)


# Low confidence → image
decision = decide_adaptive_evidence(
    0.30
)

assert (
    decision.action.value
    == "REQUEST_IMAGE"
)

assert (
    decision.decision_ready
    is False
)


# Below 60 → image
decision = decide_adaptive_evidence(
    0.59
)

assert (
    decision.decision_ready
    is False
)


# Exactly 60 + recent sensor → accept
decision = decide_adaptive_evidence(
    0.60,
    sensor_available=True,
    sensor_age_minutes=10
)

assert (
    decision.action.value
    == "ACCEPT"
)

assert (
    decision.visual_evidence_accepted
    is True
)

assert (
    decision.decision_ready
    is True
)


# Strong visual but missing sensor → sensor
decision = decide_adaptive_evidence(
    0.90,
    sensor_available=False
)

assert (
    decision.action.value
    == "REQUEST_SENSOR"
)

assert (
    decision.visual_evidence_accepted
    is True
)

assert (
    decision.decision_ready
    is False
)


# Stale sensor → refresh
decision = decide_adaptive_evidence(
    0.90,
    sensor_available=True,
    sensor_age_minutes=500
)

assert (
    decision.action.value
    == "REQUEST_SENSOR"
)

assert (
    decision.decision_ready
    is False
)


print(
    "\n✅ ALL ADAPTIVE POLICY TESTS PASSED"
)

print("=" * 75)