"""Deterministic field-device simulator for CRAI software-only development.

The simulator intentionally uses source=SIMULATED and talks to the same
field-sensor data model used by physical devices. It never changes a
SIMULATED reading into REAL evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import random
from typing import Optional

from sqlalchemy.orm import Session

from app.models.field_sensor import FieldSensorReading


SCENARIOS = {
    "NORMAL",
    "DEVELOPING_STRESS",
    "DISEASE_RISK",
    "SEVERE_EVENT",
    "RECOVERY",
}


@dataclass
class SimulatorState:
    device_id: str = "CRAI-SIM-001"
    farm_id: Optional[int] = None
    zone_id: str = "A1"
    scenario: str = "NORMAL"
    interval: float = 15.0
    seed: int = 42
    step: int = 0
    running: bool = False
    last_reading_id: Optional[str] = None
    last_timestamp: Optional[datetime] = None

    def reset(self) -> None:
        self.step = 0
        self.last_reading_id = None
        self.last_timestamp = None


_STATE = SimulatorState()


def get_state() -> SimulatorState:
    return _STATE


def configure(
    *,
    device_id: str,
    farm_id: Optional[int],
    zone_id: str,
    scenario: str,
    interval: float,
    seed: int,
    reset_step: bool = True,
) -> SimulatorState:
    scenario = str(scenario).upper()
    if scenario not in SCENARIOS:
        raise ValueError(f"Unsupported simulator scenario: {scenario}")

    _STATE.device_id = device_id
    _STATE.farm_id = farm_id
    _STATE.zone_id = zone_id.strip().upper()
    _STATE.scenario = scenario
    _STATE.interval = interval
    _STATE.seed = seed
    if reset_step:
        _STATE.reset()
    return _STATE


def start() -> SimulatorState:
    _STATE.running = True
    return _STATE


def stop() -> SimulatorState:
    _STATE.running = False
    return _STATE


def _bounded(value: float, low: float, high: float) -> float:
    return round(max(low, min(high, value)), 2)


def _scenario_values(scenario: str, step: int, seed: int) -> dict:
    # A deterministic RNG makes the same seed + step reproducible.
    rng = random.Random(seed + step * 1009)
    noise = lambda magnitude: rng.uniform(-magnitude, magnitude)

    if scenario == "NORMAL":
        return {
            "soil_moisture": _bounded(55 + noise(2), 0, 100),
            "soil_temperature": _bounded(27 + noise(0.8), -20, 80),
            "soil_ph": _bounded(6.5 + noise(0.12), 3, 10),
            "soil_ec": _bounded(1.0 + noise(0.08), 0, 10),
            "temperature": _bounded(28 + noise(1.0), -20, 80),
            "humidity": _bounded(62 + noise(3), 0, 100),
            "leaf_wetness": _bounded(10 + noise(4), 0, 100),
        }

    if scenario == "DEVELOPING_STRESS":
        return {
            "soil_moisture": _bounded(55 - 3.5 * step + noise(1), 8, 100),
            "soil_temperature": _bounded(29 + 0.35 * step + noise(0.5), -20, 80),
            "soil_ph": _bounded(6.5 + noise(0.15), 3, 10),
            "soil_ec": _bounded(1.0 + 0.05 * step + noise(0.05), 0, 10),
            "temperature": _bounded(29 + 0.7 * step + noise(0.8), -20, 80),
            "humidity": _bounded(65 + 1.5 * step + noise(2), 0, 100),
            "leaf_wetness": _bounded(18 + 2.5 * step + noise(3), 0, 100),
        }

    if scenario == "DISEASE_RISK":
        return {
            "soil_moisture": _bounded(46 - 1.5 * step + noise(1), 15, 100),
            "soil_temperature": _bounded(30 + 0.25 * step + noise(0.5), -20, 80),
            "soil_ph": _bounded(6.3 + noise(0.12), 3, 10),
            "soil_ec": _bounded(1.2 + 0.03 * step + noise(0.05), 0, 10),
            "temperature": _bounded(30 + 0.35 * step + noise(0.7), -20, 80),
            "humidity": _bounded(80 + 0.9 * step + noise(1.5), 0, 100),
            "leaf_wetness": _bounded(58 + 3.5 * step + noise(3), 0, 100),
        }

    if scenario == "SEVERE_EVENT":
        return {
            "soil_moisture": _bounded(17 + noise(2), 0, 100),
            "soil_temperature": _bounded(38 + noise(1), -20, 80),
            "soil_ph": _bounded(5.8 + noise(0.2), 3, 10),
            "soil_ec": _bounded(1.8 + noise(0.12), 0, 10),
            "temperature": _bounded(39 + noise(1), -20, 80),
            "humidity": _bounded(92 + noise(2), 0, 100),
            "leaf_wetness": _bounded(94 + noise(3), 0, 100),
        }

    # RECOVERY: conditions improve as steps advance.
    recovery = min(step, 12)
    return {
        "soil_moisture": _bounded(22 + recovery * 2.5 + noise(1), 0, 100),
        "soil_temperature": _bounded(37 - recovery * 0.45 + noise(0.6), -20, 80),
        "soil_ph": _bounded(6.0 + recovery * 0.03 + noise(0.1), 3, 10),
        "soil_ec": _bounded(1.7 - recovery * 0.04 + noise(0.05), 0, 10),
        "temperature": _bounded(38 - recovery * 0.7 + noise(0.7), -20, 80),
        "humidity": _bounded(90 - recovery * 1.8 + noise(2), 0, 100),
        "leaf_wetness": _bounded(88 - recovery * 6 + noise(3), 0, 100),
    }


def generate_reading_payload(state: SimulatorState) -> dict:
    values = _scenario_values(state.scenario, state.step, state.seed)
    timestamp = datetime.utcnow()
    return {
        "device_id": state.device_id,
        "farm_id": state.farm_id,
        "zone_id": state.zone_id,
        "source": "SIMULATED",
        "timestamp": timestamp,
        "temperature": values["temperature"],
        "humidity": values["humidity"],
        "soil_moisture": values["soil_moisture"],
        "soil_temperature": values["soil_temperature"],
        "soil_ph": values["soil_ph"],
        "soil_ec": values["soil_ec"],
        "leaf_wetness": values["leaf_wetness"],
        "latitude": None,
        "longitude": None,
        "altitude": None,
        "battery": 100.0,
        "signal_strength": None,
        "gateway_id": "CRAI-SIM-GATEWAY",
        "sequence_number": state.step,
    }


def persist_step(db: Session, *, state: Optional[SimulatorState] = None) -> FieldSensorReading:
    state = state or _STATE
    state.step += 1
    payload = generate_reading_payload(state)

    reading_id = (
        f"SIM-{payload['timestamp'].strftime('%Y%m%d%H%M%S')}-"
        f"{state.step:04d}"
    )

    reading = FieldSensorReading(
        reading_id=reading_id,
        device_id=payload["device_id"],
        farm_id=payload["farm_id"],
        zone_id=payload["zone_id"],
        source="SIMULATED",
        soil_moisture=payload["soil_moisture"],
        soil_temperature=payload["soil_temperature"],
        soil_ph=payload["soil_ph"],
        soil_ec=payload["soil_ec"],
        leaf_wetness=payload["leaf_wetness"],
        temperature=payload["temperature"],
        humidity=payload["humidity"],
        latitude=payload["latitude"],
        longitude=payload["longitude"],
        altitude=payload["altitude"],
        battery=payload["battery"],
        signal_strength=payload["signal_strength"],
        gateway_id=payload["gateway_id"],
        sequence_number=payload["sequence_number"],
        timestamp=payload["timestamp"],
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)

    state.last_reading_id = reading.reading_id
    state.last_timestamp = reading.timestamp
    return reading
