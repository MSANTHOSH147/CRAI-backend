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



def summarize_visual_evidence(*args, **kwargs):
    records = _load_index()

    if args and isinstance(args[0], list):
        records = args[0]

    event_id = kwargs.get("event_id")
    farm_id = kwargs.get("farm_id")
    zone_id = kwargs.get("zone_id")

    if event_id:
        records = [r for r in records if r.get("event_id") == event_id]

    if farm_id is not None:
        records = [r for r in records if str(r.get("farm_id")) == str(farm_id)]

    if zone_id is not None:
        records = [r for r in records if str(r.get("zone_id")) == str(zone_id)]

    phases = {
        "BEFORE": {"count": 0},
        "DURING": {"count": 0},
        "AFTER": {"count": 0},
    }

    for record in records:
        phase = str(record.get("phase", "")).upper()
        if phase in phases:
            phases[phase]["count"] += 1

    return {
        "count": len(records),
        "records": records,
        "phases": phases,
        "by_phase": phases,
        "sources": sorted(set(str(r.get("source", "")) for r in records)),
        "quality": [r.get("quality") for r in records],
        "completeness": (
            "COMPLETE"
            if all(phases[p]["count"] > 0 for p in ("BEFORE", "DURING", "AFTER"))
            else "PARTIAL"
        ),
        "available": bool(records),
    }


def link_observation(image_id, observation_id):
    record = get_record(image_id)
    if not record:
        return None
    record["observation_id"] = observation_id
    return update_record(image_id, record)

def normalize_quality_result(quality):
    """
    Stable compatibility view for tests/UI.

    The production quality evaluator remains authoritative.
    This helper only returns the existing quality payload without
    inventing a new schema or changing its score/classification.
    """
    if quality is None:
        return {}
    if isinstance(quality, dict):
        return dict(quality)
    return {"value": quality}
