from app.services.fusion_risk_service import (
    calculate_field_risk,
)


def test_visual_only_has_low_assessment_confidence():

    result = calculate_field_risk(
        disease="Tomato_Early_Blight",
        visual_confidence=0.90,
    )

    assert result["version"] == "FUSION_V1_5"

    assert result["risk_score"] > 0

    assert (
        result["assessment_confidence"]
        == "LOW"
    )


def test_full_evidence_produces_high_confidence():

    result = calculate_field_risk(
        disease="Tomato_Early_Blight",
        visual_confidence=0.90,
        soil_moisture=24,
        temperature=34,
        humidity=84,
        infected_neighbor_count=3,
        total_neighbor_count=5,
        risk_history=[
            25,
            40,
            58,
        ],
        sensor_freshness="FRESH",
    )

    assert (
        result["assessment_confidence"]
        == "HIGH"
    )

    assert result["risk_score"] > 0

    assert len(
        result["weights"]
    ) == 4


def test_stale_sensor_has_lower_environmental_quality():

    fresh = calculate_field_risk(
        disease="Tomato_Early_Blight",
        visual_confidence=0.90,
        soil_moisture=24,
        temperature=34,
        humidity=84,
        sensor_freshness="FRESH",
    )

    stale = calculate_field_risk(
        disease="Tomato_Early_Blight",
        visual_confidence=0.90,
        soil_moisture=24,
        temperature=34,
        humidity=84,
        sensor_freshness="STALE",
    )

    assert (
        stale[
            "evidence_summary"
        ]["quality"]["environmental"]
        <
        fresh[
            "evidence_summary"
        ]["quality"]["environmental"]
    )


def test_missing_evidence_is_not_given_weight():

    result = calculate_field_risk(
        disease="Tomato_Early_Blight",
        visual_confidence=0.90,
    )

    assert (
        "environmental"
        not in result["weights"]
    )

    assert (
        "spatial"
        not in result["weights"]
    )

    assert (
        "temporal"
        not in result["weights"]
    )


def test_healthy_prediction_has_low_visual_signal():

    result = calculate_field_risk(
        disease="Tomato_Healthy",
        visual_confidence=0.95,
    )

    assert (
        result["breakdown"]["visual"]
        < 10
    )
