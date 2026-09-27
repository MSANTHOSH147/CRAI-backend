from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.schemas.visual_evidence import VisualEvidenceAssociateRequest
from app.services.visual_evidence_service import (
    ALLOWED_TYPES,
    associate_record,
    create_record,
    evaluate_quality,
    get_record,
    list_records,
    record_file_path,
    summarize_records,
    verify_record,
)


router = APIRouter(
    prefix="/api/visual-evidence",
    tags=["Visual Evidence"],
)


@router.post("")
async def upload_visual_evidence(
    file: UploadFile = File(...),
    farm_id: str = Form(...),
    zone_id: str = Form(...),
    event_id: Optional[str] = Form(None),
    source: str = Form("PHONE"),
    scale: str = Form("PLANT"),
    phase: str = Form("BEFORE"),
    capture_mode: str = Form("ROUTINE"),
    timestamp: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    altitude: Optional[float] = Form(None),
    sequence: Optional[int] = Form(None),
    parent_observation_id: Optional[str] = Form(None),
    flight_id: Optional[str] = Form(None),
    observation_id: Optional[str] = Form(None),
):
    source = source.upper()
    scale = scale.upper()
    phase = phase.upper()
    capture_mode = capture_mode.upper()

    if source not in {"PHONE", "UAV"}:
        raise HTTPException(400, "source must be PHONE or UAV")

    if scale not in {"PLANT", "FIELD"}:
        raise HTTPException(400, "scale must be PLANT or FIELD")

    if phase not in {"BEFORE", "DURING", "AFTER"}:
        raise HTTPException(400, "phase must be BEFORE, DURING or AFTER")

    if capture_mode not in {
        "ROUTINE",
        "TARGETED_INSPECTION",
        "EVENT_EVIDENCE",
        "FIELD_SCAN",
    }:
        raise HTTPException(400, "Unsupported capture_mode")

    if source == "UAV":
        if scale != "FIELD":
            raise HTTPException(400, "UAV evidence must use FIELD scale")
        if capture_mode != "FIELD_SCAN":
            raise HTTPException(400, "UAV evidence must use FIELD_SCAN mode")

    if source == "PHONE" and scale != "PLANT":
        raise HTTPException(400, "PHONE evidence must use PLANT scale")

    content_type = (file.content_type or "").lower()

    if content_type not in ALLOWED_TYPES:
        raise HTTPException(
            415,
            "Unsupported image type. Use JPEG, PNG or WEBP.",
        )

    data = await file.read()

    try:
        record, duplicate = create_record(
            data,
            filename=file.filename or "upload",
            content_type=content_type,
            farm_id=farm_id,
            zone_id=zone_id,
            event_id=event_id,
            source=source,
            scale=scale,
            phase=phase,
            capture_mode=capture_mode,
            timestamp=timestamp,
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            sequence=sequence,
            parent_observation_id=parent_observation_id,
            flight_id=flight_id,
            observation_id=observation_id,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(500, f"Visual evidence storage failed: {exc}")

    return {
        "ok": True,
        "duplicate": duplicate,
        "image": record,
        "recommended_action": (
            "CONTINUE_TO_VISUAL_AI"
            if record.get("quality_status") == "GOOD"
            else "REQUEST_BETTER_IMAGE"
        ),
    }


@router.get("/event/{event_id}")
def event_visual_evidence(event_id: str):
    records = list_records(event_id=event_id)

    return {
        "event_id": event_id,
        "records": records,
        "summary": summarize_records(records),
    }


@router.get("/farm/{farm_id}")
def farm_visual_evidence(farm_id: str):
    records = list_records(farm_id=farm_id)

    return {
        "farm_id": farm_id,
        "records": records,
        "summary": summarize_records(records),
    }


@router.get("/zone/{zone_id}")
def zone_visual_evidence(zone_id: str):
    records = list_records(zone_id=zone_id)

    return {
        "zone_id": zone_id,
        "records": records,
        "summary": summarize_records(records),
    }


@router.get("/{image_id}/file")
def visual_file(image_id: str):
    try:
        path = record_file_path(image_id)
    except KeyError:
        raise HTTPException(404, "Image not found")
    except FileNotFoundError:
        raise HTTPException(404, "Stored image missing")

    return FileResponse(path)


@router.get("/{image_id}")
def get_visual_evidence(image_id: str):
    record = get_record(image_id)

    if not record:
        raise HTTPException(404, "Image not found")

    return {"image": record}


@router.post("/{image_id}/verify")
def verify_visual_evidence(image_id: str):
    try:
        return verify_record(image_id)
    except KeyError:
        raise HTTPException(404, "Image not found")


@router.post("/{image_id}/quality")
def quality_visual_evidence(image_id: str):
    try:
        return evaluate_quality(image_id)
    except KeyError:
        raise HTTPException(404, "Image not found")
    except FileNotFoundError:
        raise HTTPException(404, "Stored image missing")


@router.post("/{image_id}/associate")
def associate_visual_evidence(
    image_id: str,
    request: VisualEvidenceAssociateRequest,
):
    try:
        record = associate_record(
            image_id,
            event_id=request.event_id,
            phase=request.phase.upper() if request.phase else None,
            parent_observation_id=request.parent_observation_id,
        )
    except KeyError:
        raise HTTPException(404, "Image not found")

    return {
        "ok": True,
        "image": record,
    }
