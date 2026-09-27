from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class VisualEvidenceAssociateRequest(BaseModel):
    event_id: Optional[str] = None
    phase: Optional[str] = None
    parent_observation_id: Optional[str] = None
