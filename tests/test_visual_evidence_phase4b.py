from io import BytesIO
from pathlib import Path

from PIL import Image

from app.services.visual_evidence_service import (
    create_record,
    normalize_quality_result,
)


def reset_visual_test_storage():
    root = Path("data") / "visual_evidence"
    if root.exists():
        for p in root.rglob("*"):
            if p.is_file():
                p.unlink()
        for p in sorted(root.rglob("*"), reverse=True):
            if p.is_dir():
                p.rmdir()
    root.mkdir(parents=True, exist_ok=True)


def make_image_bytes(rgb):
    image = Image.new("RGB", (640, 480), rgb)
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def test_visual_evidence_create_and_hash():
    reset_visual_test_storage()

    data = make_image_bytes((120, 160, 120))

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
    assert record["integrity"]["sha256"]

    # Validate the actual production quality payload without
    # inventing a field name. It must be a non-empty structured
    # result produced by the existing evaluator.
    quality = normalize_quality_result(record.get("quality"))
    assert isinstance(quality, dict)
    assert quality


def test_visual_evidence_duplicate_detection():
    reset_visual_test_storage()

    data = make_image_bytes((80, 130, 190))

    first, duplicate1 = create_record(
        data,
        filename="duplicate-test.jpg",
        content_type="image/jpeg",
        farm_id="PHASE4B_DUP",
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

    second, duplicate2 = create_record(
        data,
        filename="duplicate-test-2.jpg",
        content_type="image/jpeg",
        farm_id="PHASE4B_DUP",
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
        sequence=2,
        parent_observation_id=None,
        flight_id=None,
        observation_id=None,
    )

    assert duplicate1 is False
    assert duplicate2 is True
    assert first["integrity"]["sha256"] == second["integrity"]["sha256"]
