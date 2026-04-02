import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Try loading from backend dir first, then from root dir
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env.local'))
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../.env.local'))

from sqlalchemy.orm import Session
from database import get_db, engine, Base
from models import ChatRequest, IncidentLog, IncidentRequest
from simulator import start_simulator, set_scenario, pause, resume, is_paused, clear_readings
from analytics import get_history, get_pipeline_context
from gemini_client import call_gemini_api
import random
app = FastAPI()

# Track active scenario so analytics context stays in sync
_active_scenario: str = "normal"

# Lightweight weather simulation — deterministic enough per scenario
_WEATHER_BY_SCENARIO = {
    "normal":   ["clear", "clear", "clear", "cloudy"],
    "forming":  ["cloudy", "light_rain", "light_rain", "fog"],
    "incident": ["heavy_rain", "fog", "light_rain", "snow"],
}

def _get_weather() -> str:
    options = _WEATHER_BY_SCENARIO.get(_active_scenario, ["clear"])
    return random.choice(options)

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
    return {"running": not is_paused()}


@app.post("/api/simulator/{action}")
def simulator_control(action: str):
    if action == "stop":
        pause()
    elif action == "start":
        resume()
    elif action == "clear":
        pause()
        clear_readings()
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action '{action}'")
    return {"running": not is_paused()}


@app.get("/api/status")
def read_status(db: Session = Depends(get_db)):
    ctx = get_pipeline_context(
        db,
        active_scenario=_active_scenario,
        weather=_get_weather(),
    )
    # Reshape list → {segmentId: {...}} dict that the frontend expects
    return {seg["segment_id"]: seg for seg in ctx["segments"]}


@app.get("/api/history/{seg}")
def read_history(seg: str, limit: int = 30, db: Session = Depends(get_db)):
    if seg not in ["S1", "S2", "S3", "S4", "S5"]:
        raise HTTPException(status_code=404, detail="Segment not found")
    return get_history(db, seg, limit=min(limit, 60))

@app.post("/api/scenario/{mode}")
def update_scenario(mode: str):
    global _active_scenario
    if mode not in ["normal", "forming", "incident"]:
        raise HTTPException(status_code=400, detail="Invalid mode")
    _active_scenario = mode
    set_scenario(mode)
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
    """Return paginated SegmentReading rows enriched with computed analytics fields."""
    from sqlalchemy import desc as _desc
    from models import SegmentReading as SR
    from analytics import (
        NORMAL_STDDEV, SEVERITY_THRESHOLDS, score_to_severity,
        compute_risk_score,
    )

    _SEV_RANK = {"normal": 0, "watch": 1, "warning": 2, "critical": 3}
    min_rank  = _SEV_RANK.get(min_severity or "", 0)

    q = db.query(SR)
    if segment_id:
        q = q.filter(SR.segment_id == segment_id)
    total_unfiltered = q.count()

    # Fetch a broad window then apply severity filter in Python
    # (severity is computed, not stored — avoid storing it to keep DB simple)
    rows = q.order_by(_desc(SR.timestamp)).offset(offset).limit(min(limit * 4, 2000)).all()

    items = []
    for row in rows:
        normal_stddev   = NORMAL_STDDEV.get(row.segment_id, 5.5)
        variance_ratio  = round(row.speed_stddev / normal_stddev, 2) if normal_stddev > 0 else 1.0
        baseline_delta  = (
            round(((row.avg_speed_kmh - row.baseline_avg_speed) / row.baseline_avg_speed) * 100, 1)
            if row.baseline_avg_speed > 0 else 0.0
        )
        # Simplified risk using only the two cheapest signals (no rolling state needed)
        risk_score = compute_risk_score(
            variance_ratio=variance_ratio,
            cusum_upper=0.0,            # no CUSUM state for historical rows
            baseline_delta_pct=baseline_delta,
            z_speed=0.0,
        )
        severity = score_to_severity(risk_score)

        if _SEV_RANK.get(severity, 0) < min_rank:
            continue

        items.append({
            "id":               row.id,
            "timestamp":        row.timestamp.isoformat(),
            "segment_id":       row.segment_id,
            "avg_speed_kmh":    round(row.avg_speed_kmh, 1),
            "speed_stddev":     round(row.speed_stddev, 1),
            "baseline_avg_speed": round(row.baseline_avg_speed, 1),
            "baseline_delta_pct": baseline_delta,
            "variance_ratio":   variance_ratio,
            "sample_count":     row.sample_count,
            "travel_time_seconds": round(row.travel_time_seconds, 1) if row.travel_time_seconds else None,
            "risk_score":       risk_score,
            "severity":         severity,
        })

        if len(items) >= limit:
            break

    return {"total": total_unfiltered, "items": items}


@app.post("/api/chat")
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    # Build enriched context via the 2-pass analytics pipeline:
    #   Pass 1 — per-segment scores (z-score, CUSUM, trend, forecast, risk)
    #   Pass 2 — propagation, which needs all Pass-1 scores to exist first
    llm_context = get_pipeline_context(
        db,
        active_scenario=_active_scenario,
        weather=_get_weather(),
    )
    try:
        response = call_gemini_api(request.message, request.history, llm_context)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
