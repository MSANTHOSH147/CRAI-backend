"""
CRAI Supabase client.

Supabase is persistence/infrastructure only.
CRAI intelligence remains inside FastAPI services.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()


def supabase_enabled() -> bool:
    return os.getenv("SUPABASE_ENABLED", "false").lower() == "true"


@lru_cache(maxsize=1)
def get_supabase() -> Optional[Client]:
    if not supabase_enabled():
        return None

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        raise RuntimeError(
            "SUPABASE_ENABLED=true but SUPABASE_URL or "
            "SUPABASE_SERVICE_ROLE_KEY is missing."
        )

    return create_client(url, key)