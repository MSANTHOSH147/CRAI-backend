from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String

from app.database import Base


class SensorData(Base):
    __tablename__ = "sensor_data"

    id = Column(Integer, primary_key=True, index=True)

    mission_id = Column(
        Integer,
        ForeignKey("missions.id"),
        nullable=False,
        index=True,
    )

    sensor_type = Column(
        String(30),
        nullable=False,
    )

    timestamp = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # GPS
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    altitude = Column(Float, nullable=True)

    # Thermal
    temperature = Column(Float, nullable=True)
    min_temperature = Column(Float, nullable=True)
    max_temperature = Column(Float, nullable=True)

    # Environmental
    humidity = Column(Float, nullable=True)

    # RGB / image reference
    image_path = Column(String(255), nullable=True)

    # Optional device information
    device_id = Column(String(100), nullable=True)