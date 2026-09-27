"""Farm-event, timeline, provenance and evidence-package services for CRAI."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.farm_event import FarmEvent
from app.models.field_sensor import FieldSensorReading
from app.services.visual_evidence_service import summarize_visual_evidence


RISK_ORDER = {
    "LOW": 0,
    "MODERATE": 1,
    "HIGH": 2,
    "CRITICAL": 3,
}


def _iso(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) else value


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def normalize_risk_level(value: Any) -> Optional[str]:
    if value is None:
        return None
    level = str(value).strip().upper()
    return level if level in RISK_ORDER else None


def extract_authoritative_outputs(analysis: dict) -> tuple[Optional[str], Optional[float], dict, str]:
    risk = analysis.get("risk") if isinstance(analysis, dict) else None
    decision = analysis.get("decision") if isinstance(analysis, dict) else None
    risk = risk if isinstance(risk, dict) else {}
    decision = decision if isinstance(decision, dict) else {}

    risk_level = normalize_risk_level(risk.get("risk_level"))
    risk_score = risk.get("risk_score")
    try:
        risk_score = float(risk_score) if risk_score is not None else None
    except (TypeError, ValueError):
        risk_score = None

    if not decision.get("ready", True):
        action = "COLLECT_ADDITIONAL_EVIDENCE"
    else:
        action = action_for_authoritative_decision(decision, risk_level)

    return risk_level, risk_score, decision, action


def action_for_authoritative_decision(decision: dict, risk_level: Optional[str]) -> str:
    action = str(decision.get("action") or "").upper()
    if "COLLECT_ADDITIONAL_EVIDENCE" in action or "ADDITIONAL_EVIDENCE" in action:
        return "INVESTIGATE"
    if risk_level == "CRITICAL":
        return "IMMEDIATE_PROTECTIVE_ACTION_AND_ALERT"
    if risk_level == "HIGH":
        return "PROTECT_AND_ALERT"
    if risk_level == "MODERATE":
        return "INVESTIGATE"
    return "MONITOR"


def _sensor_snapshot(reading: Optional[FieldSensorReading]) -> dict:
    if not reading:
        return {"status": "NOT_AVAILABLE", "source": None}
    return {
        "status": "AVAILABLE",
        "reading_id": reading.reading_id,
        "device_id": reading.device_id,
        "farm_id": reading.farm_id,
        "zone_id": reading.zone_id,
        "source": reading.source,
        "timestamp": _iso(reading.timestamp),
        "soil_moisture": reading.soil_moisture,
        "soil_temperature": getattr(reading, "soil_temperature", None),
        "soil_ph": getattr(reading, "soil_ph", None),
        "soil_ec": getattr(reading, "soil_ec", None),
        "leaf_wetness": getattr(reading, "leaf_wetness", None),
        "temperature": reading.temperature,
        "humidity": reading.humidity,
        "latitude": getattr(reading, "latitude", None),
        "longitude": getattr(reading, "longitude", None),
        "altitude": getattr(reading, "altitude", None),
        "battery": getattr(reading, "battery", None),
        "gateway_id": getattr(reading, "gateway_id", None),
    }


def build_state_snapshot(
    *,
    analysis: dict,
    sensor: Optional[FieldSensorReading],
    phase: str,
    crop: Optional[str] = None,
    crop_stage: Optional[str] = None,
    image_reference: Optional[dict] = None,
) -> dict:
    risk_level, risk_score, decision, action = extract_authoritative_outputs(analysis)
    disease = analysis.get("disease") if isinstance(analysis, dict) else {}
    context = analysis.get("context") if isinstance(analysis, dict) else {}
    judge = analysis.get("judge_intelligence") if isinstance(analysis, dict) else {}

    snapshot = {
        "phase": phase,
        "timestamp": datetime.utcnow().isoformat(),
        "crop": crop or context.get("crop") if isinstance(context, dict) else crop,
        "crop_stage": crop_stage or context.get("growth_stage") if isinstance(context, dict) else crop_stage,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "decision": _jsonable(decision),
        "action": action,
        "disease": _jsonable(disease),
        "sensor": _sensor_snapshot(sensor),
        "image": _jsonable(image_reference),
        "evidence_sources": _evidence_sources(analysis, sensor, image_reference),
        "temporal": _jsonable(context.get("temporal")) if isinstance(context, dict) else None,
        "spatial": _jsonable(context.get("spatial")) if isinstance(context, dict) else None,
        "judge_provenance": _jsonable(judge.get("provenance")) if isinstance(judge, dict) else None,
    }
    return snapshot


def _evidence_sources(analysis: dict, sensor: Optional[FieldSensorReading], image_reference: Optional[dict]) -> list[str]:
    sources: list[str] = []
    if analysis.get("disease"):
        sources.append("VISUAL_AI")
    if sensor:
        sources.append("SENSOR_" + str(sensor.source).upper())
    context = analysis.get("context") or {}
    temporal = context.get("temporal") if isinstance(context, dict) else None
    spatial = context.get("spatial") if isinstance(context, dict) else None
    if isinstance(temporal, dict) and temporal.get("available"):
        sources.append("TEMPORAL")
    if isinstance(spatial, dict) and spatial.get("available"):
        sources.append("SPATIAL")
    if image_reference:
        sources.append("IMAGE")
    return sorted(set(sources))


def _canonical_event_record(event: FarmEvent) -> dict:
    return _jsonable({
        "event_id": event.event_id,
        "farm_id": event.farm_id,
        "zone_id": event.zone_id,
        "device_id": event.device_id,
        "status": event.status,
        "started_at": event.started_at,
        "detected_at": event.detected_at,
        "resolved_at": event.resolved_at,
        "crop": event.crop,
        "crop_stage": event.crop_stage,
        "before_state": event.before_state,
        "during_state": event.during_state,
        "after_state": event.after_state,
        "risk_level": event.risk_level,
        "risk_score": event.risk_score,
        "decision": event.decision,
        "action": event.action,
        "evidence_sources": event.evidence_sources,
        "image_references": event.image_references,
        "sensor_references": event.sensor_references,
        "temporal_context": event.temporal_context,
        "spatial_context": event.spatial_context,
    })


def compute_integrity_hash(event: FarmEvent) -> str:
    canonical = json.dumps(
        _canonical_event_record(event),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def rebuild_evidence_package(event: FarmEvent) -> dict:
    sources = sorted(set(event.evidence_sources or []))
    items = []
    for source in sources:
        items.append({"source": source})

    package = {
        "package_id": f"PKG-{event.event_id}",
        "event_id": event.event_id,
        "created_at": datetime.utcnow().isoformat(),
        "evidence_count": len(items),
        "evidence_sources": sources,
        "record": _canonical_event_record(event),
    }
    event.evidence_package = package
    event.integrity_hash = compute_integrity_hash(event)
    # ------------------------------------------------------------
    # PHASE 4: MULTI-SCALE VISUAL EVIDENCE
    # ------------------------------------------------------------
    visual_summary = summarize_visual_evidence(
        event.image_references or []
    )

    package["visual_evidence"] = visual_summary

    package["evidence_completeness"] = {
        "before": bool(
            visual_summary["phases"]["BEFORE"]["count"]
        ),
        "during": bool(
            visual_summary["phases"]["DURING"]["count"]
        ),
        "after": bool(
            visual_summary["phases"]["AFTER"]["count"]
        ),
        "status": visual_summary["completeness"],
    }

    return package


def verify_integrity(event: FarmEvent) -> tuple[bool, str, str]:
    computed = compute_integrity_hash(event)
    stored = event.integrity_hash or ""
    return stored == computed, stored, computed


def _find_active_event(db: Session, farm_id: Optional[int], zone_id: str) -> Optional[FarmEvent]:
    query = db.query(FarmEvent).filter(FarmEvent.zone_id == zone_id.upper())
    if farm_id is not None:
        query = query.filter(FarmEvent.farm_id == farm_id)
    return (
        query.filter(FarmEvent.status.in_(["DETECTED", "CONFIRMED", "ACTIVE", "RECOVERING"]))
        .order_by(FarmEvent.started_at.desc())
        .first()
    )


def _latest_sensor(db: Session, farm_id: Optional[int], zone_id: str) -> Optional[FieldSensorReading]:
    query = db.query(FieldSensorReading).filter(FieldSensorReading.zone_id == zone_id.upper())
    if farm_id is not None:
        query = query.filter(FieldSensorReading.farm_id == farm_id)
    return query.order_by(FieldSensorReading.timestamp.desc()).first()


def _latest_resolved_event(db: Session, farm_id: Optional[int], zone_id: str) -> Optional[FarmEvent]:
    query = db.query(FarmEvent).filter(
        FarmEvent.zone_id == zone_id.upper(),
        FarmEvent.status == "RESOLVED",
    )
    if farm_id is not None:
        query = query.filter(FarmEvent.farm_id == farm_id)
    return query.order_by(FarmEvent.resolved_at.desc()).first()


def create_or_update_event(
    db: Session,
    *,
    analysis: dict,
    farm_id: Optional[int],
    zone_id: str,
    device_id: Optional[str] = None,
    crop: Optional[str] = None,
    crop_stage: Optional[str] = None,
    image_reference: Optional[dict] = None,
) -> Optional[FarmEvent]:
    """Consume an authoritative completed CRAI analysis and update event state.

    No risk is calculated here. The event layer only interprets the risk and
    decision already produced by CRAI's deterministic analysis pipeline.
    """
    if not isinstance(analysis, dict):
        return None

    decision = analysis.get("decision") or {}
    if not isinstance(decision, dict) or not decision.get("ready", True):
        return None

    risk_level, risk_score, decision, action = extract_authoritative_outputs(analysis)
    if risk_level is None:
        return None

    zone = zone_id.strip().upper()
    sensor = _latest_sensor(db, farm_id, zone)
    now = datetime.utcnow()
    active = _find_active_event(db, farm_id, zone)

    # Lifecycle contract:
    # BEFORE -> DURING -> RECOVERY -> AFTER -> RESOLVED
    #
    # A LOW observation is only an AFTER observation once the event has
    # already entered RECOVERING.  This prevents a single transient LOW
    # reading from closing a previously active event immediately.
    if risk_level == "LOW":
        if not active:
            return None

        if active.status != "RECOVERING":
            recovery = build_state_snapshot(
                analysis=analysis,
                sensor=sensor,
                phase="RECOVERY",
                crop=crop,
                crop_stage=crop_stage,
                image_reference=image_reference,
            )
            active.status = "RECOVERING"
            active.during_state = recovery
            active.risk_level = risk_level
            active.risk_score = risk_score
            active.decision = _jsonable(decision)
            active.action = action
            active.updated_at = now
            active.evidence_sources = sorted(
                set((active.evidence_sources or []) + recovery["evidence_sources"])
            )
            if image_reference:
                active.image_references = (active.image_references or []) + [image_reference]
            if sensor:
                active.sensor_references = (active.sensor_references or []) + [_sensor_snapshot(sensor)]
            active.temporal_context = recovery.get("temporal")
            active.spatial_context = recovery.get("spatial")
            rebuild_evidence_package(active)
            db.commit()
            db.refresh(active)
            return active

        # A second LOW observation after RECOVERY is the confirmed AFTER
        # state.  Only here is the event resolved.
        active.after_state = build_state_snapshot(
            analysis=analysis,
            sensor=sensor,
            phase="AFTER",
            crop=crop,
            crop_stage=crop_stage,
            image_reference=image_reference,
        )
        active.status = "RESOLVED"
        active.resolved_at = now
        active.risk_level = risk_level
        active.risk_score = risk_score
        active.decision = _jsonable(decision)
        active.action = action
        active.updated_at = now
        active.evidence_sources = sorted(
            set((active.evidence_sources or []) + active.after_state["evidence_sources"])
        )
        if image_reference:
            active.image_references = (active.image_references or []) + [image_reference]
        if sensor:
            active.sensor_references = (active.sensor_references or []) + [_sensor_snapshot(sensor)]
        active.temporal_context = active.after_state.get("temporal")
        active.spatial_context = active.after_state.get("spatial")
        rebuild_evidence_package(active)
        db.commit()
        db.refresh(active)
        return active

    previous_level = normalize_risk_level(active.risk_level) if active else None
    is_recovery = bool(
        active
        and previous_level is not None
        and RISK_ORDER.get(risk_level, 0) < RISK_ORDER.get(previous_level, 0)
    )

    current = build_state_snapshot(
        analysis=analysis,
        sensor=sensor,
        phase="RECOVERY" if is_recovery else "DURING",
        crop=crop,
        crop_stage=crop_stage,
        image_reference=image_reference,
    )

    if active is None:
        previous_event = _latest_resolved_event(db, farm_id, zone)

        # ------------------------------------------------------------
        # BEFORE STATE
        # ------------------------------------------------------------
        # Prefer the previous resolved event's AFTER state.
        #
        # For the first event in a farm/zone there may be no previous
        # resolved event. In that case, use the most recent valid field
        # sensor reading as the baseline instead of returning an empty
        # BEFORE state.
        #
        # This keeps the event lifecycle meaningful:
        #
        # BEFORE -> DURING -> AFTER
        # ------------------------------------------------------------
        if previous_event and previous_event.after_state:
            before_state = previous_event.after_state

        elif sensor:
            before_state = _sensor_snapshot(sensor)
            before_state["phase"] = "BEFORE"
            before_state["timestamp"] = (
                sensor.timestamp.isoformat()
                if getattr(sensor, "timestamp", None)
                else datetime.utcnow().isoformat()
            )

        else:
            latest_sensor = _latest_sensor(db, farm_id, zone)

            if latest_sensor:
                before_state = _sensor_snapshot(latest_sensor)
                before_state["phase"] = "BEFORE"
                before_state["timestamp"] = (
                    latest_sensor.timestamp.isoformat()
                    if getattr(latest_sensor, "timestamp", None)
                    else datetime.utcnow().isoformat()
                )
            else:
                before_state = {"status": "NOT_AVAILABLE"}

        event = FarmEvent(
            event_id=f"EVT-{now.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8].upper()}",
            farm_id=farm_id,
            zone_id=zone,
            device_id=device_id or (sensor.device_id if sensor else None),
            status="CONFIRMED",
            started_at=now,
            detected_at=now,
            crop=crop,
            crop_stage=crop_stage,
            before_state=before_state,
            during_state=current,
            after_state={"status": "NOT_AVAILABLE"},
            risk_level=risk_level,
            risk_score=risk_score,
            decision=_jsonable(decision),
            action=action,
            evidence_sources=current["evidence_sources"],
            image_references=[image_reference] if image_reference else [],
            sensor_references=[_sensor_snapshot(sensor)] if sensor else [],
            temporal_context=current.get("temporal"),
            spatial_context=current.get("spatial"),
            created_at=now,
            updated_at=now,
        )
        db.add(event)
        db.flush()
        rebuild_evidence_package(event)
        db.commit()
        db.refresh(event)
        return event

    previous_level = normalize_risk_level(active.risk_level)
    if (
        previous_level
        and RISK_ORDER.get(risk_level, 0) < RISK_ORDER.get(previous_level, 0)
    ):
        active.status = "RECOVERING"
    else:
        # Recovery must be evidence-based. If the next observation stops
        # improving or becomes worse, the event is active again.
        active.status = "ACTIVE"

    active.during_state = current
    active.risk_level = risk_level
    active.risk_score = risk_score
    active.decision = _jsonable(decision)
    active.action = action
    active.updated_at = now
    active.evidence_sources = sorted(set((active.evidence_sources or []) + current["evidence_sources"]))
    if image_reference:
        active.image_references = (active.image_references or []) + [image_reference]
    if sensor:
        active.sensor_references = (active.sensor_references or []) + [_sensor_snapshot(sensor)]
    active.temporal_context = current.get("temporal")
    active.spatial_context = current.get("spatial")
    rebuild_evidence_package(active)
    db.commit()
    db.refresh(active)
    return active


def serialize_event(event: FarmEvent) -> dict:
    return {
        "event_id": event.event_id,
        "farm_id": event.farm_id,
        "zone_id": event.zone_id,
        "device_id": event.device_id,
        "status": event.status,
        "started_at": event.started_at,
        "detected_at": event.detected_at,
        "resolved_at": event.resolved_at,
        "crop": event.crop,
        "crop_stage": event.crop_stage,
        "risk_level": event.risk_level,
        "risk_score": event.risk_score,
        "decision": event.decision,
        "action": event.action,
        "before_state": event.before_state,
        "during_state": event.during_state,
        "after_state": event.after_state,
        "evidence_sources": event.evidence_sources or [],
        "image_references": event.image_references or [],
        "sensor_references": event.sensor_references or [],
        "temporal_context": event.temporal_context,
        "spatial_context": event.spatial_context,
        "evidence_package": event.evidence_package,
        "integrity_hash": event.integrity_hash,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
    }
