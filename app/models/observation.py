from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    JSON,
    String,
)

from app.database import Base


class FieldObservation(Base):
    __tablename__ = "field_observations"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    observation_id = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # FIELD CONTEXT
    # --------------------------------------------------------

    farm_id = Column(
        Integer,
        nullable=True,
        index=True,
    )

    zone_id = Column(
        String(50),
        nullable=False,
        index=True,
    )

    crop = Column(
        String(100),
        nullable=True,
    )

    growth_stage = Column(
        String(100),
        nullable=True,
    )

    # --------------------------------------------------------
    # OBSERVATION TIME
    # --------------------------------------------------------

    observed_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # IMAGE / MODEL EVIDENCE
    # --------------------------------------------------------

    filename = Column(
        String(255),
        nullable=True,
    )

    image_sha256 = Column(
        String(64),
        nullable=True,
        index=True,
    )

    prediction = Column(
        String(150),
        nullable=True,
    )

    disease_confidence = Column(
        Float,
        nullable=True,
    )

    # --------------------------------------------------------
    # FINAL FIELD RISK
    # --------------------------------------------------------

    risk_score = Column(
        Float,
        nullable=True,
    )

    risk_level = Column(
        String(30),
        nullable=True,
    )

    assessment_confidence = Column(
        String(30),
        nullable=True,
    )

    # --------------------------------------------------------
    # CURRENT ENVIRONMENT SNAPSHOT
    # --------------------------------------------------------

    soil_moisture = Column(
        Float,
        nullable=True,
    )

    temperature = Column(
        Float,
        nullable=True,
    )

    humidity = Column(
        Float,
        nullable=True,
    )

    thermal_anomaly = Column(
        Float,
        nullable=True,
    )

    # --------------------------------------------------------
    # EXPLAINABLE FUSION SNAPSHOT
    # --------------------------------------------------------

    evidence_breakdown = Column(
        JSON,
        nullable=True,
    )

    evidence_summary = Column(
        JSON,
        nullable=True,
    )

    # --------------------------------------------------------
    # SOURCE
    # --------------------------------------------------------

    source = Column(
        String(50),
        nullable=False,
        default="FIELD_IMAGE",
    )