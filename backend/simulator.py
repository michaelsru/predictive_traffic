import threading
import time
import random
from datetime import datetime
from database import SessionLocal, engine, Base
from sqlalchemy import text
from models import SegmentReading

Base.metadata.create_all(bind=engine)

SEGMENTS = ["S1", "S2", "S3", "S4", "S5"]
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
        if segment_id == "S3":
            stddev = BASE_STDDEV * random.uniform(3.0, 4.0)
            avg_speed = BASE_SPEED * random.uniform(0.88, 0.92)
    elif scenario_mode == "incident":
        if segment_id == "S3":
            avg_speed = BASE_SPEED * random.uniform(0.2, 0.3)
            stddev = BASE_STDDEV * random.uniform(1.5, 2.5)
        elif segment_id == "S2":
            avg_speed = BASE_SPEED * random.uniform(0.5, 0.6)
            stddev = BASE_STDDEV * random.uniform(2.0, 3.0)
        elif segment_id == "S4":
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
