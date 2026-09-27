from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.field_sensor import FieldSensorReading
from app.services import field_simulator_service as simulator
from app.services.analysis_service import analyze_field_observation
from app.services.farm_event_service import create_or_update_event
from app.services.observation_service import (
    get_spatial_context,
    get_temporal_history,
)

router = APIRouter(
    prefix="/api/crai",
    tags=["CRAI End-to-End"],
)


class SimulatorAssessRequest(BaseModel):
    device_id: str = "CRAI-SIM-001"
    farm_id: Optional[int] = 1
    zone_id: str = "A1"

    crop: str = "Tomato"
    growth_stage: str = "Vegetative"

    prediction: str = "Tomato_Healthy"
    confidence: float = Field(default=95.0, ge=0.0, le=100.0)
    thermal_anomaly: float = 0.0

    advisory_language: str = "en"

    scenario: Optional[str] = None

    max_sensor_refreshes: int = Field(
        default=3,
        ge=0,
        le=3,
    )


class RealAssessRequest(BaseModel):
    device_id: str
    farm_id: Optional[int] = None
    zone_id: str

    crop: str = "Tomato"
    growth_stage: str = "Vegetative"

    prediction: str = "Tomato_Healthy"
    confidence: float = Field(default=95.0, ge=0.0, le=100.0)
    thermal_anomaly: float = 0.0

    advisory_language: str = "en"


def sensor_payload(row: FieldSensorReading) -> dict[str, Any]:
    return {
        "available": True,
        "device_id": row.device_id,
        "reading_id": row.reading_id,
        "farm_id": row.farm_id,
        "zone_id": row.zone_id,
        "source": str(row.source or "").upper(),

        "soil_moisture": row.soil_moisture,
        "soil_temperature": getattr(
            row,
            "soil_temperature",
            None,
        ),
        "soil_ph": getattr(
            row,
            "soil_ph",
            None,
        ),
        "soil_ec": getattr(
            row,
            "soil_ec",
            None,
        ),
        "leaf_wetness": getattr(
            row,
            "leaf_wetness",
            None,
        ),

        "temperature": row.temperature,
        "humidity": row.humidity,

        "timestamp": (
            row.timestamp.isoformat()
            if row.timestamp
            else None
        ),
    }


def run_authoritative_analysis(
    db: Session,
    *,
    row: FieldSensorReading,
    prediction: str,
    confidence: float,
    crop: str,
    growth_stage: str,
    thermal_anomaly: float,
    advisory_language: str,
):
    sensor = sensor_payload(row)

    history = get_temporal_history(
        farm_id=row.farm_id,
        zone_id=row.zone_id,
        crop=crop,
    )

    spatial = get_spatial_context(
        farm_id=row.farm_id,
        zone_id=row.zone_id,
    )

    analysis = analyze_field_observation(
        prediction=prediction,
        confidence=confidence,
        crop=crop,
        growth_stage=growth_stage,
        temperature=row.temperature,
        humidity=row.humidity,
        thermal_anomaly=thermal_anomaly,
        sensor=sensor,
        spatial_context=spatial,
        history=history,
        advisory_language=advisory_language,
    )

    event = None

    decision = analysis.get(
        "decision",
        {},
    )

    if (
        analysis.get("status")
        == "ANALYSIS_COMPLETE"
        and decision.get(
            "ready",
            True,
        )
    ):
        event = create_or_update_event(
            db,
            analysis=analysis,
            farm_id=row.farm_id,
            zone_id=row.zone_id,
            device_id=row.device_id,
            crop=crop,
            crop_stage=growth_stage,
        )

    return {
        "analysis": analysis,
        "event": event,
        "sensor": sensor,
    }


@router.post("/simulator/assess")
def simulator_assess(
    payload: SimulatorAssessRequest,
    db: Session = Depends(get_db),
):
    """
    Bounded simulator acquisition loop.

    SIMULATED data can only remain SIMULATED.

    If CRAI requests another sensor reading,
    the simulator acquires a fresh simulated reading.

    If CRAI requests evidence that cannot honestly
    be fabricated, the loop stops safely.
    """

    zone = payload.zone_id.strip().upper()

    simulator.configure(
    device_id=payload.device_id,
    farm_id=payload.farm_id,
    zone_id=zone,
    scenario=payload.scenario or "NORMAL",
    interval=15.0,
    seed=42,
    reset_step=True,
)

    attempts = []

    maximum = (
        payload.max_sensor_refreshes
        + 1
    )

    final_result = None

    for attempt in range(
        1,
        maximum + 1,
    ):
        row = simulator.persist_step(
            db,
            state=simulator.get_state(),
        )

        result = run_authoritative_analysis(
            db,
            row=row,
            prediction=payload.prediction,
            confidence=payload.confidence,
            crop=payload.crop,
            growth_stage=payload.growth_stage,
            thermal_anomaly=payload.thermal_anomaly,
            advisory_language=payload.advisory_language,
        )

        final_result = result

        analysis = result["analysis"]

        decision = analysis.get(
            "decision",
            {},
        )

        adaptive = (
            analysis.get(
                "adaptive_evidence"
            )
            or analysis.get(
                "adaptive"
            )
            or {}
        )

        requested = (
            adaptive.get(
                "requested_evidence",
                [],
            )
            or decision.get(
                "requested_evidence",
                [],
            )
        )

        attempts.append(
            {
                "attempt": attempt,
                "reading_id": row.reading_id,
                "source": str(
                    row.source or ""
                ).upper(),
                "timestamp": (
                    row.timestamp.isoformat()
                    if row.timestamp
                    else None
                ),
                "decision_ready": bool(
                    decision.get(
                        "ready",
                        False,
                    )
                ),
                "requested_evidence": requested,
            }
        )

        if decision.get(
            "ready",
            False,
        ):
            return {
                "status":
                    "CRAI_ASSESSMENT_COMPLETE",

                "mode":
                    "SIMULATED",

                "decision_ready":
                    True,

                "attempts":
                    attempts,

                **result,
            }

        sensor_requested = any(
            str(item).upper()
            in {
                "FRESH_SENSOR_READING",
                "ENVIRONMENT",
                "SENSOR",
            }
            for item in requested
        )

        if not sensor_requested:
            return {
                "status":
                    "ADDITIONAL_EVIDENCE_REQUIRED",

                "mode":
                    "SIMULATED",

                "decision_ready":
                    False,

                "attempts":
                    attempts,

                "reason":
                    (
                        "CRAI requested evidence that "
                        "the simulator cannot truthfully "
                        "fabricate."
                    ),

                **result,
            }

    return {
        "status":
            "ADDITIONAL_EVIDENCE_REQUIRED",

        "mode":
            "SIMULATED",

        "decision_ready":
            False,

        "attempts":
            attempts,

        "reason":
            (
                "Maximum safe simulated sensor "
                "refreshes reached."
            ),

        **final_result,
    }


@router.post("/real/assess")
def real_assess(
    payload: RealAssessRequest,
    db: Session = Depends(get_db),
):
    """
    REAL hardware assessment.

    Only source=REAL is accepted.

    SIMULATED readings are never substituted.
    """

    zone = payload.zone_id.strip().upper()

    query = (
        db.query(
            FieldSensorReading
        )
        .filter(
            FieldSensorReading.device_id
            == payload.device_id,

            FieldSensorReading.zone_id
            == zone,

            FieldSensorReading.source
            == "REAL",
        )
    )

    if payload.farm_id is not None:
        query = query.filter(
            FieldSensorReading.farm_id
            == payload.farm_id
        )

    row = (
        query
        .order_by(
            FieldSensorReading.timestamp.desc()
        )
        .first()
    )

    if row is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "No REAL sensor reading exists "
                "for this device and zone. "
                "Submit the ESP32 reading first. "
                "SIMULATED readings are never "
                "substituted for REAL evidence."
            ),
        )

    result = run_authoritative_analysis(
        db,
        row=row,
        prediction=payload.prediction,
        confidence=payload.confidence,
        crop=payload.crop,
        growth_stage=payload.growth_stage,
        thermal_anomaly=payload.thermal_anomaly,
        advisory_language=payload.advisory_language,
    )

    return {
        "status":
            "CRAI_REAL_ASSESSMENT_COMPLETE",

        "mode":
            "REAL",

        "decision_ready":
            bool(
                (
                    result["analysis"]
                    .get("decision")
                    or {}
                )
                .get(
                    "ready",
                    False,
                )
            ),

        **result,
    }
