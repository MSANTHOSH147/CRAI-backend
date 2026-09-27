"""
CRAI -> Supabase persistence adapter.

Supabase stores CRAI outputs.
It does NOT calculate risk or make decisions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from app.services.supabase_client import get_supabase


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            str(key): _jsonable(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]

    return value


def _event_value(
    event: Any,
    name: str,
    default: Any = None,
) -> Any:
    if isinstance(event, dict):
        return event.get(name, default)

    return getattr(event, name, default)


def _json_field(
    event: Any,
    name: str,
    default: Any,
) -> Any:
    value = _event_value(event, name, default)

    if value is None:
        return default

    return _jsonable(value)


def serialize_farm_event(event: Any) -> dict:
    return {
        "event_id": _event_value(event, "event_id"),
        "farm_id": _event_value(event, "farm_id"),
        "zone_id": _event_value(event, "zone_id"),
        "device_id": _event_value(event, "device_id"),

        "status": _event_value(
            event,
            "status",
            "UNKNOWN",
        ),

        "started_at": _json_field(
            event,
            "started_at",
            None,
        ),

        "detected_at": _json_field(
            event,
            "detected_at",
            None,
        ),

        "resolved_at": _json_field(
            event,
            "resolved_at",
            None,
        ),

        "crop": _event_value(event, "crop"),
        "crop_stage": _event_value(event, "crop_stage"),

        "risk_level": _event_value(
            event,
            "risk_level",
        ),

        "risk_score": _event_value(
            event,
            "risk_score",
        ),

        "decision": _json_field(
            event,
            "decision",
            {},
        ),

        "action": _event_value(
            event,
            "action",
        ),

        "before_state": _json_field(
            event,
            "before_state",
            {},
        ),

        "during_state": _json_field(
            event,
            "during_state",
            {},
        ),

        "after_state": _json_field(
            event,
            "after_state",
            {},
        ),

        "evidence_sources": _json_field(
            event,
            "evidence_sources",
            [],
        ),

        "image_references": _json_field(
            event,
            "image_references",
            [],
        ),

        "sensor_references": _json_field(
            event,
            "sensor_references",
            [],
        ),

        "temporal_context": _json_field(
            event,
            "temporal_context",
            {},
        ),

        "spatial_context": _json_field(
            event,
            "spatial_context",
            {},
        ),

        "evidence_package": _json_field(
            event,
            "evidence_package",
            {},
        ),

        "integrity_hash": _event_value(
            event,
            "integrity_hash",
        ),

        "created_at": _json_field(
            event,
            "created_at",
            None,
        ),

        "updated_at": _json_field(
            event,
            "updated_at",
            None,
        ),
    }


def persist_farm_event(event: Any) -> dict:
    client = get_supabase()

    if client is None:
        return {
            "status": "SUPABASE_DISABLED",
            "persisted": False,
        }

    payload = serialize_farm_event(event)

    response = (
        client
        .table("farm_events")
        .upsert(
            payload,
            on_conflict="event_id",
        )
        .execute()
    )

    return {
        "status": "SUPABASE_PERSISTED",
        "persisted": True,
        "event_id": payload["event_id"],
        "data": response.data,
    }


def persist_risk_snapshot(
    *,
    event: Any,
    evidence_state: Optional[dict] = None,
) -> dict:

    client = get_supabase()

    if client is None:
        return {
            "status": "SUPABASE_DISABLED",
            "persisted": False,
        }

    payload = {
        "event_id": _event_value(
            event,
            "event_id",
        ),

        "farm_id": _event_value(
            event,
            "farm_id",
        ),

        "zone_id": _event_value(
            event,
            "zone_id",
        ),

        "device_id": _event_value(
            event,
            "device_id",
        ),

        "timestamp": datetime.utcnow().isoformat(),

        "risk_level": _event_value(
            event,
            "risk_level",
        ),

        "risk_score": _event_value(
            event,
            "risk_score",
        ),

        "action": _event_value(
            event,
            "action",
        ),

        "event_status": _event_value(
            event,
            "status",
        ),

        "evidence_state": _jsonable(
            evidence_state or {}
        ),
    }

    response = (
        client
        .table("risk_history")
        .insert(payload)
        .execute()
    )

    return {
        "status": "SUPABASE_RISK_SNAPSHOT_PERSISTED",
        "persisted": True,
        "data": response.data,
    }


def fetch_event(event_id: str) -> Optional[dict]:
    client = get_supabase()

    if client is None:
        return None

    response = (
        client
        .table("farm_events")
        .select("*")
        .eq("event_id", event_id)
        .maybe_single()
        .execute()
    )

    return response.data