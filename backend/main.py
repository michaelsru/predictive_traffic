import logging
import os
import time
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Try loading from backend dir first, then from root dir
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env.local'))
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../.env.local'))

from sqlalchemy.orm import Session
from database import get_db, engine, Base
from models import ChatRequest, IncidentLog, IncidentRequest
from simulator import start_simulator, stop_simulator, set_scenario, is_running, clear_readings
from analytics import get_history, get_pipeline_context
from gemini_client import call_gemini_api
import random
app = FastAPI()

_active_scenario: str = "normal"

_WEATHER_BY_SCENARIO = {
    "normal":   ["clear", "clear", "clear", "cloudy"],
    "forming":  ["cloudy", "light_rain", "light_rain", "fog"],
    "incident": ["heavy_rain", "fog", "light_rain", "snow"],
}

def _get_weather() -> str:
    return random.choice(_WEATHER_BY_SCENARIO.get(_active_scenario, ["clear"]))

# Pipeline cache — shared between /api/status and /api/chat (one run per simulator tick)
_pipeline_cache: dict = {"result": None, "ts": 0.0}
_CACHE_TTL = 2.0  # seconds — matches simulator tick rate

def _get_cached_pipeline(db) -> dict:
    now = time.monotonic()
    if _pipeline_cache["result"] is None or (now - _pipeline_cache["ts"]) > _CACHE_TTL:
        _pipeline_cache["result"] = get_pipeline_context(
            db, active_scenario=_active_scenario, weather=_get_weather()
        )
        _pipeline_cache["ts"] = now
    return _pipeline_cache["result"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    start_simulator()

@app.get("/api/simulator/status")
def simulator_status():
    return {"running": is_running()}


@app.post("/api/simulator/{action}")
def simulator_control(action: str):
    if action == "stop":
        stop_simulator()
    elif action == "start":
        start_simulator()
    elif action == "clear":
        stop_simulator()
        clear_readings()
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action '{action}'")
    return {"running": is_running()}


@app.get("/api/status")
def read_status(db: Session = Depends(get_db)):
    ctx = _get_cached_pipeline(db)
    return {seg["segment_id"]: seg for seg in ctx["segments"]}


@app.get("/api/history/{seg}")
def read_history(seg: str, limit: int = 30, db: Session = Depends(get_db)):
    if seg not in [f"S{i}" for i in range(1, 21)]:
        raise HTTPException(status_code=404, detail="Segment not found")
    return get_history(db, seg, limit=min(limit, 60))

@app.post("/api/scenario/{mode}")
def update_scenario(mode: str):
    global _active_scenario
    if mode not in ["normal", "forming", "incident"]:
        raise HTTPException(status_code=400, detail="Invalid mode")
    _active_scenario = mode
    set_scenario(mode)
    # Bust cache so next request reflects the new scenario immediately
    _pipeline_cache["ts"] = 0.0
    return {"status": "success", "mode": mode}

@app.post("/api/incident")
def log_incident(request: IncidentRequest, db: Session = Depends(get_db)):
    VALID_SEVERITIES = {"minor", "moderate", "major", "critical"}
    if request.severity not in VALID_SEVERITIES:
        raise HTTPException(status_code=400, detail=f"severity must be one of {VALID_SEVERITIES}")
    log = IncidentLog(
        segment_id=request.segment_id,
        severity=request.severity,
        risk_score=request.risk_score,
        avg_speed_kmh=request.avg_speed_kmh,
        notes=request.notes,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return {
        "id":           log.id,
        "created_at":   log.created_at.isoformat(),
        "segment_id":   log.segment_id,
        "severity":     log.severity,
        "risk_score":   log.risk_score,
        "avg_speed_kmh": log.avg_speed_kmh,
        "notes":        log.notes,
        "confirmed_by": log.confirmed_by,
    }


@app.get("/api/incidents")
def list_incidents(
    limit: int = 50,
    offset: int = 0,
    segment_id: str | None = None,
    db: Session = Depends(get_db),
):
    from sqlalchemy import desc as _desc
    q = db.query(IncidentLog)
    if segment_id:
        q = q.filter(IncidentLog.segment_id == segment_id)
    total = q.count()
    rows = q.order_by(_desc(IncidentLog.created_at)).offset(offset).limit(min(limit, 200)).all()
    return {
        "total": total,
        "items": [
            {
                "id":            row.id,
                "created_at":    row.created_at.isoformat(),
                "segment_id":    row.segment_id,
                "severity":      row.severity,
                "risk_score":    row.risk_score,
                "avg_speed_kmh": row.avg_speed_kmh,
                "notes":         row.notes,
                "confirmed_by":  row.confirmed_by,
            }
            for row in rows
        ],
    }


@app.get("/api/readings")
def list_readings(
    limit: int = 100,
    offset: int = 0,
    segment_id: str | None = None,
    min_severity: str | None = None,   # "watch" | "warning" | "critical"
    db: Session = Depends(get_db),
):
    """Paginated SegmentReading rows with analytics fields computed from available signals."""
    from sqlalchemy import desc as _desc
    from models import SegmentReading as SR
    from analytics import NORMAL_STDDEV, score_to_severity, compute_risk_score

    _SEV_RANK = {"normal": 0, "watch": 1, "warning": 2, "critical": 3}
    min_rank  = _SEV_RANK.get(min_severity or "", 0)

    q = db.query(SR)
    if segment_id:
        q = q.filter(SR.segment_id == segment_id)
    total_unfiltered = q.count()

    # Over-fetch to compensate for severity filtering (severity not stored in DB)
    rows = q.order_by(_desc(SR.timestamp)).offset(offset).limit(min(limit * 4, 2000)).all()

    items = []
    for row in rows:
        normal_stddev  = NORMAL_STDDEV.get(row.segment_id, 5.5)
        variance_ratio = round(row.speed_stddev / normal_stddev, 2) if normal_stddev > 0 else 1.0
        baseline_delta = (
            round(((row.avg_speed_kmh - row.baseline_avg_speed) / row.baseline_avg_speed) * 100, 1)
            if row.baseline_avg_speed > 0 else 0.0
        )
        # Note: historical rows don't have rolling CUSUM/z-score state, so those
        # contributions are 0. Risk score is conservative (under-reports severity)
        # but is consistent and honest about what signals are available.
        risk_score = compute_risk_score(
            variance_ratio=variance_ratio,
            cusum_upper=0.0,
            baseline_delta_pct=baseline_delta,
            z_speed=0.0,
        )
        severity = score_to_severity(risk_score)

        if _SEV_RANK.get(severity, 0) < min_rank:
            continue

        items.append({
            "id":                  row.id,
            "timestamp":           row.timestamp.isoformat(),
            "segment_id":          row.segment_id,
            "avg_speed_kmh":       round(row.avg_speed_kmh, 1),
            "speed_stddev":        round(row.speed_stddev, 1),
            "baseline_avg_speed":  round(row.baseline_avg_speed, 1),
            "baseline_delta_pct":  baseline_delta,
            "variance_ratio":      variance_ratio,
            "sample_count":        row.sample_count,
            "travel_time_seconds": round(row.travel_time_seconds, 1) if row.travel_time_seconds else None,
            "risk_score":          risk_score,
            "severity":            severity,
        })

        if len(items) >= limit:
            break

    return {"total": total_unfiltered, "items": items}


@app.post("/api/chat")
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    llm_context = _get_cached_pipeline(db)
    try:
        response = call_gemini_api(request.message, request.history, llm_context, db)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn

    class _SuppressApiPolling(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return "/api/" not in record.getMessage()

    logging.getLogger("uvicorn.access").addFilter(_SuppressApiPolling())

    uvicorn.run(app, host="0.0.0.0", port=8000)
