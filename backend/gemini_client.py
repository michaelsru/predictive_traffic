import os
import json
import logging
from google import genai
from google.genai import types

logger = logging.getLogger("gemini_client")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s [gemini_client] %(levelname)s %(message)s"))
    logger.addHandler(_h)
logger.setLevel(logging.DEBUG)


# ---------------------------------------------------------------------------
# 11 UI command types the agent can emit per step
# ---------------------------------------------------------------------------
UI_COMMAND_SCHEMA = """
UI command types (one object per step — only ONE command per step):
  { "type": "focusSegment", "segmentId": "S9", "lat": float, "lng": float, "label": "S9 — 28 km/h", "color": "red"|"amber"|"yellow"|"green", "durationMs": 4000, "pulseDurationMs": 2000 }
    ↳ Compound: flies map to segment, expands its alert card, pulses it with color, and drops a label annotation.
      Use this whenever you are DISCUSSING a specific segment. lat/lng from anchor coordinates.
      label should be a short fact (speed, severity, risk%) — max 20 chars.
      color matches severity: red=critical, amber=warning, yellow=watch, green=normal.
  { "type": "pulseSegment",  "segmentId": "...", "color": "...", "durationMs": 2000 }  ← standalone only, do NOT pair with focusSegment
  { "type": "clearHighlights" }
  { "type": "switchChart",   "segmentId": "..." }
  { "type": "switchMetric",  "metric": "speed"|"volume"|"risk" }
  { "type": "setTimeWindow", "minutes": 5|15|30|60 }
  { "type": "pulseKpi",      "kpi": "avgSpeed"|"worstSegment"|"activeAlerts", "durationMs": 1500 }
  { "type": "switchOverlay", "overlay": "risk"|"speed"|"volume" }
  { "type": "panTo",         "segmentId": "..." }  ← use only when NOT discussing a segment directly
  { "type": "annotate",      "lat": float, "lng": float, "text": "...", "durationMs": 4000 }  ← standalone annotation only
  { "type": "expandAlert",   "segmentId": "..." }  ← use only to expand without flying to

Rules:
- narrative[] and uiCommands[] MUST have the same length (one command per step).
- Every step MUST have a meaningful UI action from the list above.
- STEP COUNT is determined by corridor conditions, not query type (see Response length below).
- When narrating about a specific segment, ALWAYS prefer focusSegment over panTo alone.
"""

SEGMENT_LOCATIONS = {
    "S1":  {"lat": 43.7078, "lng": -79.5553},
    "S2":  {"lat": 43.7089, "lng": -79.5537},
    "S3":  {"lat": 43.7097, "lng": -79.5515},
    "S4":  {"lat": 43.7128, "lng": -79.5386},
    "S5":  {"lat": 43.7149, "lng": -79.5298},
    "S6":  {"lat": 43.7157, "lng": -79.5264},
    "S7":  {"lat": 43.7165, "lng": -79.5193},
    "S8":  {"lat": 43.7178, "lng": -79.5080},
    "S9":  {"lat": 43.7184, "lng": -79.5024},
    "S10": {"lat": 43.7197, "lng": -79.4943},
    "S11": {"lat": 43.7207, "lng": -79.4897},
    "S12": {"lat": 43.7230, "lng": -79.4803},
    "S13": {"lat": 43.7248, "lng": -79.4728},
    "S14": {"lat": 43.7271, "lng": -79.4624},
    "S15": {"lat": 43.7284, "lng": -79.4565},
    "S16": {"lat": 43.7307, "lng": -79.4457},
    "S17": {"lat": 43.7313, "lng": -79.4432},
    "S18": {"lat": 43.7319, "lng": -79.4412},
    "S19": {"lat": 43.7326, "lng": -79.4399},
    "S20": {"lat": 43.7332, "lng": -79.4387},
}

QUERY_INTENTS = """
Response length — ALWAYS evaluate corridor conditions first:

NOMINAL (all segments have severity="normal" AND risk_score < 0.25):
  → 1 step only. focusSegment on the highest-risk segment. Narrative: single sentence stating
    corridor is clear, corridor-wide avg speed (km/h), and speed std dev range. Nothing more.

NON-NOMINAL (any segment has severity != "normal" OR risk_score >= 0.25):
  → Focus ONLY on segments with severity != "normal", ordered by risk_score descending.
  → 1 step per affected segment using focusSegment (include color matching severity).
  → State: current speed vs baseline, risk_score, severity, trend, and any propagation direction.
  → Skip all segments with severity="normal" entirely — do not mention them unless asked.

Query-specific additions (apply on top of the above):
- Risk explanation: also switchMetric to risk before the segment steps.
- Timeline walk: also setTimeWindow before narrating changes.
- "What to watch": identify fastest-rising risk_score or deteriorating trend; narrate shockwave risk.
- Alert triage: process non-normal segments in strict risk_score descending order.
"""


def call_gemini_api(message: str, history: list, status_data: dict):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")

    client = genai.Client(api_key=api_key)

    system_prompt = f"""You are an expert TMC (Traffic Management Center) operator assistant for Highway 401 westbound in Toronto.
You are NOT a chatbot. You are a co-pilot that reads live traffic data and drives the dashboard while you talk.

LIVE CORRIDOR DATA (assembled at query time — use ONLY these numbers in your narrative):
{json.dumps(status_data, indent=2)}

Segment anchor coordinates:
{json.dumps(SEGMENT_LOCATIONS, indent=2)}

{QUERY_INTENTS}

{UI_COMMAND_SCHEMA}

CRITICAL RULES:
1. Never invent numbers. Every speed, risk score, volume, z-score, or time reference MUST come from the live data above.
2. If a UI command references a segment that doesn't exist, use clearHighlights and narrate the gap.
3. narrative[] and uiCommands[] must always have EXACTLY the same length.
4. Return ONLY the raw JSON object below — no markdown, no preamble.

Response schema (strict):
{{
  "narrative": ["step 0 text", "step 1 text", ...],
  "uiCommands": [
    {{ "type": "...", ... }},
    ...
  ]
}}
"""

    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})

    contents.append({"role": "user", "parts": [{"text": message}]})

    logger.debug("=== GEMINI IN ===")
    logger.debug("USER MESSAGE: %s", message)
    logger.debug("HISTORY TURNS: %d", len(history))
    logger.debug("SYSTEM PROMPT (trimmed):\n%s", system_prompt[:2000])

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )

    response_text = response.text.strip()
    logger.debug("=== GEMINI OUT (raw) ===\n%s", response_text[:4000])

    # Strip accidental markdown fences
    if response_text.startswith("```json"):
        response_text = response_text[7:]
    if response_text.startswith("```"):
        response_text = response_text[3:]
    if response_text.endswith("```"):
        response_text = response_text[:-3]

    parsed = json.loads(response_text.strip())

    # Validate and repair: ensure both arrays have the same length
    narratives = parsed.get("narrative", [])
    commands = parsed.get("uiCommands", [])
    length = max(len(narratives), len(commands))

    while len(narratives) < length:
        narratives.append("")
    while len(commands) < length:
        commands.append({"type": "clearHighlights"})

    result = {"narrative": narratives, "uiCommands": commands}
    logger.debug("=== GEMINI PARSED === steps=%d", len(narratives))
    for i, (n, c) in enumerate(zip(narratives, commands)):
        logger.debug("  [%d] cmd=%-18s  %s", i, c.get("type", "?"), n[:80])
    return result
