import threading
import time
import random
from datetime import datetime
from database import SessionLocal, engine, Base
from sqlalchemy import text
from models import SegmentReading

Base.metadata.create_all(bind=engine)

SEGMENTS = [f"S{i}" for i in range(1, 21)]
BASE_SPEED = 100.0
BASE_STDDEV = 5.0

scenario_mode = "normal"
_paused = threading.Event()   # set = paused, clear = running

def set_scenario(mode: str):
    global scenario_mode
    scenario_mode = mode

def pause():
    _paused.set()

def resume():
    _paused.clear()

def is_paused() -> bool:
    return _paused.is_set()

def clear_readings():
    """Truncate segment_readings — call only when paused or from the main thread."""
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM segment_readings"))
        db.commit()
    finally:
        db.close()

def generate_reading(segment_id: str) -> SegmentReading:
    avg_speed = BASE_SPEED
    stddev = BASE_STDDEV
    
    # Natural variance
    avg_speed += random.uniform(-2, 2)
    stddev += random.uniform(-0.5, 0.5)
    
    if scenario_mode == "forming":
        # Old S3 → new S9-S12 (middle corridor); early signs on first two sub-segs
        if segment_id in ("S9", "S10"):
            stddev = BASE_STDDEV * random.uniform(3.0, 4.0)
            avg_speed = BASE_SPEED * random.uniform(0.88, 0.92)
    elif scenario_mode == "incident":
        # Core incident zone: old S3 → new S9-S12
        if segment_id in ("S9", "S10", "S11", "S12"):
            avg_speed = BASE_SPEED * random.uniform(0.2, 0.3)
            stddev = BASE_STDDEV * random.uniform(1.5, 2.5)
        # Upstream spillback: old S2 tail → new S7-S8
        elif segment_id in ("S7", "S8"):
            avg_speed = BASE_SPEED * random.uniform(0.5, 0.6)
            stddev = BASE_STDDEV * random.uniform(2.0, 3.0)
        # Downstream gawking: old S4 head → new S13-S14
        elif segment_id in ("S13", "S14"):
            avg_speed = BASE_SPEED * random.uniform(1.05, 1.1)
            stddev = BASE_STDDEV * random.uniform(0.8, 1.2)
            
    return SegmentReading(
        segment_id=segment_id,
        timestamp=datetime.utcnow(),
        avg_speed_kmh=avg_speed,
        speed_stddev=stddev,
        sample_count=random.randint(50, 150),
        travel_time_seconds=(2.0 / (avg_speed / 3600)) if avg_speed > 0 else 999,
        baseline_avg_speed=BASE_SPEED
    )

def simulator_loop():
    while True:
        if _paused.is_set():
            time.sleep(0.5)
            continue
        db = SessionLocal()
        try:
            for seg in SEGMENTS:
                reading = generate_reading(seg)
                db.add(reading)
            db.commit()
        finally:
            db.close()
        time.sleep(2)

def start_simulator():
    thread = threading.Thread(target=simulator_loop, daemon=True)
    thread.start()
