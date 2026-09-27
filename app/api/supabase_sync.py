from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.farm_event import FarmEvent
from app.services.supabase_persistence import (
    persist_farm_event,
    persist_risk_snapshot,
)

router = APIRouter(
    prefix="/api/supabase",
    tags=["supabase"],
)


@router.post("/sync/event/{event_id}")
def sync_event(
    event_id: str,
    db: Session = Depends(get_db),
):
    # --------------------------------------------------------
    # 1. Get the authoritative CRAI event
    # --------------------------------------------------------

    event = (
        db.query(FarmEvent)
        .filter(FarmEvent.event_id == event_id)
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=404,
            detail=f"Farm event not found: {event_id}",
        )

    # --------------------------------------------------------
    # 2. Persist the complete event to Supabase
    # --------------------------------------------------------

    event_result = persist_farm_event(event)

    if not event_result.get("persisted"):
        raise HTTPException(
            status_code=503,
            detail=event_result,
        )

    # --------------------------------------------------------
    # 3. Store a risk-history snapshot
    # --------------------------------------------------------

    risk_result = persist_risk_snapshot(
        event=event,
        evidence_state={
            "source": "CRAI_EVENT_ENGINE",
            "event_status": event.status,
            "risk_level": event.risk_level,
            "risk_score": event.risk_score,
        },
    )

    if not risk_result.get("persisted"):
        raise HTTPException(
            status_code=503,
            detail=risk_result,
        )

    # --------------------------------------------------------
    # 4. Return synchronization result
    # --------------------------------------------------------

    return {
        "status": "SYNC_COMPLETE",
        "event_id": event.event_id,
        "event_status": event.status,
        "risk_level": event.risk_level,
        "risk_score": event.risk_score,
        "farm_event": event_result,
        "risk_snapshot": risk_result,
    }
@router.post("/sync/complete/{event_id}")
def complete_supabase_sync(
    event_id: str,
    db: Session = Depends(get_db),
):
    from app.services.supabase_storage import (
        upload_event_evidence,
    )

    event = (
        db.query(FarmEvent)
        .filter(
            FarmEvent.event_id == event_id
        )
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=404,
            detail=f"Farm event not found: {event_id}",
        )

    event_result = persist_farm_event(event)

    if not event_result.get("persisted"):
        raise HTTPException(
            status_code=503,
            detail=event_result,
        )

    risk_result = persist_risk_snapshot(
        event=event,
        evidence_state={
            "source": "CRAI_EVENT_ENGINE",
            "event_status": event.status,
            "risk_level": event.risk_level,
            "risk_score": event.risk_score,
        },
    )

    if not risk_result.get("persisted"):
        raise HTTPException(
            status_code=503,
            detail=risk_result,
        )

    if not event.evidence_package:
        rebuild_evidence_package(event)
        db.commit()
        db.refresh(event)

    storage_result = upload_event_evidence(
        event_id=event.event_id,
        evidence_package=event.evidence_package or {},
    )

    if not storage_result.get("uploaded"):
        raise HTTPException(
            status_code=503,
            detail=storage_result,
        )

    return {
        "status": "CRAI_SUPABASE_COMPLETE",
        "event_id": event.event_id,
        "event": event_result,
        "risk_history": risk_result,
        "evidence_storage": storage_result,
    }