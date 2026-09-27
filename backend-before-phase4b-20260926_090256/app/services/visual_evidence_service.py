
"""
CRAI Visual Evidence Service
Phase 4

Multi-scale visual evidence:
    UAV   -> field/zone scale
    PHONE -> plant/ground scale

The service does NOT calculate CRAI risk.
It only manages visual evidence and metadata.

Risk remains owned by the deterministic CRAI fusion layer.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


BASE_DIR = Path(__file__).resolve().parents[2]
VISUAL_STORAGE = BASE_DIR / "data" / "visual_evidence"

VISUAL_STORAGE.mkdir(parents=True, exist_ok=True)


VALID_SOURCES = {
    "PHONE",
    "UAV",
}

VALID_PHASES = {
    "BEFORE",
    "DURING",
    "AFTER",
}

VALID_CAPTURE_MODES = {
    "ROUTINE",
    "TARGETED_INSPECTION",
    "EVENT_EVIDENCE",
    "FIELD_SCAN",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_image_id() -> str:
    return (
        f"IMG-{utc_now().strftime('%Y%m%d%H%M%S')}-"
        f"{uuid.uuid4().hex[:8].upper()}"
    )


def validate_source(source: str) -> str:
    source = str(source or "").upper().strip()

    if source not in VALID_SOURCES:
        raise ValueError(
            f"Invalid visual source '{source}'. "
            f"Expected one of {sorted(VALID_SOURCES)}."
        )

    return source


def validate_phase(phase: str) -> str:
    phase = str(phase or "").upper().strip()

    if phase not in VALID_PHASES:
        raise ValueError(
            f"Invalid evidence phase '{phase}'. "
            f"Expected one of {sorted(VALID_PHASES)}."
        )

    return phase


def validate_capture_mode(mode: str) -> str:
    mode = str(mode or "").upper().strip()

    if mode not in VALID_CAPTURE_MODES:
        raise ValueError(
            f"Invalid capture mode '{mode}'. "
            f"Expected one of {sorted(VALID_CAPTURE_MODES)}."
        )

    return mode


def calculate_file_hash(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def build_visual_metadata(
    *,
    image_id: str,
    farm_id: Optional[int],
    zone_id: Optional[str],
    event_id: Optional[str],
    source: str,
    phase: str,
    capture_mode: str,
    filename: str,
    stored_path: str,
    content_type: Optional[str],
    file_hash: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    altitude: Optional[float] = None,
    sequence: Optional[int] = None,
    parent_observation_id: Optional[str] = None,
    quality_score: Optional[float] = None,
    quality_status: Optional[str] = None,
    visual_confidence: Optional[float] = None,
) -> dict[str, Any]:

    return {
        "image_id": image_id,
        "farm_id": farm_id,
        "zone_id": zone_id,
        "event_id": event_id,

        "source": source,
        "scale": "FIELD" if source == "UAV" else "PLANT",

        "phase": phase,
        "capture_mode": capture_mode,

        "filename": filename,
        "stored_path": stored_path,
        "content_type": content_type,

        "timestamp": utc_now().isoformat(),

        "latitude": latitude,
        "longitude": longitude,
        "altitude": altitude,

        "sequence": sequence,
        "parent_observation_id": parent_observation_id,

        "quality_score": quality_score,
        "quality_status": quality_status,

        "visual_confidence": visual_confidence,

        "integrity": {
            "algorithm": "SHA-256",
            "hash": file_hash,
        },
    }


def save_visual_file(
    *,
    content: bytes,
    filename: str,
    metadata: dict[str, Any],
) -> tuple[Path, str]:

    safe_name = Path(filename).name

    image_id = metadata["image_id"]

    folder = (
        VISUAL_STORAGE
        / str(metadata.get("farm_id") or "unknown_farm")
        / str(metadata.get("zone_id") or "unknown_zone")
        / str(metadata["phase"]).lower()
    )

    folder.mkdir(parents=True, exist_ok=True)

    output = folder / f"{image_id}_{safe_name}"

    output.write_bytes(content)

    file_hash = calculate_file_hash(output)

    return output, file_hash


def summarize_visual_evidence(
    image_references: Optional[list[dict[str, Any]]],
) -> dict[str, Any]:

    images = image_references or []

    by_phase = {
        "BEFORE": [],
        "DURING": [],
        "AFTER": [],
    }

    by_source = {
        "PHONE": 0,
        "UAV": 0,
    }

    for image in images:

        phase = str(image.get("phase", "")).upper()

        source = str(image.get("source", "")).upper()

        if phase in by_phase:
            by_phase[phase].append(image)

        if source in by_source:
            by_source[source] += 1

    phases = {
        phase: {
            "count": len(items),
            "sources": sorted(
                {
                    str(item.get("source"))
                    for item in items
                    if item.get("source")
                }
            ),
            "images": items,
        }
        for phase, items in by_phase.items()
    }

    populated = sum(
        1
        for items in by_phase.values()
        if items
    )

    if populated == 3:
        completeness = "COMPLETE"
    elif populated > 0:
        completeness = "PARTIAL"
    else:
        completeness = "NONE"

    return {
        "image_count": len(images),
        "phone_count": by_source["PHONE"],
        "uav_count": by_source["UAV"],
        "completeness": completeness,
        "phases": phases,
    }


def build_image_reference(
    *,
    image_id: str,
    farm_id: Optional[int],
    zone_id: Optional[str],
    event_id: Optional[str],
    source: str,
    phase: str,
    capture_mode: str,
    filename: str,
    stored_path: str,
    content_type: Optional[str],
    file_hash: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    altitude: Optional[float] = None,
    sequence: Optional[int] = None,
    parent_observation_id: Optional[str] = None,
    quality_score: Optional[float] = None,
    quality_status: Optional[str] = None,
    visual_confidence: Optional[float] = None,
) -> dict[str, Any]:

    source = validate_source(source)
    phase = validate_phase(phase)
    capture_mode = validate_capture_mode(capture_mode)

    return build_visual_metadata(
        image_id=image_id,
        farm_id=farm_id,
        zone_id=zone_id,
        event_id=event_id,
        source=source,
        phase=phase,
        capture_mode=capture_mode,
        filename=filename,
        stored_path=stored_path,
        content_type=content_type,
        file_hash=file_hash,
        latitude=latitude,
        longitude=longitude,
        altitude=altitude,
        sequence=sequence,
        parent_observation_id=parent_observation_id,
        quality_score=quality_score,
        quality_status=quality_status,
        visual_confidence=visual_confidence,
    )


def serialize_visual_reference(reference: dict[str, Any]) -> dict[str, Any]:
    """
    Return safe JSON-compatible metadata.
    """

    return json.loads(
        json.dumps(reference, default=str)
    )
