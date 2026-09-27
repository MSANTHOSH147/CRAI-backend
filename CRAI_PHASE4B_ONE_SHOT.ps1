$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "======================================================================"
Write-Host "          CRAI PHASE 4B - ONE SHOT INSTALLER"
Write-Host "     PRODUCTION VISUAL EVIDENCE INGESTION + INTEGRITY"
Write-Host "======================================================================"
Write-Host ""

$Backend = (Get-Location).Path
$App = Join-Path $Backend "app"
$Services = Join-Path $App "services"
$Schemas = Join-Path $App "schemas"
$Api = Join-Path $App "api"
$Data = Join-Path $Backend "data\visual_evidence"

if (!(Test-Path $Services)) { throw "app\services not found. Run this from the CRAI backend directory." }
New-Item -ItemType Directory -Force $Schemas | Out-Null
New-Item -ItemType Directory -Force $Api | Out-Null
New-Item -ItemType Directory -Force $Data | Out-Null

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backup = Join-Path $Backend "backend-before-phase4b-$stamp"
New-Item -ItemType Directory -Force $backup | Out-Null

foreach ($p in @(
    "app\services\visual_evidence_service.py",
    "app\schemas\visual_evidence.py",
    "app\api\visual_evidence.py",
    "app\main.py"
)) {
    $src = Join-Path $Backend $p
    if (Test-Path $src) {
        $dst = Join-Path $backup $p
        New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
        Copy-Item $src $dst -Force
    }
}

Write-Host "[1/6] Backup created: $backup"

$service = @'
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageStat

try:
    import cv2
except Exception:
    cv2 = None


BACKEND_ROOT = Path(__file__).resolve().parents[2]
VISUAL_ROOT = BACKEND_ROOT / "data" / "visual_evidence"
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MIN_WIDTH = 320
MIN_HEIGHT = 240
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

VISUAL_ROOT.mkdir(parents=True, exist_ok=True)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_token(value: Any, default: str = "unknown") -> str:
    raw = str(value if value is not None else default)
    cleaned = "".join(c if c.isalnum() or c in "-_" else "_" for c in raw)
    return cleaned[:80] or default


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _index_path() -> Path:
    return VISUAL_ROOT / "registry.json"


def _load_index() -> list[dict[str, Any]]:
    p = _index_path()
    if not p.exists():
        return []
    try:
        value = json.loads(p.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except Exception:
        return []


def _save_index(items: list[dict[str, Any]]) -> None:
    p = _index_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(items, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(tmp, p)


def get_record(image_id: str) -> Optional[dict[str, Any]]:
    for item in _load_index():
        if item.get("image_id") == image_id:
            return item
    return None


def find_by_hash(content_hash: str) -> Optional[dict[str, Any]]:
    for item in _load_index():
        if item.get("integrity", {}).get("sha256") == content_hash:
            return item
    return None


def _record_path(record: dict[str, Any]) -> Path:
    return (
        VISUAL_ROOT
        / safe_token(record["farm_id"], "farm")
        / safe_token(record["zone_id"], "zone")
        / safe_token(record["phase"], "routine").lower()
        / record["stored_filename"]
    )


def _quality_from_bytes(data: bytes) -> dict[str, Any]:
    try:
        from io import BytesIO

        img = Image.open(BytesIO(data))
        img.verify()

        img = Image.open(BytesIO(data)).convert("RGB")
        width, height = img.size
        stat = ImageStat.Stat(img)
        brightness = sum(stat.mean) / 3.0

        score = 100.0
        reasons: list[str] = []

        if width < MIN_WIDTH or height < MIN_HEIGHT:
            score -= 35
            reasons.append("dimensions_below_minimum")

        if brightness < 35:
            score -= 35
            reasons.append("too_dark")
        elif brightness > 225:
            score -= 30
            reasons.append("too_bright")

        blur_variance = None

        if cv2 is not None:
            import numpy as np

            arr = np.asarray(img)
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
            blur_variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())

            if blur_variance < 35:
                score -= 35
                reasons.append("possible_blur")

        score = max(0.0, min(100.0, score))

        if score >= 70:
            status = "GOOD"
        elif score < 45:
            status = "RETAKE"
        else:
            status = "UNCERTAIN"

        return {
            "quality_score": round(score, 2),
            "quality_status": status,
            "width": width,
            "height": height,
            "mean_brightness": round(brightness, 2),
            "blur_variance": (
                round(blur_variance, 2)
                if blur_variance is not None
                else None
            ),
            "reasons": reasons,
        }

    except Exception as exc:
        return {
            "quality_score": 0.0,
            "quality_status": "RETAKE",
            "width": 0,
            "height": 0,
            "mean_brightness": None,
            "blur_variance": None,
            "reasons": ["invalid_image", str(exc)[:160]],
        }


def create_record(
    data: bytes,
    *,
    filename: str,
    content_type: str,
    farm_id: str,
    zone_id: str,
    event_id: Optional[str],
    source: str,
    scale: str,
    phase: str,
    capture_mode: str,
    timestamp: Optional[str],
    latitude: Optional[float],
    longitude: Optional[float],
    altitude: Optional[float],
    sequence: Optional[int],
    parent_observation_id: Optional[str],
    flight_id: Optional[str],
    observation_id: Optional[str],
) -> tuple[dict[str, Any], bool]:

    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Image exceeds 10 MB limit.")

    if content_type not in ALLOWED_TYPES:
        raise ValueError(f"Unsupported content type: {content_type}")

    suffix = Path(filename or "").suffix.lower()

    if suffix and suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported image extension.")

    # Validate actual image bytes, not just extension/content-type.
    quality = _quality_from_bytes(data)

    content_hash = sha256_bytes(data)

    existing = find_by_hash(content_hash)
    if existing:
        return existing, True

    image_id = "IMG-" + uuid.uuid4().hex[:16].upper()

    ext = suffix if suffix in ALLOWED_EXTENSIONS else ".jpg"

    phase_dir = safe_token(phase, "routine").lower()
    farm_dir = safe_token(farm_id, "farm")
    zone_dir = safe_token(zone_id, "zone")

    target_dir = VISUAL_ROOT / farm_dir / zone_dir / phase_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{image_id}{ext}"
    target = target_dir / stored_filename
    target.write_bytes(data)

    record = {
        "image_id": image_id,
        "farm_id": farm_id,
        "zone_id": zone_id,
        "event_id": event_id,
        "source": source,
        "scale": scale,
        "phase": phase,
        "capture_mode": capture_mode,
        "timestamp": timestamp or iso_now(),
        "latitude": latitude,
        "longitude": longitude,
        "altitude": altitude,
        "sequence": sequence,
        "parent_observation_id": parent_observation_id,
        "flight_id": flight_id,
        "observation_id": observation_id or image_id,
        "filename": filename,
        "stored_filename": stored_filename,
        "mime_type": content_type,
        "size_bytes": len(data),
        "quality_score": quality["quality_score"],
        "quality_status": quality["quality_status"],
        "quality": quality,
        "visual_confidence": None,
        "integrity": {
            "algorithm": "SHA-256",
            "sha256": content_hash,
        },
        "created_at": iso_now(),
        "api_file_url": f"/api/visual-evidence/{image_id}/file",
    }

    items = _load_index()
    items.append(record)
    _save_index(items)

    return record, False


def update_record(image_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    items = _load_index()

    for i, item in enumerate(items):
        if item.get("image_id") == image_id:
            item.update(updates)
            items[i] = item
            _save_index(items)
            return item

    raise KeyError(image_id)


def list_records(
    *,
    event_id: Optional[str] = None,
    farm_id: Optional[str] = None,
    zone_id: Optional[str] = None,
) -> list[dict[str, Any]]:

    items = _load_index()

    if event_id is not None:
        items = [x for x in items if x.get("event_id") == event_id]

    if farm_id is not None:
        items = [
            x for x in items
            if str(x.get("farm_id")) == str(farm_id)
        ]

    if zone_id is not None:
        items = [
            x for x in items
            if str(x.get("zone_id")) == str(zone_id)
        ]

    return sorted(items, key=lambda x: x.get("timestamp", ""))


def verify_record(image_id: str) -> dict[str, Any]:
    record = get_record(image_id)

    if not record:
        raise KeyError(image_id)

    path = _record_path(record)

    if not path.exists():
        return {
            "image_id": image_id,
            "valid": False,
            "reason": "stored_file_missing",
        }

    actual = sha256_bytes(path.read_bytes())
    expected = record.get("integrity", {}).get("sha256")

    return {
        "image_id": image_id,
        "valid": actual == expected,
        "expected_sha256": expected,
        "actual_sha256": actual,
        "algorithm": "SHA-256",
    }


def evaluate_quality(image_id: str) -> dict[str, Any]:
    record = get_record(image_id)

    if not record:
        raise KeyError(image_id)

    path = _record_path(record)

    if not path.exists():
        raise FileNotFoundError(image_id)

    quality = _quality_from_bytes(path.read_bytes())

    updated = update_record(
        image_id,
        {
            "quality_score": quality["quality_score"],
            "quality_status": quality["quality_status"],
            "quality": quality,
        },
    )

    return {
        "image_id": image_id,
        "quality_score": updated["quality_score"],
        "quality_status": updated["quality_status"],
        "quality": quality,
        "recommended_action": (
            "CONTINUE_TO_VISUAL_AI"
            if quality["quality_status"] == "GOOD"
            else "REQUEST_BETTER_IMAGE"
        ),
    }


def associate_record(
    image_id: str,
    *,
    event_id: Optional[str] = None,
    phase: Optional[str] = None,
    parent_observation_id: Optional[str] = None,
) -> dict[str, Any]:

    updates: dict[str, Any] = {}

    if event_id is not None:
        updates["event_id"] = event_id

    if phase is not None:
        updates["phase"] = phase

    if parent_observation_id is not None:
        updates["parent_observation_id"] = parent_observation_id

    return update_record(image_id, updates)


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    phases = {
        "BEFORE": [],
        "DURING": [],
        "AFTER": [],
    }

    for item in records:
        phase = item.get("phase")
        if phase in phases:
            phases[phase].append(item)

    present = sum(bool(phases[p]) for p in phases)

    if present == 3:
        completeness = "COMPLETE"
    elif present > 0:
        completeness = "PARTIAL"
    else:
        completeness = "NONE"

    return {
        "count": len(records),
        "by_phase": {
            p: [x["image_id"] for x in values]
            for p, values in phases.items()
        },
        "sources": sorted(
            set(x.get("source") for x in records if x.get("source"))
        ),
        "quality": {
            "good": sum(
                x.get("quality_status") == "GOOD"
                for x in records
            ),
            "retake": sum(
                x.get("quality_status") == "RETAKE"
                for x in records
            ),
            "uncertain": sum(
                x.get("quality_status") == "UNCERTAIN"
                for x in records
            ),
        },
        "completeness": completeness,
    }


def record_file_path(image_id: str) -> Path:
    record = get_record(image_id)

    if not record:
        raise KeyError(image_id)

    path = _record_path(record)

    if not path.exists():
        raise FileNotFoundError(image_id)

    return path
'@

Set-Content -Path (Join-Path $Services "visual_evidence_service.py") -Value $service -Encoding UTF8

$schema = @'
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class VisualEvidenceAssociateRequest(BaseModel):
    event_id: Optional[str] = None
    phase: Optional[str] = None
    parent_observation_id: Optional[str] = None
'@

Set-Content -Path (Join-Path $Schemas "visual_evidence.py") -Value $schema -Encoding UTF8

$router = @'
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
'@

Set-Content -Path (Join-Path $Api "visual_evidence.py") -Value $router -Encoding UTF8

Write-Host "[2/6] Phase 4B visual evidence modules written."

$mainPath = Join-Path $App "main.py"
$main = Get-Content $mainPath -Raw

if ($main -notmatch "app\.api\.visual_evidence") {
    $main = "from app.api.visual_evidence import router as visual_evidence_router`r`n" + $main
}

if ($main -notmatch "include_router\(visual_evidence_router\)") {
    $main = $main.TrimEnd() + "`r`n`r`napp.include_router(visual_evidence_router)`r`n"
}

Set-Content $mainPath $main -Encoding UTF8

Write-Host "[3/6] Router registration checked."

$testDir = Join-Path $Backend "tests"
New-Item -ItemType Directory -Force $testDir | Out-Null

$test = @'
from io import BytesIO

from PIL import Image

from app.services.visual_evidence_service import (
    create_record,
    summarize_records,
)


def make_image_bytes(color=(80, 140, 80)):
    image = Image.new("RGB", (640, 480), color)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


def test_visual_evidence_create_and_hash():
    data = make_image_bytes()

    record, duplicate = create_record(
        data,
        filename="phase4b-test.jpg",
        content_type="image/jpeg",
        farm_id="PHASE4B_TEST",
        zone_id="A1",
        event_id=None,
        source="PHONE",
        scale="PLANT",
        phase="BEFORE",
        capture_mode="ROUTINE",
        timestamp=None,
        latitude=13.1,
        longitude=80.2,
        altitude=None,
        sequence=1,
        parent_observation_id=None,
        flight_id=None,
        observation_id=None,
    )

    assert duplicate is False
    assert record["integrity"]["algorithm"] == "SHA-256"
    assert len(record["integrity"]["sha256"]) == 64
    assert record["source"] == "PHONE"
    assert record["scale"] == "PLANT"


def test_visual_evidence_summary_partial():
    records = [
        {
            "image_id": "IMG-BEFORE",
            "phase": "BEFORE",
            "source": "PHONE",
            "quality_status": "GOOD",
        },
        {
            "image_id": "IMG-DURING",
            "phase": "DURING",
            "source": "UAV",
            "quality_status": "GOOD",
        },
    ]

    summary = summarize_records(records)

    assert summary["completeness"] == "PARTIAL"
    assert set(summary["sources"]) == {"PHONE", "UAV"}
'@

Set-Content -Path (Join-Path $testDir "test_visual_evidence_phase4b.py") -Value $test -Encoding UTF8

Write-Host "[4/6] Phase 4B tests written."

Write-Host "[5/6] Running Python syntax validation..."

$pyFiles = @(
    (Join-Path $Services "visual_evidence_service.py"),
    (Join-Path $Schemas "visual_evidence.py"),
    (Join-Path $Api "visual_evidence.py"),
    $mainPath
)

foreach ($file in $pyFiles) {
    python -m py_compile $file
}

Write-Host "Python syntax: PASS"

Write-Host "[6/6] Running test suite..."
python -m pytest -q

Write-Host ""
Write-Host "======================================================================"
Write-Host "                  PHASE 4B INSTALLATION COMPLETE"
Write-Host "======================================================================"
Write-Host ""
Write-Host "Backup:"
Write-Host "  $backup"
Write-Host ""
Write-Host "Visual storage:"
Write-Host "  $Data"
Write-Host ""
Write-Host "APIs:"
Write-Host "  POST /api/visual-evidence"
Write-Host "  GET  /api/visual-evidence/{image_id}"
Write-Host "  GET  /api/visual-evidence/event/{event_id}"
Write-Host "  GET  /api/visual-evidence/farm/{farm_id}"
Write-Host "  GET  /api/visual-evidence/zone/{zone_id}"
Write-Host "  POST /api/visual-evidence/{image_id}/verify"
Write-Host "  POST /api/visual-evidence/{image_id}/associate"
Write-Host "  POST /api/visual-evidence/{image_id}/quality"
Write-Host ""
Write-Host "IMPORTANT: restart FastAPI before API smoke testing."
Write-Host ""
Write-Host "  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
Write-Host ""
Write-Host "======================================================================"
