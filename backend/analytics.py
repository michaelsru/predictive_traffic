"""
analytics.py — Corridor Intelligence Analytics Pipeline

Transforms raw segment readings into pre-interpreted signals for the LLM.
The LLM never does math — it reads a structured instrument panel.

Pipeline stages:
  1. Z-score     — how anomalous is this reading vs rolling history?
  2. CUSUM       — is there sustained drift accumulating over time?
  3. Trend       — is the segment improving, stable, or deteriorating?
  4. Propagation — is congestion spreading upstream or downstream?
  5. Forecast    — where is speed heading in the next 5 minutes?
  6. Risk score  — single 0.0–1.0 composite score per segment
"""

def get_history(db, segment_id: str, limit: int = 30):
    from models import SegmentReading
    from sqlalchemy import desc
    readings = db.query(SegmentReading).filter(SegmentReading.segment_id == segment_id).order_by(desc(SegmentReading.timestamp)).limit(limit).all()
    return [
        {
            "timestamp": r.timestamp.isoformat(),
            "avg_speed_kmh": r.avg_speed_kmh,
            "speed_stddev": r.speed_stddev
        }
        for r in reversed(readings)
    ]


import math
from collections import deque
from dataclasses import dataclass, field
from typing import Literal

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Rolling window sizes
Z_SCORE_WINDOW = 20          # samples used to compute rolling mean/std
TREND_WINDOW = 6             # samples compared to determine trend direction
FORECAST_ALPHA = 0.25        # exponential smoothing factor (higher = more reactive)

# CUSUM sensitivity — lower k = more sensitive, higher h = fewer false alarms
CUSUM_K = 0.5                # allowance parameter (half the shift size to detect)
CUSUM_H = 4.0                # decision threshold (alarm when score exceeds this)

# Risk score weights — must sum to 1.0
RISK_WEIGHTS = {
    "variance_ratio":   0.25,
    "cusum_upper":      0.25,
    "baseline_delta":   0.35,
    "z_speed":          0.15,
}

# Severity thresholds on the 0.0–1.0 risk score
SEVERITY_THRESHOLDS = {
    "critical": 0.75,
    "warning":  0.50,
    "watch":    0.25,
    "normal":   0.0,
}

# Trend classification — pct change in avg_speed over TREND_WINDOW samples
TREND_DETERIORATING_PCT = -3.0   # speed dropped more than 3%
TREND_IMPROVING_PCT     =  3.0   # speed rose more than 3%

# Normal stddev for each segment under free-flow (interpolated across 20 sub-segments)
NORMAL_STDDEV = {
    "S1":  5.20, "S2":  5.35, "S3":  5.50, "S4":  5.65,   # old S1 zone
    "S5":  5.80, "S6":  5.73, "S7":  5.65, "S8":  5.58,   # old S2 zone
    "S9":  5.50, "S10": 5.65, "S11": 5.80, "S12": 5.95,  # old S3 zone
    "S13": 6.10, "S14": 5.83, "S15": 5.55, "S16": 5.28,  # old S4 zone
    "S17": 5.00, "S18": 5.00, "S19": 5.00, "S20": 5.00,  # old S5 zone
}


# ---------------------------------------------------------------------------
# Per-segment state (maintained in memory across readings)
# ---------------------------------------------------------------------------

@dataclass
class SegmentState:
    segment_id: str

    # Rolling history for z-score computation
    speed_history:  deque = field(default_factory=lambda: deque(maxlen=Z_SCORE_WINDOW))
    stddev_history: deque = field(default_factory=lambda: deque(maxlen=Z_SCORE_WINDOW))

    # CUSUM accumulators — track upper (speed drop) and lower (speed spike) drift
    cusum_upper: float = 0.0   # accumulates evidence of speed decreasing
    cusum_lower: float = 0.0   # accumulates evidence of speed increasing

    # Exponential smoothing state
    smoothed_speed: float | None = None

    # Recent readings for trend + forecast
    recent_speeds: deque = field(default_factory=lambda: deque(maxlen=30))


# Global state store — one entry per segment, persists across requests
_segment_states: dict[str, SegmentState] = {}


def _get_state(segment_id: str) -> SegmentState:
    if segment_id not in _segment_states:
        _segment_states[segment_id] = SegmentState(segment_id=segment_id)
    return _segment_states[segment_id]


def reset_state(segment_id: str | None = None) -> None:
    """Reset state for one or all segments (call on scenario switch)."""
    if segment_id:
        _segment_states.pop(segment_id, None)
    else:
        _segment_states.clear()


# ---------------------------------------------------------------------------
# Stage 1 — Z-score
# ---------------------------------------------------------------------------

def _rolling_mean_std(history: deque) -> tuple[float, float]:
    """Return (mean, std) of a deque. Returns (0, 1) if insufficient data."""
    n = len(history)
    if n < 3:
        return 0.0, 1.0
    mean = sum(history) / n
    variance = sum((x - mean) ** 2 for x in history) / (n - 1)
    return mean, math.sqrt(variance) if variance > 0 else 1.0


def compute_z_scores(
    state: SegmentState,
    avg_speed: float,
    speed_stddev: float,
) -> tuple[float, float]:
    """
    Compute z-scores for current speed and stddev vs rolling history.

    z_speed:  negative = slower than normal (bad)
    z_stddev: positive = more variance than normal (early warning signal)

    Returns (z_speed, z_stddev).
    """
    # Update histories with current reading
    state.speed_history.append(avg_speed)
    state.stddev_history.append(speed_stddev)

    mean_speed, std_speed   = _rolling_mean_std(state.speed_history)
    mean_stddev, std_stddev = _rolling_mean_std(state.stddev_history)

    z_speed  = (avg_speed    - mean_speed)  / std_speed   if std_speed  > 0 else 0.0
    z_stddev = (speed_stddev - mean_stddev) / std_stddev  if std_stddev > 0 else 0.0

    return round(z_speed, 3), round(z_stddev, 3)


# ---------------------------------------------------------------------------
# Stage 2 — CUSUM (Page's test, upper-sided for speed drops)
# ---------------------------------------------------------------------------

def compute_cusum(
    state: SegmentState,
    avg_speed: float,
    baseline_speed: float,
) -> tuple[float, float]:
    """
    CUSUM change-point detection on speed vs baseline.

    Detects sustained drift — catches a gradual queue forming that z-score
    might miss because each individual reading looks only slightly off.

    cusum_upper: evidence accumulating that speed is DROPPING (congestion forming)
    cusum_lower: evidence accumulating that speed is RISING (clearing)

    Both reset to 0 when they cross the threshold h (alarm fired, reset).
    Values are normalised by h so they read as 0.0–1.0+ fractions of threshold.

    Returns (cusum_upper_normalised, cusum_lower_normalised).
    """
    # Standardised deviation from baseline
    # k is the allowance — we only accumulate evidence beyond k std devs
    if baseline_speed > 0:
        deviation = (baseline_speed - avg_speed) / baseline_speed * 100  # pct below baseline
    else:
        deviation = 0.0

    # Upper CUSUM — accumulates when speed drops below baseline
    state.cusum_upper = max(0.0, state.cusum_upper + deviation - CUSUM_K)

    # Lower CUSUM — accumulates when speed rises above baseline (clearing)
    state.cusum_lower = max(0.0, state.cusum_lower - deviation - CUSUM_K)

    # Alarm + reset if threshold crossed — clamp rather than reset so
    # sustained incidents don't zero out the CUSUM contribution.
    if state.cusum_upper >= CUSUM_H:
        state.cusum_upper = CUSUM_H   # stay at ceiling, not reset
    if state.cusum_lower >= CUSUM_H:
        state.cusum_lower = CUSUM_H

    # Normalise to 0.0–1.0 fraction of threshold (>1.0 means alarm fired)
    cusum_upper_norm = round(min(state.cusum_upper / CUSUM_H, 1.5), 3)
    cusum_lower_norm = round(min(state.cusum_lower / CUSUM_H, 1.5), 3)

    return cusum_upper_norm, cusum_lower_norm


# ---------------------------------------------------------------------------
# Stage 3 — Trend classifier
# ---------------------------------------------------------------------------

Trend = Literal["improving", "stable", "deteriorating"]


def compute_trend(state: SegmentState, avg_speed: float) -> Trend:
    """
    Compare current speed to TREND_WINDOW samples ago.
    Returns a direction label for Claude to include in its narrative.
    """
    state.recent_speeds.append(avg_speed)

    if len(state.recent_speeds) < TREND_WINDOW:
        return "stable"

    speeds = list(state.recent_speeds)
    older_avg = sum(speeds[:TREND_WINDOW // 2]) / (TREND_WINDOW // 2)
    newer_avg = sum(speeds[-(TREND_WINDOW // 2):]) / (TREND_WINDOW // 2)

    if older_avg == 0:
        return "stable"

    pct_change = ((newer_avg - older_avg) / older_avg) * 100

    if pct_change <= TREND_DETERIORATING_PCT:
        return "deteriorating"
    elif pct_change >= TREND_IMPROVING_PCT:
        return "improving"
    else:
        return "stable"


# ---------------------------------------------------------------------------
# Stage 4 — Exponential smoothing forecast
# ---------------------------------------------------------------------------

def compute_forecast(state: SegmentState, avg_speed: float) -> float:
    """
    Single-step exponential smoothing — predicts next reading's speed.
    Acts as a 1-step ahead forecast: where is this segment heading?
    """
    if state.smoothed_speed is None:
        state.smoothed_speed = avg_speed
    else:
        state.smoothed_speed = (
            FORECAST_ALPHA * avg_speed
            + (1 - FORECAST_ALPHA) * state.smoothed_speed
        )
    return round(state.smoothed_speed, 1)


# ---------------------------------------------------------------------------
# Stage 5 — Composite risk score
# ---------------------------------------------------------------------------

def compute_risk_score(
    variance_ratio: float,
    cusum_upper: float,
    baseline_delta_pct: float,
    z_speed: float,
) -> float:
    """
    Weighted composite risk score in [0.0, 1.0].

    Each input is normalised to a 0–1 contribution before weighting.
    Designed so the weights can be replaced with XGBoost output later
    without changing anything upstream or downstream.
    """
    # Normalise variance_ratio: 1.0 = normal, 4.0+ = very anomalous
    norm_variance = min(max((variance_ratio - 1.0) / 3.0, 0.0), 1.0)

    # CUSUM upper is already 0.0–1.0+ normalised
    norm_cusum = min(cusum_upper, 1.0)

    # baseline_delta_pct: 0% = fine, -30% = severe
    norm_baseline = min(max(-baseline_delta_pct / 30.0, 0.0), 1.0)

    # z_speed: negative = slow. -3 std devs = fully anomalous
    norm_z_speed = min(max(-z_speed / 3.0, 0.0), 1.0)

    score = (
        norm_variance  * RISK_WEIGHTS["variance_ratio"] +
        norm_cusum     * RISK_WEIGHTS["cusum_upper"]    +
        norm_baseline  * RISK_WEIGHTS["baseline_delta"] +
        norm_z_speed   * RISK_WEIGHTS["z_speed"]
    )

    return round(min(score, 1.0), 3)


def score_to_severity(risk_score: float, avg_speed_kmh: float | None = None, baseline_speed: float = 100.0) -> str:
    # Absolute speed floor: severe slowdowns override the composite score.
    # Prevents sustained incidents from appearing mild once CUSUM/z-score
    # adapt to the new normal.
    if avg_speed_kmh is not None and baseline_speed > 0:
        speed_ratio = avg_speed_kmh / baseline_speed
        if speed_ratio < 0.35:    # >65% below baseline → always critical
            return "critical"
        elif speed_ratio < 0.55:  # >45% below baseline → at least warning
            if risk_score < SEVERITY_THRESHOLDS["warning"]:
                return "warning"

    if risk_score >= SEVERITY_THRESHOLDS["critical"]:
        return "critical"
    elif risk_score >= SEVERITY_THRESHOLDS["warning"]:
        return "warning"
    elif risk_score >= SEVERITY_THRESHOLDS["watch"]:
        return "watch"
    return "normal"


def severity_to_color(severity: str) -> str:
    return {
        "critical": "red",
        "warning":  "amber",
        "watch":    "yellow",
        "normal":   "green",
    }.get(severity, "green")


# ---------------------------------------------------------------------------
# Stage 6 — Propagation detector
# ---------------------------------------------------------------------------

def compute_propagation(
    segment_id: str,
    all_risk_scores: dict[str, float],
    segment_order: list[str],
) -> dict:
    """
    Compare this segment's risk to its neighbours.
    Detects whether congestion is spreading upstream (the dangerous case)
    or clearing downstream.

    Returns a dict with upstream_risk, downstream_risk, propagation_direction.
    """
    try:
        idx = segment_order.index(segment_id)
    except ValueError:
        return {"upstream_risk": 0.0, "downstream_risk": 0.0, "propagation": "none"}

    upstream_id   = segment_order[idx - 1] if idx > 0 else None
    downstream_id = segment_order[idx + 1] if idx < len(segment_order) - 1 else None

    upstream_risk   = all_risk_scores.get(upstream_id, 0.0)   if upstream_id   else 0.0
    downstream_risk = all_risk_scores.get(downstream_id, 0.0) if downstream_id else 0.0
    own_risk        = all_risk_scores.get(segment_id, 0.0)

    # Determine propagation direction
    if own_risk > 0.4 and upstream_risk > 0.25 and upstream_risk < own_risk:
        direction = "spreading_upstream"
    elif own_risk > 0.4 and downstream_risk > 0.25 and downstream_risk < own_risk:
        direction = "spreading_downstream"
    elif own_risk < 0.2 and (upstream_risk > 0.4 or downstream_risk > 0.4):
        direction = "clearing"
    else:
        direction = "none"

    return {
        "upstream_risk":   round(upstream_risk, 3),
        "downstream_risk": round(downstream_risk, 3),
        "propagation":     direction,
    }


# ---------------------------------------------------------------------------
# Main entry point — run full pipeline for all segments
# ---------------------------------------------------------------------------

def run_pipeline(raw_readings: list[dict], segment_order: list[str]) -> list[dict]:
    """
    Takes raw segment readings from the DB and returns enriched analytics
    objects ready to be serialised into the Claude context payload.

    Each raw reading must contain:
        segment_id, avg_speed_kmh, speed_stddev, baseline_avg_speed,
        variance_ratio, baseline_delta_pct

    Returns a list of enriched dicts in segment_order sequence.
    """
    # Index readings by segment for easy lookup
    readings_by_seg = {r["segment_id"]: r for r in raw_readings}

    # --- Pass 1: compute per-segment scores ---
    partial_results = {}
    for seg_id in segment_order:
        reading = readings_by_seg.get(seg_id)
        if not reading:
            continue

        state = _get_state(seg_id)

        avg_speed      = reading["avg_speed_kmh"]
        speed_stddev   = reading["speed_stddev"]
        baseline_speed = reading["baseline_avg_speed"]
        variance_ratio = reading["variance_ratio"]
        baseline_delta = reading["baseline_delta_pct"]

        z_speed, z_stddev         = compute_z_scores(state, avg_speed, speed_stddev)
        cusum_upper, cusum_lower  = compute_cusum(state, avg_speed, baseline_speed)
        trend                     = compute_trend(state, avg_speed)
        forecast_speed            = compute_forecast(state, avg_speed)
        risk_score                = compute_risk_score(
                                        variance_ratio, cusum_upper,
                                        baseline_delta, z_speed
                                    )
        severity                  = score_to_severity(risk_score, avg_speed, baseline_speed)

        partial_results[seg_id] = {
            "segment_id":        seg_id,
            "avg_speed_kmh":     round(avg_speed, 1),
            "speed_stddev":      round(speed_stddev, 1),
            "baseline_avg_speed": round(baseline_speed, 1),
            "baseline_delta_pct": baseline_delta,
            "variance_ratio":    variance_ratio,
            "z_speed":           z_speed,
            "z_stddev":          z_stddev,
            "cusum_upper":       cusum_upper,
            "cusum_lower":       cusum_lower,
            "trend":             trend,
            "forecast_speed_kmh": forecast_speed,
            "risk_score":        risk_score,
            "severity":          severity,
            "color":             severity_to_color(severity),
            "sample_count":      reading.get("sample_count", 0),
        }

    # --- Pass 2: propagation (needs all risk scores computed first) ---
    all_risks = {seg: r["risk_score"] for seg, r in partial_results.items()}

    enriched = []
    for seg_id in segment_order:
        if seg_id not in partial_results:
            continue
        result = partial_results[seg_id]
        propagation = compute_propagation(seg_id, all_risks, segment_order)
        result.update(propagation)
        enriched.append(result)

    return enriched


# ---------------------------------------------------------------------------
# Context formatter — produces the final payload for Gemini
# ---------------------------------------------------------------------------

def format_llm_context(
    enriched_segments: list[dict],
    active_scenario: str,
    weather: str = "clear",
    active_events: list[str] | None = None,
) -> dict:
    """Packages enriched analytics into the structured context object injected into the system prompt."""
    return {
        "corridor": "Highway 401 Westbound — Weston Rd to Allen Rd",
        "scenario": active_scenario,
        "segments": enriched_segments,
        "context": {
            "weather":       weather,
            "active_events": active_events or [],
        },
        "signal_guide": {
            "variance_ratio":  "1.0 = normal stddev. >2.5 = early warning. >3.5 = forming incident.",
            "cusum_upper":     "0.0–1.0 fraction of alarm threshold. >0.7 = sustained speed drop.",
            "z_speed":         "Negative = slower than rolling avg. < -2.0 = statistically anomalous.",
            "risk_score":      "0.0–1.0 composite. >0.5 = operator attention needed. >0.75 = critical.",
            "trend":           "Direction of speed over last 6 readings.",
            "propagation":     "spreading_upstream = congestion moving backward — most dangerous pattern.",
        }
    }


# ---------------------------------------------------------------------------
# DB bridge — fetch → pipeline (2 passes) → LLM context in one call
# ---------------------------------------------------------------------------

SEGMENT_ORDER = [f"S{i}" for i in range(1, 21)]


def get_pipeline_context(
    db,                          # sqlalchemy Session
    active_scenario: str = "unknown",
    weather: str = "clear",
    active_events: list[str] | None = None,
) -> dict:
    """
    End-to-end bridge:
      1. Fetch the latest SegmentReading per segment from the DB.
      2. Map DB rows → raw_reading dicts that run_pipeline expects.
      3. Run the 2-pass pipeline (Pass 1: per-segment scores;
         Pass 2: neighbour-aware propagation).
      4. Return format_llm_context() payload ready for the LLM system prompt.

    Pass 1 gives every segment a score.
    Pass 2 gives every segment awareness of its neighbours.
    You can't do both in one pass because when scoring S2, S3's score
    doesn't exist yet — and propagation needs S3's score to determine
    whether S2 is upstream of a problem.
    """
    from models import SegmentReading          # local import avoids circular dep
    from sqlalchemy import desc as _desc

    raw_readings: list[dict] = []
    for seg_id in SEGMENT_ORDER:
        row = (
            db.query(SegmentReading)
            .filter(SegmentReading.segment_id == seg_id)
            .order_by(_desc(SegmentReading.timestamp))
            .first()
        )
        if row is None:
            continue

        # Compute derived fields the pipeline expects
        baseline_delta_pct = (
            ((row.avg_speed_kmh - row.baseline_avg_speed) / row.baseline_avg_speed) * 100
            if row.baseline_avg_speed > 0 else 0.0
        )
        normal_stddev = NORMAL_STDDEV.get(seg_id, 5.5)
        variance_ratio = round(row.speed_stddev / normal_stddev, 2) if normal_stddev > 0 else 1.0

        raw_readings.append({
            "segment_id":         row.segment_id,
            "avg_speed_kmh":      row.avg_speed_kmh,
            "speed_stddev":       row.speed_stddev,
            "baseline_avg_speed": row.baseline_avg_speed,
            "baseline_delta_pct": round(baseline_delta_pct, 1),
            "variance_ratio":     variance_ratio,
            "sample_count":       row.sample_count,
            "travel_time_seconds": row.travel_time_seconds,
        })

    # Pass 1 + Pass 2 — see run_pipeline docstring
    enriched = run_pipeline(raw_readings, SEGMENT_ORDER)

    return format_llm_context(enriched, active_scenario, weather, active_events)