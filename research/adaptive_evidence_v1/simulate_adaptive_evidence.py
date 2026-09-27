# ================================================================
# CRAI ADAPTIVE EVIDENCE ACQUISITION V1
#
# Uses the frozen 71-image CRAI Tomato Benchmark.
#
# IMPORTANT:
# This experiment does NOT pretend that additional evidence
# magically fixes incorrect predictions.
#
# It measures:
#   confidence -> accept OR request more evidence
#
# This is a selective prediction / risk-coverage experiment.
# ================================================================

from pathlib import Path
import json

import numpy as np
import pandas as pd


# ================================================================
# CONFIG
# ================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ------------------------------------------------
# Preferred local benchmark path
# ------------------------------------------------

BENCHMARK_PATHS = [

    PROJECT_ROOT
    / "backend"
    / "research"
    / "crai_tomato_benchmark_v1"
    / "per_image_predictions.csv",

    PROJECT_ROOT
    / "research"
    / "crai_tomato_benchmark_v1"
    / "per_image_predictions.csv",

    Path(
        "research/crai_tomato_benchmark_v1/"
        "per_image_predictions.csv"
    ),
]


OUTPUT_DIR = (
    PROJECT_ROOT
    / "research"
    / "adaptive_evidence_v1"
    / "results"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


THRESHOLDS = [
    0.50,
    0.60,
    0.70,
    0.80,
    0.90,
]


# ================================================================
# FIND BENCHMARK
# ================================================================

benchmark_file = None

for candidate in BENCHMARK_PATHS:

    if candidate.exists():

        benchmark_file = candidate
        break


if benchmark_file is None:

    print()
    print("=" * 75)
    print("❌ BENCHMARK FILE NOT FOUND")
    print("=" * 75)

    print(
        "\nExpected:"
    )

    for path in BENCHMARK_PATHS:
        print(" ", path)

    print(
        "\nCopy the Kaggle benchmark file:"
    )

    print(
        "per_image_predictions.csv"
    )

    print(
        "into one of the locations above."
    )

    raise SystemExit(1)


# ================================================================
# LOAD
# ================================================================

df = pd.read_csv(
    benchmark_file
)


required_columns = {
    "actual",
    "specialist_prediction",
    "specialist_confidence",
    "specialist_correct",
}


missing = (
    required_columns
    - set(df.columns)
)


if missing:

    raise ValueError(
        "Missing required columns: "
        + str(sorted(missing))
    )


print("=" * 75)
print("🧠 CRAI ADAPTIVE EVIDENCE ACQUISITION V1")
print("=" * 75)

print(
    "Benchmark:",
    benchmark_file
)

print(
    "Observations:",
    len(df)
)


# ================================================================
# NORMALIZE DATA
# ================================================================

df["confidence"] = pd.to_numeric(
    df["specialist_confidence"],
    errors="coerce"
)

df["correct"] = (
    df["specialist_correct"]
    .astype(bool)
)


if df["confidence"].isna().any():

    raise ValueError(
        "Invalid confidence values found."
    )


# ================================================================
# BASELINE
# ================================================================

total = len(df)

baseline_correct = int(
    df["correct"].sum()
)

baseline_accuracy = (
    baseline_correct / total
)


print("\n" + "=" * 75)
print("BASELINE — VISUAL MODEL")
print("=" * 75)

print(
    "Total observations:",
    total
)

print(
    "Correct:",
    baseline_correct
)

print(
    "Incorrect:",
    total - baseline_correct
)

print(
    "Accuracy:",
    f"{baseline_accuracy * 100:.2f}%"
)


# ================================================================
# THRESHOLD EXPERIMENT
# ================================================================

results = []

for threshold in THRESHOLDS:

    accepted = (
        df["confidence"]
        >= threshold
    )

    requested = ~accepted

    accepted_count = int(
        accepted.sum()
    )

    requested_count = int(
        requested.sum()
    )

    accepted_correct = int(
        (
            accepted
            & df["correct"]
        ).sum()
    )

    accepted_wrong = (
        accepted_count
        - accepted_correct
    )


    # ------------------------------------------------------------
    # Coverage
    # ------------------------------------------------------------

    coverage = (
        accepted_count / total
    )


    # ------------------------------------------------------------
    # Evidence request rate
    # ------------------------------------------------------------

    request_rate = (
        requested_count / total
    )


    # ------------------------------------------------------------
    # Selective accuracy
    # ------------------------------------------------------------

    if accepted_count > 0:

        selective_accuracy = (
            accepted_correct
            / accepted_count
        )

    else:

        selective_accuracy = 0.0


    # ------------------------------------------------------------
    # Selective error
    # ------------------------------------------------------------

    selective_error = (
        accepted_wrong
        / accepted_count
        if accepted_count > 0
        else 0.0
    )


    # ------------------------------------------------------------
    # High-confidence wrong cases
    # ------------------------------------------------------------

    high_conf_wrong = int(
        (
            accepted
            & ~df["correct"]
        ).sum()
    )


    # ------------------------------------------------------------
    # Accepted / rejected correctness
    # ------------------------------------------------------------

    rejected_correct = int(
        (
            requested
            & df["correct"]
        ).sum()
    )

    rejected_wrong = int(
        (
            requested
            & ~df["correct"]
        ).sum()
    )


    results.append({

        "threshold":
            threshold,

        "total_observations":
            total,

        "accepted_observations":
            accepted_count,

        "additional_evidence_requests":
            requested_count,

        "coverage":
            coverage,

        "evidence_request_rate":
            request_rate,

        "accepted_correct":
            accepted_correct,

        "accepted_wrong":
            accepted_wrong,

        "selective_accuracy":
            selective_accuracy,

        "selective_error_rate":
            selective_error,

        "rejected_correct":
            rejected_correct,

        "rejected_wrong":
            rejected_wrong,

        "high_confidence_wrong_accepted":
            high_conf_wrong,
    })


# ================================================================
# RESULTS TABLE
# ================================================================

results_df = pd.DataFrame(
    results
)


print("\n" + "=" * 75)
print("📊 ADAPTIVE EVIDENCE RESULTS")
print("=" * 75)

print()

print(
    results_df[
        [
            "threshold",
            "accepted_observations",
            "additional_evidence_requests",
            "coverage",
            "selective_accuracy",
            "high_confidence_wrong_accepted",
        ]
    ].to_string(
        index=False,
        formatters={
            "coverage":
                lambda x:
                f"{x * 100:.2f}%",

            "selective_accuracy":
                lambda x:
                f"{x * 100:.2f}%"
        }
    )
)


# ================================================================
# DETAILED INTERPRETATION
# ================================================================

print("\n" + "=" * 75)
print("🔎 THRESHOLD INTERPRETATION")
print("=" * 75)

for row in results:

    threshold = row[
        "threshold"
    ]

    coverage = row[
        "coverage"
    ]

    selective_accuracy = row[
        "selective_accuracy"
    ]

    requests = row[
        "additional_evidence_requests"
    ]

    high_conf_wrong = row[
        "high_confidence_wrong_accepted"
    ]


    print()

    print(
        f"Threshold {threshold * 100:.0f}%"
    )

    print(
        f"  Visual-only coverage : "
        f"{coverage * 100:.2f}%"
    )

    print(
        f"  Evidence requests    : "
        f"{requests}/{total}"
    )

    print(
        f"  Accepted accuracy    : "
        f"{selective_accuracy * 100:.2f}%"
    )

    print(
        f"  High-conf errors     : "
        f"{high_conf_wrong}"
    )


# ================================================================
# FIND A REASONABLE OPERATING POINT
#
# We do NOT automatically claim this is the best threshold.
#
# Here we identify thresholds with:
#   - selective accuracy >= 80%
#   - highest possible coverage
#
# If none reaches 80%, report that honestly.
# ================================================================

target_accuracy = 0.80

eligible = results_df[
    results_df[
        "selective_accuracy"
    ]
    >= target_accuracy
]


print("\n" + "=" * 75)
print("🎯 CANDIDATE OPERATING POINT")
print("=" * 75)

if len(eligible) == 0:

    print(
        "No tested threshold reached "
        f"{target_accuracy * 100:.0f}% "
        "selective accuracy."
    )

    print(
        "Do not force an operating threshold."
    )

else:

    best = eligible.sort_values(
        "coverage",
        ascending=False
    ).iloc[0]

    print(
        "Candidate threshold:",
        f"{best['threshold'] * 100:.0f}%"
    )

    print(
        "Coverage:",
        f"{best['coverage'] * 100:.2f}%"
    )

    print(
        "Selective accuracy:",
        f"{best['selective_accuracy'] * 100:.2f}%"
    )

    print(
        "Evidence requests:",
        int(
            best[
                "additional_evidence_requests"
            ]
        )
    )


# ================================================================
# RISK-COVERAGE DATA
# ================================================================

risk_coverage = results_df[
    [
        "threshold",
        "coverage",
        "selective_accuracy",
        "selective_error_rate",
        "evidence_request_rate",
    ]
].copy()

risk_coverage[
    "selective_risk"
] = risk_coverage[
    "selective_error_rate"
]


# ================================================================
# SAVE
# ================================================================

results_csv = (
    OUTPUT_DIR
    / "adaptive_evidence_results.csv"
)

risk_csv = (
    OUTPUT_DIR
    / "risk_coverage_curve.csv"
)

summary_json = (
    OUTPUT_DIR
    / "adaptive_evidence_summary.json"
)


results_df.to_csv(
    results_csv,
    index=False
)

risk_coverage.to_csv(
    risk_csv,
    index=False
)


summary = {

    "experiment":
        "CRAI_ADAPTIVE_EVIDENCE_V1",

    "benchmark":
        str(benchmark_file),

    "observations":
        total,

    "baseline_accuracy":
        float(baseline_accuracy),

    "thresholds":
        THRESHOLDS,

    "results":
        results,

    "target_selective_accuracy":
        target_accuracy,

    "interpretation":
        (
            "Confidence-aware escalation was evaluated "
            "as a selective prediction policy. "
            "Rejected observations are assumed to require "
            "additional evidence; no corrective benefit "
            "from that evidence is assumed."
        )
}


with open(
    summary_json,
    "w"
) as f:

    json.dump(
        summary,
        f,
        indent=2
    )


# ================================================================
# FINAL
# ================================================================

print("\n" + "=" * 75)
print("✅ ADAPTIVE EVIDENCE EXPERIMENT COMPLETE")
print("=" * 75)

print(
    "Results:",
    results_csv
)

print(
    "Risk-coverage:",
    risk_csv
)

print(
    "Summary:",
    summary_json
)

print()
print(
    "🔥 No model training performed."
)

print(
    "🔥 No test images modified."
)

print(
    "🔥 No artificial correction of wrong predictions."
)

print("=" * 75)