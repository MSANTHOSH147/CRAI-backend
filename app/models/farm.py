from sqlalchemy import Column, Float, Integer, String

from app.database import Base


class Farm(Base):
    __tablename__ = "farms"

    id = Column(Integer, primary_key=True, index=True)
    farm_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    crop = Column(String(100), nullable=False)
    area_acres = Column(Float, nullable=False)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    health_score = Column(Float, default=100.0)
    risk_level = Column(String(30), default="LOW")