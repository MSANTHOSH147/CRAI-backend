# CRAI Adaptive Evidence Acquisition V1

## Objective

Evaluate whether CRAI can avoid making low-confidence visual
decisions and instead request additional evidence.

The experiment uses the frozen CRAI Tomato Specialist V1 and the
same 71-image PlantDoc benchmark used by CRAI Tomato Benchmark V1.

## Research Question

Can confidence-aware evidence acquisition improve the reliability
of accepted visual decisions while identifying observations that
require additional evidence?

## Baseline

Model:

CRAI Tomato Specialist V1

Architecture:

MobileNetV3-Small

Test set:

PlantDoc test — 71 images

Baseline:

Accuracy = 59.15%

Macro F1 = 51.63%

## Adaptive Policy

For a selected confidence threshold T:

confidence >= T
    -> accept visual assessment

confidence < T
    -> request additional evidence

Additional evidence may include:

- second image
- improved image
- environmental sensor reading
- spatial observation
- temporal re-observation
- thermal observation when available

## Metrics

### Coverage

Percentage of observations accepted using visual evidence alone.

Coverage = accepted observations / total observations

### Selective Accuracy

Accuracy among observations accepted by CRAI.

Selective Accuracy =
correct accepted observations / accepted observations

### Selective Error Rate

1 - selective accuracy

### Evidence Request Rate

Percentage of observations requiring additional evidence.

Evidence Request Rate =
rejected observations / total observations

## Thresholds

Evaluate:

50%
60%
70%
80%
90%

## Important Limitation

This experiment does not claim that additional evidence corrects
the rejected cases.

It only evaluates whether confidence-aware escalation identifies
a subset of observations with improved visual reliability.

A future experiment will measure whether actual additional evidence
improves the final field decision.

## Desired Research Outcome

A useful adaptive system should demonstrate a trade-off:

higher evidence threshold
    ->
lower visual-only coverage
    ->
higher reliability of accepted cases

The final CRAI system should choose an operational threshold based
on safety, field conditions, sensing cost, and acceptable uncertainty.