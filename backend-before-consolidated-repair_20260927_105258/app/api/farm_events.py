from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.farm_event import FarmEvent
from app.models.field_sensor import FieldSensorReading
from app.schemas.farm_event import EvidenceVerifyResponse
from app.schemas.simulator import (
    SimulatorConfig,
    SimulatorEvaluationRequest,
    SimulatorScenarioRequest,
    SimulatorStatusResponse,
    SimulatorStepRequest,
)
from app.services import field_simulator_service as simulator
from app.services.analysis_service import analyze_field_observation
from app.services.farm_event_service import (
    create_or_update_event,
    rebuild_evidence_package,
    serialize_event,
    verify_integrity,
)
from app.services.observation_service import get_spatial_context, get_temporal_history

router = APIRouter(prefix="/api", tags=["CRAI Farm Intelligence"])


def _status_payload() -> dict:
    state = simulator.get_state()
    return {
        "running": state.running,
        "device_id": state.device_id,
        "farm_id": state.farm_id,
        "zone_id": state.zone_id,
        "scenario": state.scenario,
        "step": state.step,
        "interval": state.interval,
        "seed": state.seed,
        "last_reading_id": state.last_reading_id,
        "last_timestamp": state.last_timestamp,
    }


@router.get("/simulator/status", response_model=SimulatorStatusResponse)
def simulator_status():
    return _status_payload()


@router.post("/simulator/start", response_model=SimulatorStatusResponse)
def simulator_start(payload: SimulatorConfig):
    simulator.configure(
        device_id=payload.device_id,
        farm_id=payload.farm_id,
        zone_id=payload.zone_id,
        scenario=payload.scenario,
        interval=payload.interval,
        seed=payload.seed,
        reset_step=True,
    )
    simulator.start()
    return _status_payload()


@router.post("/simulator/stop", response_model=SimulatorStatusResponse)
def simulator_stop():
    simulator.stop()
    return _status_payload()


@router.post("/simulator/scenario", response_model=SimulatorStatusResponse)
def simulator_scenario(payload: SimulatorScenarioRequest):
    simulator.configure(
        device_id=payload.device_id,
        farm_id=payload.farm_id,
        zone_id=payload.zone_id,
        scenario=payload.scenario,
        interval=payload.interval,
        seed=payload.seed,
        reset_step=payload.reset_step,
    )
    return _status_payload()


@router.post("/simulator/step")
def simulator_step(payload: SimulatorStepRequest, db: Session = Depends(get_db)):
    state = simulator.get_state()
    if payload.device_id:
        state.device_id = payload.device_id
    if payload.farm_id is not None:
        state.farm_id = payload.farm_id
    if payload.zone_id:
        state.zone_id = payload.zone_id.strip().upper()

    readings = []
    for _ in range(payload.steps):
        reading = simulator.persist_step(db, state=state)
        readings.append({
            "reading_id": reading.reading_id,
            "device_id": reading.device_id,
            "farm_id": reading.farm_id,
            "zone_id": reading.zone_id,
            "source": reading.source,
            "timestamp": reading.timestamp,
            "temperature": reading.temperature,
            "humidity": reading.humidity,
            "soil_moisture": reading.soil_moisture,
            "soil_temperature": reading.soil_temperature,
            "soil_ph": reading.soil_ph,
            "soil_ec": reading.soil_ec,
            "leaf_wetness": reading.leaf_wetness,
            "gateway_id": reading.gateway_id,
            "sequence_number": reading.sequence_number,
        })

    return {
        "status": "SIMULATION_STEP_COMPLETE",
        "source": "SIMULATED",
        "scenario": state.scenario,
        "count": len(readings),
        "readings": readings,
        "simulator": _status_payload(),
    }


@router.post("/simulator/evaluate")
def simulator_evaluate(payload: SimulatorEvaluationRequest, db: Session = Depends(get_db)):
    """Run the existing authoritative CRAI analysis using the latest simulated sensor.

    The visual prediction is an explicit input to the simulator endpoint; this endpoint
    never fabricates a visual model result. Production image analysis continues through
    POST /api/analysis/image.
    """
    query = db.query(FieldSensorReading).filter(
        FieldSensorReading.device_id == payload.device_id,
        FieldSensorReading.zone_id == payload.zone_id.strip().upper(),
        FieldSensorReading.source == "SIMULATED",
    )
    if payload.farm_id is not None:
        query = query.filter(FieldSensorReading.farm_id == payload.farm_id)
    sensor_row = query.order_by(FieldSensorReading.timestamp.desc()).first()

    if sensor_row is None:
        raise HTTPException(
            status_code=409,
            detail="No SIMULATED reading exists for this device/zone. Run /api/simulator/step first.",
        )

    sensor = {
        "available": True,
        "device_id": sensor_row.device_id,
        "reading_id": sensor_row.reading_id,
        "farm_id": sensor_row.farm_id,
        "zone_id": sensor_row.zone_id,
        "source": "SIMULATED",
        "soil_moisture": sensor_row.soil_moisture,
        "soil_temperature": sensor_row.soil_temperature,
        "soil_ph": sensor_row.soil_ph,
        "soil_ec": sensor_row.soil_ec,
        "leaf_wetness": sensor_row.leaf_wetness,
        "temperature": sensor_row.temperature,
        "humidity": sensor_row.humidity,
        "timestamp": sensor_row.timestamp.isoformat(),
    }

    history = get_temporal_history(
        
        zone_id=payload.zone_id,
        crop=payload.crop,
        farm_id=payload.farm_id,
    )
    spatial = get_spatial_context(
        
        zone_id=payload.zone_id,
        farm_id=payload.farm_id,
    )

    analysis = analyze_field_observation(
        prediction=payload.prediction,
        confidence=payload.confidence,
        crop=payload.crop,
        growth_stage=payload.growth_stage,
        temperature=sensor_row.temperature,
        humidity=sensor_row.humidity,
        thermal_anomaly=payload.thermal_anomaly,
        sensor=sensor,
        spatial_context=spatial,
        history=history,
        advisory_language=payload.advisory_language,
    )

    event = None
    if analysis.get("status") == "ANALYSIS_COMPLETE" and analysis.get("decision", {}).get("ready", True):
        event = create_or_update_event(
            db,
            analysis=analysis,
            farm_id=payload.farm_id,
            zone_id=payload.zone_id,
            device_id=payload.device_id,
            crop=payload.crop,
            crop_stage=payload.growth_stage,
        )

    return {
        "status": "SIMULATED_ANALYSIS_COMPLETE",
        "source": "SIMULATED",
        "scenario": simulator.get_state().scenario,
        "sensor": sensor,
        "analysis": analysis,
        "event": serialize_event(event) if event else None,
    }


@router.get("/farms/{farm_id}/state")
def get_farm_state(farm_id: int, db: Session = Depends(get_db)):
    latest_sensor = (
        db.query(FieldSensorReading)
        .filter(FieldSensorReading.farm_id == farm_id)
        .order_by(FieldSensorReading.timestamp.desc())
        .first()
    )
    latest_event = (
        db.query(FarmEvent)
        .filter(FarmEvent.farm_id == farm_id)
        .order_by(FarmEvent.updated_at.desc())
        .first()
    )
    zones = [
        row[0]
        for row in db.query(FieldSensorReading.zone_id)
        .filter(FieldSensorReading.farm_id == farm_id, FieldSensorReading.zone_id.isnot(None))
        .distinct()
        .all()
    ]
    return {
        "farm_id": farm_id,
        "zones": sorted(zones),
        "latest_sensor": _sensor_response(latest_sensor),
        "latest_event": serialize_event(latest_event) if latest_event else None,
    }


@router.get("/farms/{farm_id}/zones/{zone_id}/state")
def get_zone_state(farm_id: int, zone_id: str, db: Session = Depends(get_db)):
    zone = zone_id.strip().upper()
    sensor = (
        db.query(FieldSensorReading)
        .filter(FieldSensorReading.farm_id == farm_id, FieldSensorReading.zone_id == zone)
        .order_by(FieldSensorReading.timestamp.desc())
        .first()
    )
    event = (
        db.query(FarmEvent)
        .filter(FarmEvent.farm_id == farm_id, FarmEvent.zone_id == zone)
        .order_by(FarmEvent.updated_at.desc())
        .first()
    )
    return {
        "farm_id": farm_id,
        "zone_id": zone,
        "latest_sensor": _sensor_response(sensor),
        "latest_event": serialize_event(event) if event else None,
    }


@router.get("/events")
def list_events(
    farm_id: int | None = None,
    zone_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    query = db.query(FarmEvent)
    if farm_id is not None:
        query = query.filter(FarmEvent.farm_id == farm_id)
    if zone_id:
        query = query.filter(FarmEvent.zone_id == zone_id.strip().upper())
    if status:
        query = query.filter(FarmEvent.status == status.upper())
    events = query.order_by(FarmEvent.updated_at.desc()).limit(min(max(limit, 1), 200)).all()
    return {"count": len(events), "events": [serialize_event(item) for item in events]}


@router.get("/events/active")
def list_active_events(farm_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(FarmEvent).filter(FarmEvent.status.in_(["DETECTED", "CONFIRMED", "ACTIVE", "RECOVERING"]))
    if farm_id is not None:
        query = query.filter(FarmEvent.farm_id == farm_id)
    events = query.order_by(FarmEvent.updated_at.desc()).all()
    return {"count": len(events), "events": [serialize_event(item) for item in events]}


@router.get("/events/{event_id}")
def get_event(event_id: str, db: Session = Depends(get_db)):
    event = db.query(FarmEvent).filter(FarmEvent.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Farm event not found")
    return serialize_event(event)


@router.get("/events/{event_id}/timeline")
def get_event_timeline(event_id: str, db: Session = Depends(get_db)):
    event = db.query(FarmEvent).filter(FarmEvent.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Farm event not found")
    return {
        "event_id": event.event_id,
        "status": event.status,
        "before": event.before_state or {"status": "NOT_AVAILABLE"},
        "during": event.during_state or {"status": "NOT_AVAILABLE"},
        "after": event.after_state or {"status": "NOT_AVAILABLE"},
    }


@router.get("/events/{event_id}/evidence")
def get_event_evidence(event_id: str, db: Session = Depends(get_db)):
    event = db.query(FarmEvent).filter(FarmEvent.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Farm event not found")
    if not event.evidence_package:
        rebuild_evidence_package(event)
        db.commit()
        db.refresh(event)
    return {
        "event_id": event.event_id,
        "package": event.evidence_package,
        "integrity_hash": event.integrity_hash,
    }


@router.post("/evidence/verify", response_model=EvidenceVerifyResponse)
def verify_event_evidence(event_id: str, db: Session = Depends(get_db)):
    event = db.query(FarmEvent).filter(FarmEvent.event_id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Farm event not found")
    valid, stored, computed = verify_integrity(event)
    return {
        "event_id": event.event_id,
        "valid": valid,
        "stored_hash": stored or None,
        "computed_hash": computed,
        "reason": "Integrity hash matches the canonical event record." if valid else "Stored hash does not match the canonical event record.",
    }


def _sensor_response(reading: FieldSensorReading | None):
    if not reading:
        return None
    return {
        "reading_id": reading.reading_id,
        "device_id": reading.device_id,
        "farm_id": reading.farm_id,
        "zone_id": reading.zone_id,
        "source": reading.source,
        "timestamp": reading.timestamp,
        "temperature": reading.temperature,
        "humidity": reading.humidity,
        "soil_moisture": reading.soil_moisture,
        "soil_temperature": reading.soil_temperature,
        "soil_ph": reading.soil_ph,
        "soil_ec": reading.soil_ec,
        "leaf_wetness": reading.leaf_wetness,
        "latitude": reading.latitude,
        "longitude": reading.longitude,
        "altitude": reading.altitude,
        "battery": reading.battery,
        "signal_strength": reading.signal_strength,
        "gateway_id": reading.gateway_id,
        "sequence_number": reading.sequence_number,
    }
