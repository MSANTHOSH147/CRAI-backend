"""
CRAI Hardware Adapter Interface

The CRAI intelligence layer consumes normalized evidence dictionaries.
Any sensor board, gateway, serial device, BLE device, LoRa gateway,
or future vendor integration can implement this interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class EvidenceAdapter(ABC):

    @abstractmethod
    def read(self) -> Optional[Dict[str, Any]]:
        """Return one normalized evidence packet or None."""
        raise NotImplementedError

    def close(self) -> None:
        """Optional cleanup hook."""
        return None


class DictEvidenceAdapter(EvidenceAdapter):
    """Useful for simulation, tests, MQTT callbacks, or direct integration."""

    def __init__(
        self,
        payload: Optional[Dict[str, Any]] = None,
    ):
        self.payload = payload or {}

    def update(
        self,
        payload: Dict[str, Any],
    ) -> None:

        self.payload = dict(payload)

    def read(
        self,
    ) -> Optional[Dict[str, Any]]:

        return (
            dict(self.payload)
            if self.payload
            else None
        )
