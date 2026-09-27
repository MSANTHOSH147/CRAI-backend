"""
CRAI Adaptive Evidence Service test.
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


from app.services.adaptive_evidence_service import (
    evaluate_adaptive_evidence,
)


print("=" * 75)
print("🧠 CRAI ADAPTIVE EVIDENCE SERVICE")
print("=" * 75)


cases = [

    {
        "name": "No image prediction",

        "visual_confidence": None,

        "sensor_available": False,
    },

    {
        "name": "Low visual confidence",

        "visual_confidence": 0.35,

        "sensor_available": False,
    },

    {
        "name": "Moderate visual confidence",

        "visual_confidence": 0.55,

        "sensor_available": True,

        "sensor_age_minutes": 10,
    },

    {
        "name": "Accepted multimodal evidence",

        "visual_confidence": 0.75,

        "sensor_available": True,

        "sensor_age_minutes": 10,
    },

    {
        "name": "Strong image but missing sensor",

        "visual_confidence": 0.90,

        "sensor_available": False,
    },

    {
        "name": "Strong image + stale sensor",

        "visual_confidence": 0.90,

        "sensor_available": True,

        "sensor_age_minutes": 500,
    },
]


for case in cases:

    result = evaluate_adaptive_evidence(
        **{
            key: value
            for key, value in case.items()
            if key != "name"
        }
    )

    print("\n" + "-" * 75)

    print(
        "CASE:",
        case["name"]
    )

    print(
        "Action:",
        result["action"]
    )

    print(
        "Evidence:",
        result["evidence_required"]
    )

    print(
        "Priority:",
        result["priority"]
    )

    print(
        "Decision ready:",
        result["decision_ready"]
    )

    print(
        "Reason:",
        result["reason"]
    )


# ================================================================
# ASSERTIONS
# ================================================================

print("\n" + "=" * 75)
print("🧪 SERVICE ASSERTIONS")
print("=" * 75)


result = evaluate_adaptive_evidence(
    visual_confidence=None
)

assert (
    result["action"]
    == "REQUEST_IMAGE"
)

assert (
    result["decision_ready"]
    is False
)


result = evaluate_adaptive_evidence(
    visual_confidence=0.55,
    sensor_available=True,
    sensor_age_minutes=10
)

assert (
    result["action"]
    == "REQUEST_IMAGE"
)


result = evaluate_adaptive_evidence(
    visual_confidence=0.75,
    sensor_available=True,
    sensor_age_minutes=10
)

assert (
    result["action"]
    == "REQUEST_IMAGE"
)

assert (
    result["decision_ready"]
    is False
)


result = evaluate_adaptive_evidence(
    visual_confidence=0.90,
    sensor_available=False
)

assert (
    result["action"]
    == "REQUEST_SENSOR"
)

assert (
    result["decision_ready"]
    is False
)


print(
    "\n✅ ALL ADAPTER TESTS PASSED"
)

print("=" * 75)
