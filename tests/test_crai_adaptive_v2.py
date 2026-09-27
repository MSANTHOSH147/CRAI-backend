import pytest

from app.services.adaptive_evidence_service import evaluate_adaptive_evidence
from app.services.evidence_service import evaluate_evidence


def test_cost_aware_prefers_second_image_for_low_visual_confidence():
    result = evaluate_adaptive_evidence(
        visual_confidence=0.48,
        sensor_available=True,
        sensor_age_minutes=5,
    )
    assert result["decision_ready"] is False
    assert result["evidence_required"] == "SECOND_IMAGE"
    assert result["next_best_source"] == "SMARTPHONE"
    assert result["cost_aware_selection"]["selected"]["model"] == "CRAI_V3"
    assert result["cost_aware_selection"]["ranked_candidates"]


def test_cost_aware_prefers_fresh_sensor_for_strong_visual_without_sensor():
    result = evaluate_adaptive_evidence(
        visual_confidence=0.92,
        sensor_available=False,
    )
    assert result["decision_ready"] is False
    assert result["evidence_required"] == "ENVIRONMENT"
    assert result["next_best_source"] == "ESP32"
    assert result["cost_aware_selection"]["selected"]["evidence"] == "FRESH_SENSOR_READING"


def test_stale_sensor_is_context_not_current_evidence():
    result = evaluate_evidence(
        prediction="Tomato_Healthy",
        confidence=64.9,
        sensor={
            "device_id": "ESP32_001",
            "soil_moisture": 24,
            "temperature": 31,
            "humidity": 78,
            "timestamp": "2020-01-01T00:00:00+00:00",
            "source": "REAL",
        },
    )
    environmental = result["details"]["environmental"]
    assert environmental["available"] is True
    assert environmental["usable"] is False
    assert environmental["evidence_scope"] == "HISTORICAL_OR_STALE_CONTEXT"
    assert result["decision_ready"] is False
    assert "FRESH_SENSOR_READING" in result["requested_evidence"]


def test_adaptive_sensor_wrapper_no_key_error():
    result = evaluate_adaptive_evidence(
        visual_confidence=0.91,
        sensor_available=True,
        sensor_freshness="FRESH",
    )
    assert result["decision_ready"] is True
    assert result["adaptive_action"] == "DECISION_READY"


def test_uav_is_ranked_only_when_a_real_uav_path_is_available():
    from app.services.adaptive_evidence_service import evaluate_adaptive_evidence
    result = evaluate_adaptive_evidence(
        visual_confidence=0.90,
        sensor_available=True,
        sensor_freshness="FRESH",
        spatial_available=False,
        uav_available=True,
    )
    assert result["decision_ready"] is True
    assert any(
        item["evidence"] == "UAV_OBSERVATION"
        for item in result["cost_aware_selection"]["ranked_candidates"]
    )
