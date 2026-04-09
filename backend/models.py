from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from database import Base
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class AlertLog(Base):
    __tablename__ = "alert_logs"

    id           = Column(Integer, primary_key=True, index=True)
    created_at   = Column(DateTime, default=datetime.utcnow)
    segment_id   = Column(String, index=True)
    severity     = Column(String)           # watch | warning | critical | normal (cleared)
    prev_severity = Column(String)          # what it was before this transition
    avg_speed_kmh = Column(Float, nullable=True)
    risk_score   = Column(Float, nullable=True)

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

class IncidentLog(Base):
    __tablename__ = "incident_logs"

    id               = Column(Integer, primary_key=True, index=True)
    created_at       = Column(DateTime, default=datetime.utcnow)
    segment_id       = Column(String, index=True)
    severity         = Column(String)          # minor | moderate | major | critical
    risk_score       = Column(Float, nullable=True)
    avg_speed_kmh    = Column(Float, nullable=True)
    notes            = Column(Text, nullable=True)
    confirmed_by     = Column(String, default="operator")

class IncidentRequest(BaseModel):
    segment_id: str
    severity: str
    risk_score: Optional[float] = None
    avg_speed_kmh: Optional[float] = None
    notes: Optional[str] = None
