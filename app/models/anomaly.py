from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String

from app.database import Base


class Anomaly(Base):
    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True, index=True)

    mission_id = Column(
        Integer,
        ForeignKey("missions.id"),
        nullable=False,
        index=True,
    )

    region = Column(
        String(50),
        nullable=False,
    )

    detection = Column(
        String(150),
        nullable=False,
    )

    confidence = Column(
        Float,
        nullable=False,
    )

    temperature = Column(
        Float,
        nullable=True,
    )

    latitude = Column(
        Float,
        nullable=True,
    )

    longitude = Column(
        Float,
        nullable=True,
    )

    risk_level = Column(
        String(30),
        nullable=False,
    )

    recommendation = Column(
        String(255),
        nullable=True,
    )

    image_path = Column(
        String(255),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )