from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
)

from app.database import Base


class SensorAcquisitionRequest(Base):
    __tablename__ = "sensor_acquisition_requests"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    request_id = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    farm_id = Column(
        Integer,
        nullable=True,
        index=True,
    )

    zone_id = Column(
        String(50),
        nullable=True,
        index=True,
    )

    device_id = Column(
        String(100),
        nullable=True,
        index=True,
    )

    source = Column(
        String(30),
        nullable=False,
        default="ESP32",
    )

    requested_evidence = Column(
        String(100),
        nullable=False,
        default="FRESH_SENSOR",
    )

    reason = Column(
        String(200),
        nullable=True,
    )

    priority = Column(
        String(20),
        nullable=False,
        default="MEDIUM",
    )

    status = Column(
        String(30),
        nullable=False,
        default="PENDING",
        index=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    claimed_at = Column(
        DateTime,
        nullable=True,
    )

    completed_at = Column(
        DateTime,
        nullable=True,
    )

    expires_at = Column(
        DateTime,
        nullable=True,
    )

    fulfilled_reading_id = Column(
        String(100),
        nullable=True,
    )