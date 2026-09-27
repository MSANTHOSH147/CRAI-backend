import pytest

from app.services.adaptive_evidence_service import (
    evaluate_adaptive_evidence,
)

from app.services.evidence_normalizer import (
    normalize_evidence,
)


def test_missing_visual_requests_image():

    result = evaluate_adaptive_evidence(
        visual_confidence=None,
        sensor_available=False,
    )

    assert result["action"] == "REQUEST_IMAGE"
    assert result["decision_ready"] is False


def test_low_visual_requests_second_image():

    result = evaluate_adaptive_evidence(
        visual_confidence=0.42,
        sensor_available=True,
        sensor_age_minutes=5,
    )

    assert result["action"] == "REQUEST_IMAGE"

    assert (
        result["evidence_required"]
        == "SECOND_IMAGE"
    )

    assert result["decision_ready"] is False


def test_strong_visual_missing_sensor_requests_sensor():

    result = evaluate_adaptive_evidence(
        visual_confidence=0.91,
        sensor_available=False,
    )

    assert result["action"] == "REQUEST_SENSOR"
    assert result["decision_ready"] is False


def test_strong_visual_fresh_sensor_accepts():

    result = evaluate_adaptive_evidence(
        visual_confidence=0.91,
        sensor_available=True,
        sensor_age_minutes=5,
    )

    assert result["action"] == "ACCEPT_AND_FUSE"
    assert result["decision_ready"] is True


def test_strong_visual_stale_sensor_requests_sensor():

    result = evaluate_adaptive_evidence(
        visual_confidence=0.91,
        sensor_available=True,
        sensor_age_minutes=400,
    )

    assert result["action"] == "REQUEST_SENSOR"
    assert result["decision_ready"] is False


def test_quality_failure_requests_retake():

    result = evaluate_adaptive_evidence(
        visual_confidence=0.90,
        sensor_available=True,
        sensor_age_minutes=5,
        image_quality={
            "status": "RETAKE_REQUIRED",
            "failed_checks": ["sharpness"],
        },
    )

    assert result["action"] == "REQUEST_IMAGE"

    assert (
        result["evidence_required"]
        == "RETAKE_IMAGE"
    )


def test_normalizer_accepts_percent_confidence():

    result = normalize_evidence(
        {
            "confidence": 87.0,
            "soil_moisture": 31.0,
            "temperature": 28.0,
            "humidity": 74.0,
            "thermal_anomaly": 0.3,
            "infected_neighbor_count": 2,
            "total_neighbor_count": 5,
            "history_length": 3,
        }
    )

    assert (
        result.visual_confidence
        == pytest.approx(0.87)
    )

    assert result.sensor_available is True
    assert result.thermal_available is True
    assert result.spatial_available is True
    assert result.temporal_available is True


def test_normalizer_marks_missing_sensor():

    result = normalize_evidence(
        {
            "confidence": 0.91,
        }
    )

    assert result.sensor_available is False
    assert result.sensor_freshness == "UNKNOWN"
