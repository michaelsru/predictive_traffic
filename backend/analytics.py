from sqlalchemy.orm import Session
from models import SegmentReading
from sqlalchemy import desc

def get_latest_status(db: Session):
    status = {}
    for seg in ["S1", "S2", "S3", "S4", "S5"]:
        reading = db.query(SegmentReading).filter(SegmentReading.segment_id == seg).order_by(desc(SegmentReading.timestamp)).first()
        if reading:
            baseline_delta_pct = ((reading.avg_speed_kmh - reading.baseline_avg_speed) / reading.baseline_avg_speed) * 100
            variance_ratio = reading.speed_stddev / 5.0
            
            status[seg] = {
                "segment_id": reading.segment_id,
                "timestamp": reading.timestamp.isoformat(),
                "avg_speed_kmh": reading.avg_speed_kmh,
                "speed_stddev": reading.speed_stddev,
                "sample_count": reading.sample_count,
                "travel_time_seconds": reading.travel_time_seconds,
                "baseline_avg_speed": reading.baseline_avg_speed,
                "baseline_delta_pct": baseline_delta_pct,
                "variance_ratio": variance_ratio
            }
    return status

def get_history(db: Session, segment_id: str, limit: int = 30):
    readings = db.query(SegmentReading).filter(SegmentReading.segment_id == segment_id).order_by(desc(SegmentReading.timestamp)).limit(limit).all()
    return [
        {
            "timestamp": r.timestamp.isoformat(),
            "avg_speed_kmh": r.avg_speed_kmh,
            "speed_stddev": r.speed_stddev
        }
        for r in reversed(readings)
    ]
