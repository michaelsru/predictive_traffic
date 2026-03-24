import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Try loading from backend dir first, then from root dir
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env.local'))
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '../.env.local'))

from sqlalchemy.orm import Session
from database import get_db, engine, Base
from models import ChatRequest
from simulator import start_simulator, set_scenario
from analytics import get_latest_status, get_history, get_pipeline_context
from claude_client import call_claude_api
from gemini_client import call_gemini_api
app = FastAPI()

# Track active scenario so analytics context stays in sync
_active_scenario: str = "normal"

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

@app.get("/api/status")
def read_status(db: Session = Depends(get_db)):
    return get_latest_status(db)

@app.get("/api/history/{seg}")
def read_history(seg: str, db: Session = Depends(get_db)):
    if seg not in ["S1", "S2", "S3", "S4", "S5"]:
        raise HTTPException(status_code=404, detail="Segment not found")
    return get_history(db, seg)

@app.post("/api/scenario/{mode}")
def update_scenario(mode: str):
    global _active_scenario
    if mode not in ["normal", "forming", "incident"]:
        raise HTTPException(status_code=400, detail="Invalid mode")
    _active_scenario = mode
    set_scenario(mode)
    return {"status": "success", "mode": mode}

@app.post("/api/chat")
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    # Build enriched context via the 2-pass analytics pipeline:
    #   Pass 1 — per-segment scores (z-score, CUSUM, trend, forecast, risk)
    #   Pass 2 — propagation, which needs all Pass-1 scores to exist first
    llm_context = get_pipeline_context(db, active_scenario=_active_scenario)
    try:
        response = call_gemini_api(request.message, request.history, llm_context)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
