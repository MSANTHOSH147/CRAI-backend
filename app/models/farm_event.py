from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, JSON, String

from app.database import Base


class FarmEvent(Base):
    __tablename__ = "farm_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(100), unique=True, nullable=False, index=True)

    farm_id = Column(Integer, nullable=True, index=True)
    zone_id = Column(String(50), nullable=False, index=True)
    device_id = Column(String(100), nullable=True, index=True)

    status = Column(String(30), nullable=False, default="DETECTED", index=True)

    started_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    detected_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    crop = Column(String(100), nullable=True)
    crop_stage = Column(String(100), nullable=True)

    before_state = Column(JSON, nullable=True)
    during_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)

    risk_level = Column(String(30), nullable=True)
    risk_score = Column(Float, nullable=True)
    decision = Column(JSON, nullable=True)
    action = Column(String(100), nullable=True)

    evidence_sources = Column(JSON, nullable=True)
    image_references = Column(JSON, nullable=True)
    sensor_references = Column(JSON, nullable=True)
    temporal_context = Column(JSON, nullable=True)
    spatial_context = Column(JSON, nullable=True)

    evidence_package = Column(JSON, nullable=True)
    integrity_hash = Column(String(64), nullable=True, index=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
