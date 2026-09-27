from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.farm_event import FarmEvent
from app.models.field_sensor import FieldSensorReading
from app.services.farm_event_service import (
    action_for_authoritative_decision,
    compute_integrity_hash,
    create_or_update_event,
    verify_integrity,
)
from app.services.field_simulator_service import (
    configure,
    generate_reading_payload,
)


def _db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_simulator_is_explicitly_simulated_and_deterministic():
    state = configure(
        device_id="CRAI-SIM-TEST",
        farm_id=1,
        zone_id="A1",
        scenario="DISEASE_RISK",
        interval=15,
        seed=42,
        reset_step=True,
    )

    state.step = 3

    first = generate_reading_payload(state)
    second = generate_reading_payload(state)

    assert first["source"] == "SIMULATED"
    assert first["soil_moisture"] == second["soil_moisture"]
    assert first["leaf_wetness"] == second["leaf_wetness"]


def test_simulator_supports_production_sensor_fields():
    state = configure(
        device_id="CRAI-SIM-TEST",
        farm_id=1,
        zone_id="A1",
        scenario="NORMAL",
        interval=15,
        seed=42,
        reset_step=True,
    )

    payload = generate_reading_payload(state)

    assert {
        "soil_moisture",
        "soil_temperature",
        "soil_ph",
        "soil_ec",
        "leaf_wetness",
    }.issubset(payload)


def test_action_mapping_uses_authoritative_decision_and_risk():
    assert (
        action_for_authoritative_decision({"ready": True}, "LOW")
        == "MONITOR"
    )

    assert (
        action_for_authoritative_decision({"ready": True}, "MODERATE")
        == "INVESTIGATE"
    )

    assert (
        action_for_authoritative_decision({"ready": True}, "HIGH")
        == "PROTECT_AND_ALERT"
    )

    assert (
        action_for_authoritative_decision({"ready": True}, "CRITICAL")
        == "IMMEDIATE_PROTECTIVE_ACTION_AND_ALERT"
    )

    assert (
        action_for_authoritative_decision(
            {"ready": False, "action": "COLLECT_ADDITIONAL_EVIDENCE"},
            None,
        )
        == "INVESTIGATE"
    )


def _analysis(
    risk_level: str,
    score: float,
    prediction: str = "Tomato_Early_Blight",
):
    return {
        "status": "ANALYSIS_COMPLETE",
        "disease": {
            "prediction": prediction,
            "confidence": 91.0,
        },
        "risk": {
            "risk_level": risk_level,
            "risk_score": score,
            "breakdown": {},
        },
        "decision": {
            "ready": True,
            "action": "DECISION_READY",
            "priority": risk_level,
        },
        "context": {
            "crop": "Tomato",
            "growth_stage": "Vegetative",
            "temporal": {
                "available": True,
            },
            "spatial": {
                "available": True,
            },
        },
        "judge_intelligence": {
            "provenance": {
                "source": "CRAI_FUSION_V1_5",
            },
        },
    }


def test_event_lifecycle_and_before_during_after():
    db = _db()

    reading = FieldSensorReading(
        reading_id="SIM-1",
        device_id="CRAI-SIM-001",
        farm_id=1,
        zone_id="A1",
        source="SIMULATED",
        soil_moisture=18,
        soil_temperature=38,
        soil_ph=6.0,
        soil_ec=1.8,
        leaf_wetness=94,
        temperature=39,
        humidity=92,
        timestamp=datetime.utcnow(),
    )

    db.add(reading)
    db.commit()

    # ---------------------------------------------------------
    # 1. EVENT DETECTED
    # ---------------------------------------------------------
    event = create_or_update_event(
        db,
        analysis=_analysis("HIGH", 76),
        farm_id=1,
        zone_id="A1",
        device_id="CRAI-SIM-001",
        crop="Tomato",
        crop_stage="Vegetative",
    )

    assert event is not None
    assert event.status == "CONFIRMED"
    assert event.during_state["phase"] == "DURING"
    assert event.before_state["status"] == "AVAILABLE"
    assert event.after_state["status"] == "NOT_AVAILABLE"
    assert event.integrity_hash

    # ---------------------------------------------------------
    # 2. EVENT IMPROVES → RECOVERY
    # ---------------------------------------------------------
    event = create_or_update_event(
        db,
        analysis=_analysis(
            "MODERATE",
            45,
            prediction="Tomato_Improving",
        ),
        farm_id=1,
        zone_id="A1",
        device_id="CRAI-SIM-001",
        crop="Tomato",
        crop_stage="Vegetative",
    )

    assert event.status == "RECOVERING"
    assert event.during_state["phase"] == "RECOVERY"
    assert event.after_state["status"] == "NOT_AVAILABLE"
    assert event.resolved_at is None

    # ---------------------------------------------------------
    # 3. SAFE CONFIRMATION → AFTER → RESOLVED
    # ---------------------------------------------------------
    event = create_or_update_event(
        db,
        analysis=_analysis(
            "LOW",
            15,
            prediction="Tomato_Healthy",
        ),
        farm_id=1,
        zone_id="A1",
        device_id="CRAI-SIM-001",
        crop="Tomato",
        crop_stage="Vegetative",
    )

    assert event.status == "RESOLVED"
    assert event.resolved_at is not None
    assert event.after_state["phase"] == "AFTER"
    assert event.after_state["risk_level"] == "LOW"
    assert event.integrity_hash


def test_integrity_hash_changes_when_record_changes():
    event = FarmEvent(
        event_id="EVT-TEST",
        farm_id=1,
        zone_id="A1",
        status="CONFIRMED",
        started_at=datetime.utcnow(),
        detected_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        risk_level="HIGH",
        risk_score=75,
    )

    first = compute_integrity_hash(event)

    event.risk_score = 76

    second = compute_integrity_hash(event)

    assert first != second


def test_verify_integrity():
    event = FarmEvent(
        event_id="EVT-VERIFY",
        farm_id=1,
        zone_id="A1",
        status="CONFIRMED",
        started_at=datetime.utcnow(),
        detected_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        risk_level="HIGH",
        risk_score=75,
    )

    event.integrity_hash = compute_integrity_hash(event)

    valid, stored, computed = verify_integrity(event)

    assert valid is True
    assert stored == computed