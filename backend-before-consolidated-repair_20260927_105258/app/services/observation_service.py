from datetime import datetime
from pathlib import Path
import json
import uuid

ROOT = Path("data/observations")
ROOT.mkdir(parents=True, exist_ok=True)
REGISTRY = ROOT / "registry.json"
QUEUE = ROOT / "queue.json"

SOURCES = {"PHONE", "UAV", "SENSOR", "SYSTEM"}
SCALES = {"PLANT", "FIELD", "ZONE", "FARM"}
STATUSES = {"PENDING", "UPLOADED", "PROCESSED", "ASSOCIATED", "FAILED"}
QUEUE_STATUSES = {"PENDING", "UPLOADED", "FAILED"}


def _now():
    return datetime.utcnow().isoformat()


def _read(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _registry():
    value = _read(REGISTRY, {})
    return value if isinstance(value, dict) else {}


def _queue():
    value = _read(QUEUE, {})
    return value if isinstance(value, dict) else {}


def create_observation(
    farm_id,
    zone_id,
    source,
    scale,
    capture_mode=None,
    latitude=None,
    longitude=None,
    timestamp=None,
    event_id=None,
    parent_observation_id=None,
    observation_id=None,
    status="PENDING",
):
    source = str(source).upper()
    scale = str(scale).upper()
    status = str(status).upper()
    if source not in SOURCES:
        raise ValueError(f"Unsupported observation source: {source}")
    if scale not in SCALES:
        raise ValueError(f"Unsupported observation scale: {scale}")
    if status not in STATUSES:
        raise ValueError(f"Unsupported observation status: {status}")

    registry = _registry()
    observation_id = observation_id or f"OBS-{datetime.utcnow():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8].upper()}"

    existing = registry.get(observation_id)
    if existing:
        return existing, True

    if parent_observation_id:
        if parent_observation_id not in registry:
            raise ValueError("parent_observation_id does not exist")
        parent = registry[parent_observation_id]
        if parent.get("farm_id") != farm_id or parent.get("zone_id") != zone_id:
            raise ValueError("Parent observation must belong to the same farm and zone")

    record = {
        "observation_id": observation_id,
        "farm_id": str(farm_id),
        "zone_id": str(zone_id),
        "timestamp": timestamp or _now(),
        "source": source,
        "scale": scale,
        "capture_mode": capture_mode,
        "latitude": latitude,
        "longitude": longitude,
        "event_id": event_id,
        "parent_observation_id": parent_observation_id,
        "status": status,
        "visual_evidence_ids": [],
        "sensor_evidence_ids": [],
        "created_at": _now(),
        "updated_at": _now(),
    }
    registry[observation_id] = record
    _write(REGISTRY, registry)
    return record, False


def get_observation(observation_id):
    return _registry().get(observation_id)


def list_observations(farm_id=None, zone_id=None, event_id=None, parent_observation_id=None):
    values = list(_registry().values())
    if farm_id is not None:
        values = [x for x in values if str(x.get("farm_id")) == str(farm_id)]
    if zone_id is not None:
        values = [x for x in values if str(x.get("zone_id")) == str(zone_id)]
    if event_id is not None:
        values = [x for x in values if x.get("event_id") == event_id]
    if parent_observation_id is not None:
        values = [x for x in values if x.get("parent_observation_id") == parent_observation_id]
    return sorted(values, key=lambda x: x.get("timestamp") or "")


def update_observation(observation_id, **changes):
    registry = _registry()
    record = registry.get(observation_id)
    if not record:
        return None
    for key, value in changes.items():
        if value is not None:
            record[key] = value
    record["updated_at"] = _now()
    registry[observation_id] = record
    _write(REGISTRY, registry)
    return record


def associate_event(observation_id, event_id):
    return update_observation(observation_id, event_id=event_id, status="ASSOCIATED")


def attach_visual_evidence(observation_id, image_id):
    registry = _registry()
    record = registry.get(observation_id)
    if not record:
        return None
    ids = record.setdefault("visual_evidence_ids", [])
    if image_id not in ids:
        ids.append(image_id)
    record["status"] = "PROCESSED"
    record["updated_at"] = _now()
    registry[observation_id] = record
    _write(REGISTRY, registry)
    return record


def attach_sensor_evidence(observation_id, sensor_id):
    registry = _registry()
    record = registry.get(observation_id)
    if not record:
        return None
    ids = record.setdefault("sensor_evidence_ids", [])
    if sensor_id not in ids:
        ids.append(sensor_id)
    record["updated_at"] = _now()
    registry[observation_id] = record
    _write(REGISTRY, registry)
    return record


def enqueue_observation(observation_id, file_reference=None):
    if not get_observation(observation_id):
        raise ValueError("observation_id does not exist")
    queue = _queue()
    for item in queue.values():
        if item.get("observation_id") == observation_id and item.get("status") == "PENDING":
            return item, True
    queue_id = f"Q-{uuid.uuid4().hex[:12].upper()}"
    item = {
        "queue_id": queue_id,
        "observation_id": observation_id,
        "file_reference": file_reference,
        "created_at": _now(),
        "attempt_count": 0,
        "last_error": None,
        "status": "PENDING",
    }
    queue[queue_id] = item
    _write(QUEUE, queue)
    update_observation(observation_id, status="PENDING")
    return item, False


def retry_observation(observation_id):
    queue = _queue()
    matches = [x for x in queue.values() if x.get("observation_id") == observation_id]
    if not matches:
        return None
    item = sorted(matches, key=lambda x: x.get("created_at") or "")[-1]
    item["attempt_count"] = int(item.get("attempt_count") or 0) + 1
    item["status"] = "UPLOADED"
    item["last_error"] = None
    queue[item["queue_id"]] = item
    _write(QUEUE, queue)
    update_observation(observation_id, status="UPLOADED")
    return item


def list_queue(observation_id=None):
    values = list(_queue().values())
    if observation_id:
        values = [x for x in values if x.get("observation_id") == observation_id]
    return values


def build_observation_graph(observation_id):
    root = get_observation(observation_id)
    if not root:
        return None
    children = list_observations(parent_observation_id=observation_id)
    return {"observation": root, "children": children}


def clear_test_data():
    if REGISTRY.exists():
        REGISTRY.unlink()
    if QUEUE.exists():
        QUEUE.unlink()

# ---------------------------------------------------------------------------
# Existing CRAI route compatibility helpers
# ---------------------------------------------------------------------------

def get_temporal_history(
    farm_id=None,
    zone_id=None,
    start_time=None,
    end_time=None,
    limit=50,
    **kwargs,
):
    """Return observation history for the requested farm/zone.

    This adapter intentionally reads the existing observation registry.
    It does not create or modify risk/fusion decisions.
    """
    records = list_observations(farm_id=farm_id, zone_id=zone_id)

    if start_time is not None:
        records = [
            r for r in records
            if str(r.get("timestamp", "")) >= str(start_time)
        ]
    if end_time is not None:
        records = [
            r for r in records
            if str(r.get("timestamp", "")) <= str(end_time)
        ]

    records = sorted(
        records,
        key=lambda r: str(r.get("timestamp", "")),
        reverse=True,
    )

    try:
        limit_value = max(1, int(limit))
    except (TypeError, ValueError):
        limit_value = 50

    records = records[:limit_value]

    return {
        "farm_id": farm_id,
        "zone_id": zone_id,
        "count": len(records),
        "observations": records,
    }


def get_spatial_context(
    farm_id=None,
    zone_id=None,
    latitude=None,
    longitude=None,
    **kwargs,
):
    """Return spatial context from the existing observation metadata."""
    records = list_observations(farm_id=farm_id, zone_id=zone_id)

    points = []
    for record in records:
        lat = record.get("latitude")
        lon = record.get("longitude")
        if lat is not None and lon is not None:
            points.append({
                "observation_id": record.get("observation_id"),
                "latitude": lat,
                "longitude": lon,
                "timestamp": record.get("timestamp"),
                "zone_id": record.get("zone_id"),
            })

    return {
        "farm_id": farm_id,
        "zone_id": zone_id,
        "latitude": latitude,
        "longitude": longitude,
        "count": len(points),
        "points": points,
    }


def resolve_farm_id_from_sensor(sensor_data=None, **kwargs):
    """Resolve farm identity from an incoming sensor payload.

    Priority:
    1. Explicit farm_id.
    2. Existing observation registry matched by device_id.
    3. None when unresolved.
    """
    payload = sensor_data if isinstance(sensor_data, dict) else {}

    explicit = payload.get("farm_id")
    if explicit is not None:
        return explicit

    device_id = (
        payload.get("device_id")
        or payload.get("deviceId")
        or payload.get("gateway_id")
        or payload.get("gatewayId")
    )

    if device_id is not None:
        records = list_observations()
        for record in reversed(records):
            if (
                record.get("device_id") == device_id
                or record.get("deviceId") == device_id
                or record.get("gateway_id") == device_id
                or record.get("gatewayId") == device_id
            ):
                return record.get("farm_id")

    return None


def save_field_observation(observation=None, **kwargs):
    """Compatibility adapter for legacy field-observation callers.

    It maps common legacy payload names into the Phase 5 observation
    registry without changing deterministic risk logic.
    """
    payload = {}
    if isinstance(observation, dict):
        payload.update(observation)
    payload.update({k: v for k, v in kwargs.items() if v is not None})

    farm_id = payload.get("farm_id")
    zone_id = payload.get("zone_id")

    if farm_id is None:
        farm_id = resolve_farm_id_from_sensor(payload)

    source = (
        payload.get("source")
        or payload.get("capture_source")
        or payload.get("observation_source")
        or "SENSOR"
    )

    scale = payload.get("scale") or "ZONE"
    phase = payload.get("phase") or "DURING"
    capture_mode = payload.get("capture_mode") or "ROUTINE"

    return create_observation(
        farm_id=farm_id,
        zone_id=zone_id,
        source=source,
        scale=scale,
        phase=phase,
        capture_mode=capture_mode,
        timestamp=payload.get("timestamp"),
        latitude=payload.get("latitude"),
        longitude=payload.get("longitude"),
        altitude=payload.get("altitude"),
        parent_observation_id=payload.get("parent_observation_id"),
        event_id=payload.get("event_id"),
        metadata=payload,
    )
