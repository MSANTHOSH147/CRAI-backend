from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    JSON,
    String,
    Text,
)

from app.database import Base


class PendingFieldAnalysis(Base):
    __tablename__ = "pending_field_analyses"

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

    crop = Column(
        String(100),
        nullable=False,
        default="Tomato",
    )

    growth_stage = Column(
        String(100),
        nullable=False,
        default="Vegetative",
    )

    filename = Column(
        String(255),
        nullable=True,
    )

    image_path = Column(
        Text,
        nullable=False,
    )

    prediction = Column(
        String(255),
        nullable=True,
    )

    confidence = Column(
        Float,
        nullable=True,
    )

    image_quality = Column(
        JSON,
        nullable=True,
    )

    evidence_gap = Column(
        String(100),
        nullable=True,
    )

    reason = Column(
        Text,
        nullable=True,
    )

    advisory_language = Column(
        String(20),
        nullable=False,
        default="English",
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

    completed_at = Column(
        DateTime,
        nullable=True,
    )