from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.supabase_client import (
    get_supabase,
    supabase_enabled,
)

router = APIRouter(
    prefix="/api/supabase",
    tags=["supabase"],
)


@router.get("/status")
def supabase_status():

    if not supabase_enabled():
        return {
            "enabled": False,
            "connected": False,
            "status": "DISABLED",
        }

    try:

        client = get_supabase()

        if client is None:
            return {
                "enabled": True,
                "connected": False,
                "status": "NOT_INITIALIZED",
            }

        response = (
            client
            .table("farm_events")
            .select("event_id")
            .limit(1)
            .execute()
        )

        return {
            "enabled": True,
            "connected": True,
            "status": "READY",
            "rows_visible": len(
                response.data or []
            ),
        }

    except Exception as exc:

        raise HTTPException(
            status_code=503,
            detail={
                "status": "SUPABASE_CONNECTION_FAILED",
                "error": str(exc),
            },
        )