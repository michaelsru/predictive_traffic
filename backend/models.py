from sqlalchemy import Column, Integer, String, Float, DateTime
from database import Base
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class SegmentReading(Base):
    __tablename__ = "segment_readings"

    id = Column(Integer, primary_key=True, index=True)
    segment_id = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    avg_speed_kmh = Column(Float)
    speed_stddev = Column(Float)
    sample_count = Column(Integer)
    travel_time_seconds = Column(Float)
    baseline_avg_speed = Column(Float)

class ChatRequest(BaseModel):
    message: str
    history: List[dict] = []
