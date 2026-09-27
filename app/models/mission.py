from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String

from app.database import Base


class Mission(Base):
    __tablename__ = "missions"

    id = Column(Integer, primary_key=True, index=True)

    mission_code = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    farm_id = Column(
        Integer,
        ForeignKey("farms.id"),
        nullable=False,
    )

    status = Column(
        String(30),
        default="PLANNED",
        nullable=False,
    )

    battery = Column(Float, default=100.0)

    altitude = Column(Float, default=0.0)

    coverage = Column(Float, default=0.0)

    start_time = Column(DateTime, nullable=True)

    end_time = Column(DateTime, nullable=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )