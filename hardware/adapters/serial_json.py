"""
CRAI Serial JSON Evidence Adapter

Expected device protocol:
    one JSON object per line

Example:
    {"soil_moisture":31.2,"temperature":29.4,"humidity":78.1,"zone":"A"}

The CRAI intelligence layer does not depend on this transport.
"""

import json
from typing import Any, Dict, Optional

from .base import EvidenceAdapter


class SerialJsonEvidenceAdapter(
    EvidenceAdapter
):

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        timeout: float = 2.0,
    ):

        try:
            import serial

        except ImportError as exc:

            raise RuntimeError(
                "pyserial is required only when using "
                "the serial hardware adapter. "
                "Install it with: pip install pyserial"
            ) from exc

        self._serial = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=timeout,
        )

    def read(
        self,
    ) -> Optional[Dict[str, Any]]:

        raw = self._serial.readline()

        if not raw:
            return None

        try:

            text = raw.decode(
                "utf-8",
                errors="ignore",
            ).strip()

            if not text:
                return None

            payload = json.loads(
                text
            )

        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ):

            return None

        if not isinstance(
            payload,
            dict,
        ):

            return None

        return payload

    def close(
        self,
    ) -> None:

        if getattr(
            self,
            "_serial",
            None,
        ) is not None:

            self._serial.close()
