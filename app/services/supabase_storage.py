from __future__ import annotations

import json
from typing import Any

from app.services.supabase_client import get_supabase


BUCKET_NAME = "crai-evidence"


def upload_event_evidence(
    event_id: str,
    evidence_package: dict[str, Any],
) -> dict:

    client = get_supabase()

    if client is None:
        return {
            "status": "SUPABASE_DISABLED",
            "uploaded": False,
        }

    payload = json.dumps(
        evidence_package,
        indent=2,
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")

    storage_path = (
        f"events/{event_id}/evidence.json"
    )

    response = (
        client
        .storage
        .from_(BUCKET_NAME)
        .upload(
            storage_path,
            payload,
            file_options={
                "content-type": "application/json",
                "upsert": "true",
            },
        )
    )

    return {
        "status": "EVIDENCE_UPLOADED",
        "uploaded": True,
        "bucket": BUCKET_NAME,
        "path": storage_path,
        "response": str(response),
    }


def create_evidence_signed_url(
    storage_path: str,
    expires_in: int = 3600,
) -> dict:

    client = get_supabase()

    if client is None:
        return {
            "status": "SUPABASE_DISABLED",
            "url": None,
        }

    response = (
        client
        .storage
        .from_(BUCKET_NAME)
        .create_signed_url(
            storage_path,
            expires_in,
        )
    )

    return {
        "status": "SIGNED_URL_CREATED",
        "bucket": BUCKET_NAME,
        "path": storage_path,
        "expires_in": expires_in,
        "data": response,
    }