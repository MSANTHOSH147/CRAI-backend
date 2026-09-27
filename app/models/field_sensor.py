from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
)

from app.database import Base


class FieldSensorReading(Base):
    __tablename__ = "field_sensor_readings"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    reading_id = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    device_id = Column(
        String(100),
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

    source = Column(
        String(30),
        nullable=False,
        default="REAL",
    )

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

    soil_temperature = Column(Float, nullable=True)
    soil_ph = Column(Float, nullable=True)
    soil_ec = Column(Float, nullable=True)
    leaf_wetness = Column(Float, nullable=True)

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    altitude = Column(Float, nullable=True)
    battery = Column(Float, nullable=True)
    signal_strength = Column(Float, nullable=True)
    gateway_id = Column(String(100), nullable=True, index=True)
    sequence_number = Column(Integer, nullable=True)

    timestamp = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )