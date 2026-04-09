"""
tools.py — DB query functions exposed to Gemini as callable tools.

Each function takes `db` as first arg + typed kwargs from the LLM,
returns a JSON-serialisable dict. No analytics state touched here.
"""

from datetime import datetime, timedelta
from sqlalchemy import desc

from models import SegmentReading, IncidentLog
from analytics import NORMAL_STDDEV, compute_risk_score

SEGMENT_ORDER = [f"S{i}" for i in range(1, 21)]


# ---------------------------------------------------------------------------
# Tool 1 — Single-segment timeseries
# ---------------------------------------------------------------------------

def get_segment_history(db, segment_id: str, limit: int = 30) -> dict:
    """Return the last `limit` readings for one segment, oldest first."""
    rows = (
        db.query(SegmentReading)
        .filter(SegmentReading.segment_id == segment_id)
        .order_by(desc(SegmentReading.timestamp))
        .limit(min(limit, 120))
        .all()
    )
    readings = [
        {
            "timestamp":        r.timestamp.isoformat(),
            "avg_speed_kmh":    round(r.avg_speed_kmh,    1),
            "speed_stddev":     round(r.speed_stddev,     1),
            "baseline_avg_speed": round(r.baseline_avg_speed, 1),
        }
        for r in reversed(rows)
    ]
    return {
        "segment_id":    segment_id,
        "reading_count": len(readings),
        "readings":      readings,
    }


# ---------------------------------------------------------------------------
# Tool 2 — Multi-segment side-by-side comparison
# ---------------------------------------------------------------------------

def get_multi_segment_history(db, segment_ids: list, limit: int = 20) -> dict:
    """
    Return last `limit` readings for each segment in `segment_ids`.
    Use when comparing onset times across segments to trace propagation.
    """
    result = {}
    for seg_id in segment_ids:
        rows = (
            db.query(SegmentReading)
            .filter(SegmentReading.segment_id == seg_id)
            .order_by(desc(SegmentReading.timestamp))
            .limit(min(limit, 60))
            .all()
        )
        result[seg_id] = [
            {
                "timestamp":     r.timestamp.isoformat(),
                "avg_speed_kmh": round(r.avg_speed_kmh, 1),
                "speed_stddev":  round(r.speed_stddev,  1),
            }
            for r in reversed(rows)
        ]
    return {"segments": result}


# ---------------------------------------------------------------------------
# Tool 3 — Speed threshold crossing detector
# ---------------------------------------------------------------------------

def get_speed_threshold_crossings(
    db, segment_id: str, threshold_kmh: float, since_mins: int = 60
) -> dict:
    """
    Find every moment speed crossed `threshold_kmh` in the last `since_mins` minutes.
    Reports 'dropped_below' and 'recovered_above' events with timestamps.
    Use to answer: "when exactly did congestion start on S9?"
    """
    since = datetime.utcnow() - timedelta(minutes=since_mins)
    rows = (
        db.query(SegmentReading)
        .filter(
            SegmentReading.segment_id == segment_id,
            SegmentReading.timestamp >= since,
        )
        .order_by(SegmentReading.timestamp)
        .all()
    )

    crossings = []
    prev_above = True
    for r in rows:
        is_above = r.avg_speed_kmh >= threshold_kmh
        if prev_above and not is_above:
            crossings.append({
                "event":             "dropped_below",
                "timestamp":         r.timestamp.isoformat(),
                "speed_at_crossing": round(r.avg_speed_kmh, 1),
            })
        elif not prev_above and is_above:
            crossings.append({
                "event":             "recovered_above",
                "timestamp":         r.timestamp.isoformat(),
                "speed_at_crossing": round(r.avg_speed_kmh, 1),
            })
        prev_above = is_above

    currently_below = bool(rows) and rows[-1].avg_speed_kmh < threshold_kmh
    return {
        "segment_id":             segment_id,
        "threshold_kmh":          threshold_kmh,
        "since_mins":             since_mins,
        "crossings":              crossings,
        "currently_below":        currently_below,
        "readings_checked":       len(rows),
    }


# ---------------------------------------------------------------------------
# Tool 4 — Peak conditions in a time window
# ---------------------------------------------------------------------------

def get_peak_conditions(db, segment_id: str, since_mins: int = 30) -> dict:
    """
    Return the worst (min speed) and best (max speed) readings in the last
    `since_mins` minutes. Answers: "how bad did it get on S9?"
    """
    since = datetime.utcnow() - timedelta(minutes=since_mins)
    rows = (
        db.query(SegmentReading)
        .filter(
            SegmentReading.segment_id == segment_id,
            SegmentReading.timestamp >= since,
        )
        .order_by(SegmentReading.timestamp)
        .all()
    )
    if not rows:
        return {"segment_id": segment_id, "since_mins": since_mins, "no_data": True}

    worst = min(rows, key=lambda r: r.avg_speed_kmh)
    best  = max(rows, key=lambda r: r.avg_speed_kmh)
    speeds = [r.avg_speed_kmh for r in rows]
    avg    = sum(speeds) / len(speeds)

    return {
        "segment_id":       segment_id,
        "since_mins":       since_mins,
        "reading_count":    len(rows),
        "worst": {
            "timestamp":     worst.timestamp.isoformat(),
            "avg_speed_kmh": round(worst.avg_speed_kmh, 1),
            "speed_stddev":  round(worst.speed_stddev,  1),
        },
        "best": {
            "timestamp":     best.timestamp.isoformat(),
            "avg_speed_kmh": round(best.avg_speed_kmh,  1),
        },
        "average_speed_kmh":  round(avg, 1),
        "baseline_avg_speed": round(rows[0].baseline_avg_speed, 1),
    }


# ---------------------------------------------------------------------------
# Tool 5 — Corridor snapshot at a past time
# ---------------------------------------------------------------------------

def get_corridor_snapshot(db, time_offset_mins: int = 15) -> dict:
    """
    Return one reading per segment closest to `time_offset_mins` ago.
    Answers: "what did the corridor look like 15 minutes ago?"
    """
    target_time = datetime.utcnow() - timedelta(minutes=time_offset_mins)
    snapshot = {}
    for seg_id in SEGMENT_ORDER:
        row = (
            db.query(SegmentReading)
            .filter(
                SegmentReading.segment_id == seg_id,
                SegmentReading.timestamp <= target_time,
            )
            .order_by(desc(SegmentReading.timestamp))
            .first()
        )
        if row:
            snapshot[seg_id] = {
                "timestamp":          row.timestamp.isoformat(),
                "avg_speed_kmh":      round(row.avg_speed_kmh,      1),
                "speed_stddev":       round(row.speed_stddev,       1),
                "baseline_avg_speed": round(row.baseline_avg_speed, 1),
            }
    return {
        "approximate_time":  target_time.isoformat(),
        "time_offset_mins":  time_offset_mins,
        "segments":          snapshot,
    }


# ---------------------------------------------------------------------------
# Tool 6 — Confirmed incidents log
# ---------------------------------------------------------------------------

def get_incidents(db, segment_id: str = None, limit: int = 20) -> dict:
    """
    Return operator-confirmed incidents, optionally filtered by segment.
    Answers: "have any incidents been reported on S9?"
    """
    q = db.query(IncidentLog)
    if segment_id:
        q = q.filter(IncidentLog.segment_id == segment_id)
    rows = q.order_by(desc(IncidentLog.created_at)).limit(min(limit, 100)).all()
    return {
        "count": len(rows),
        "incidents": [
            {
                "id":            r.id,
                "created_at":    r.created_at.isoformat(),
                "segment_id":    r.segment_id,
                "severity":      r.severity,
                "risk_score":    r.risk_score,
                "avg_speed_kmh": r.avg_speed_kmh,
                "notes":         r.notes,
                "confirmed_by":  r.confirmed_by,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Tool 7 — Propagation window (anchor + neighbours)
# ---------------------------------------------------------------------------

def get_propagation_window(
    db,
    anchor_segment_id: str,
    upstream_count: int   = 3,
    downstream_count: int = 3,
    limit_per_segment: int = 20,
) -> dict:
    """
    Return recent history for the anchor segment plus N upstream and N downstream
    neighbours. Compares timestamps to show how congestion spread in time.
    Answers: "how did congestion on S9 propagate?"
    """
    try:
        idx = SEGMENT_ORDER.index(anchor_segment_id)
    except ValueError:
        return {"error": f"Unknown segment: {anchor_segment_id}"}

    upstream_ids   = SEGMENT_ORDER[max(0, idx - upstream_count):idx]
    downstream_ids = SEGMENT_ORDER[idx + 1: idx + 1 + downstream_count]
    all_ids        = upstream_ids + [anchor_segment_id] + downstream_ids

    segments = {}
    for seg_id in all_ids:
        rows = (
            db.query(SegmentReading)
            .filter(SegmentReading.segment_id == seg_id)
            .order_by(desc(SegmentReading.timestamp))
            .limit(min(limit_per_segment, 60))
            .all()
        )
        segments[seg_id] = [
            {
                "timestamp":     r.timestamp.isoformat(),
                "avg_speed_kmh": round(r.avg_speed_kmh, 1),
                "speed_stddev":  round(r.speed_stddev,  1),
            }
            for r in reversed(rows)
        ]

    return {
        "anchor":               anchor_segment_id,
        "upstream_segments":    upstream_ids,
        "downstream_segments":  downstream_ids,
        "segments":             segments,
    }


# ---------------------------------------------------------------------------
# Tool 8 — Risk score trend over time
# ---------------------------------------------------------------------------

def get_segment_risk_trend(db, segment_id: str, since_mins: int = 30) -> dict:
    """
    Compute risk score for each reading in the last `since_mins` minutes and
    determine if the trend is rising, stable, or falling.
    Answers: "is S9 getting worse or stabilising?"
    Note: CUSUM/z-score not available here (no pipeline state), so risk scores
    are conservative — directional accuracy is reliable, magnitudes are not.
    """
    since = datetime.utcnow() - timedelta(minutes=since_mins)
    rows  = (
        db.query(SegmentReading)
        .filter(
            SegmentReading.segment_id == segment_id,
            SegmentReading.timestamp >= since,
        )
        .order_by(SegmentReading.timestamp)
        .all()
    )
    if not rows:
        return {"segment_id": segment_id, "since_mins": since_mins, "no_data": True}

    normal_stddev = NORMAL_STDDEV.get(segment_id, 5.5)
    data_points   = []
    for r in rows:
        variance_ratio = round(r.speed_stddev / normal_stddev, 2) if normal_stddev > 0 else 1.0
        baseline_delta = (
            ((r.avg_speed_kmh - r.baseline_avg_speed) / r.baseline_avg_speed) * 100
            if r.baseline_avg_speed > 0 else 0.0
        )
        risk = compute_risk_score(
            variance_ratio=variance_ratio,
            cusum_upper=0.0,
            baseline_delta_pct=round(baseline_delta, 1),
            z_speed=0.0,
        )
        data_points.append({
            "timestamp":     r.timestamp.isoformat(),
            "avg_speed_kmh": round(r.avg_speed_kmh, 1),
            "risk_score":    risk,
        })

    half = len(data_points) // 2
    if half > 0:
        first_avg  = sum(p["risk_score"] for p in data_points[:half])  / half
        second_avg = sum(p["risk_score"] for p in data_points[half:])  / (len(data_points) - half)
        delta      = second_avg - first_avg
        direction  = "rising" if delta > 0.05 else "falling" if delta < -0.05 else "stable"
    else:
        direction, delta = "stable", 0.0

    return {
        "segment_id":       segment_id,
        "since_mins":       since_mins,
        "trend_direction":  direction,
        "risk_delta":       round(delta, 3),
        "data_points":      data_points,
    }


# ---------------------------------------------------------------------------
# Dispatcher — called by gemini_client with (name, args, db)
# ---------------------------------------------------------------------------

_TOOL_FNS = {
    "get_segment_history":          get_segment_history,
    "get_multi_segment_history":    get_multi_segment_history,
    "get_speed_threshold_crossings": get_speed_threshold_crossings,
    "get_peak_conditions":          get_peak_conditions,
    "get_corridor_snapshot":        get_corridor_snapshot,
    "get_incidents":                get_incidents,
    "get_propagation_window":       get_propagation_window,
    "get_segment_risk_trend":       get_segment_risk_trend,
}


def execute_tool(name: str, args: dict, db) -> dict:
    fn = _TOOL_FNS.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(db, **args)
    except Exception as exc:
        return {"error": str(exc), "tool": name, "args": args}
