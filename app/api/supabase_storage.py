from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.farm_event import FarmEvent
from app.services.farm_event_service import (
    rebuild_evidence_package,
)
from app.services.supabase_storage import (
    create_evidence_signed_url,
    upload_event_evidence,
)


router = APIRouter(
    prefix="/api/supabase",
    tags=["supabase-storage"],
)


@router.post("/storage/event/{event_id}")
def upload_event_storage(
    event_id: str,
    db: Session = Depends(get_db),
):

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

    if not event.evidence_package:
        rebuild_evidence_package(event)
        db.commit()
        db.refresh(event)

    result = upload_event_evidence(
        event_id=event.event_id,
        evidence_package=event.evidence_package or {},
    )

    if not result.get("uploaded"):
        raise HTTPException(
            status_code=503,
            detail=result,
        )

    return {
        "status": "STORAGE_SYNC_COMPLETE",
        "event_id": event.event_id,
        "bucket": result["bucket"],
        "path": result["path"],
    }


@router.get("/storage/event/{event_id}/url")
def get_event_storage_url(
    event_id: str,
):

    storage_path = (
        f"events/{event_id}/evidence.json"
    )

    result = create_evidence_signed_url(
        storage_path,
        expires_in=3600,
    )

    if not result.get("data"):
        raise HTTPException(
            status_code=503,
            detail=result,
        )

    return {
        "status": "SIGNED_URL_READY",
        "event_id": event_id,
        "bucket": result["bucket"],
        "path": result["path"],
        "expires_in": result["expires_in"],
        "url": result["data"],
    }