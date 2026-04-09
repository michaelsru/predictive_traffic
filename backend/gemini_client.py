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

# Max tool-call rounds before aborting (prevents infinite loops)
_MAX_TOOL_ROUNDS = 5

# ---------------------------------------------------------------------------
# Tool declarations — mirrors tools.py signatures exactly
# ---------------------------------------------------------------------------

_TOOL_DECLARATIONS = [
    types.FunctionDeclaration(
        name="get_segment_history",
        description=(
            "Return the last N readings for one segment (oldest→newest). "
            "Use when the user asks how long congestion has been going on, "
            "or wants a time-series view of a single segment."
        ),
        parameters={
            "type": "object",
            "properties": {
                "segment_id": {"type": "string", "description": "e.g. 'S9'"},
                "limit":      {"type": "integer", "description": "Number of readings to return (max 120, default 30)"},
            },
            "required": ["segment_id"],
        },
    ),
    types.FunctionDeclaration(
        name="get_multi_segment_history",
        description=(
            "Return recent readings for multiple segments side-by-side. "
            "Use to compare onset timestamps and trace how congestion propagated "
            "from segment to segment."
        ),
        parameters={
            "type": "object",
            "properties": {
                "segment_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of segment IDs, e.g. ['S7', 'S8', 'S9', 'S10']",
                },
                "limit": {"type": "integer", "description": "Readings per segment (max 60, default 20)"},
            },
            "required": ["segment_ids"],
        },
    ),
    types.FunctionDeclaration(
        name="get_speed_threshold_crossings",
        description=(
            "Find every moment speed crossed a given threshold in the last N minutes. "
            "Returns 'dropped_below' and 'recovered_above' events with exact timestamps. "
            "Use when the user asks 'when exactly did S9 slow down?' or 'how long has S9 been below 50 km/h?'"
        ),
        parameters={
            "type": "object",
            "properties": {
                "segment_id":    {"type": "string"},
                "threshold_kmh": {"type": "number", "description": "Speed threshold in km/h, e.g. 50.0"},
                "since_mins":    {"type": "integer", "description": "Look-back window in minutes (default 60)"},
            },
            "required": ["segment_id", "threshold_kmh"],
        },
    ),
    types.FunctionDeclaration(
        name="get_peak_conditions",
        description=(
            "Return the worst (min speed) and best (max speed) readings for a segment "
            "in the last N minutes. Use for 'how bad did it get?' questions."
        ),
        parameters={
            "type": "object",
            "properties": {
                "segment_id": {"type": "string"},
                "since_mins": {"type": "integer", "description": "Look-back window in minutes (default 30)"},
            },
            "required": ["segment_id"],
        },
    ),
    types.FunctionDeclaration(
        name="get_corridor_snapshot",
        description=(
            "Return one reading per segment from approximately N minutes ago. "
            "Use when the user asks 'what did the corridor look like 15 minutes ago?' "
            "or wants to compare current vs past state."
        ),
        parameters={
            "type": "object",
            "properties": {
                "time_offset_mins": {"type": "integer", "description": "How many minutes ago to snapshot (default 15)"},
            },
            "required": ["time_offset_mins"],
        },
    ),
    types.FunctionDeclaration(
        name="get_incidents",
        description=(
            "Return operator-confirmed incidents from the log, optionally filtered by segment. "
            "Use when the user asks 'have any incidents been confirmed?' or 'show me logged incidents on S9'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "segment_id": {"type": "string", "description": "Filter to a specific segment (omit for all segments)"},
                "limit":      {"type": "integer", "description": "Max incidents to return (default 20)"},
            },
            "required": [],
        },
    ),
    types.FunctionDeclaration(
        name="get_propagation_window",
        description=(
            "Return recent history for an anchor segment plus its upstream and downstream neighbours. "
            "Comparing timestamps across neighbours reveals how congestion spread. "
            "Use for 'how did the congestion propagate from S9?' questions."
        ),
        parameters={
            "type": "object",
            "properties": {
                "anchor_segment_id": {"type": "string", "description": "The segment at the centre of the analysis"},
                "upstream_count":    {"type": "integer", "description": "How many upstream segments to include (default 3)"},
                "downstream_count":  {"type": "integer", "description": "How many downstream segments to include (default 3)"},
                "limit_per_segment": {"type": "integer", "description": "Readings per segment (default 20)"},
            },
            "required": ["anchor_segment_id"],
        },
    ),
    types.FunctionDeclaration(
        name="get_segment_risk_trend",
        description=(
            "Compute risk score over time for a segment and return trend direction "
            "('rising', 'stable', 'falling') with data points. "
            "Use for 'is S9 getting worse or stabilising?' questions."
        ),
        parameters={
            "type": "object",
            "properties": {
                "segment_id": {"type": "string"},
                "since_mins": {"type": "integer", "description": "Look-back window in minutes (default 30)"},
            },
            "required": ["segment_id"],
        },
    ),
    types.FunctionDeclaration(
        name="get_alert_history",
        description=(
            "Return severity-transition events from the alert log (normal→watch, watch→critical, etc.) "
            "for one or all segments. Each event shows FROM/TO severity with timestamp and speed. "
            "Use for 'has S9 been flapping?', 'when did S9 first go critical?', "
            "'how often has S9 triggered alerts in the last hour?' questions."
        ),
        parameters={
            "type": "object",
            "properties": {
                "segment_id": {"type": "string", "description": "Filter to a specific segment (omit for all segments)"},
                "since_mins": {"type": "integer", "description": "Look-back window in minutes (default 60)"},
                "limit":      {"type": "integer", "description": "Max events to return (default 50)"},
            },
            "required": [],
        },
    ),
    types.FunctionDeclaration(
        name="get_corridor_handover_summary",
        description=(
            "Pre-aggregated corridor-wide alert digest. Returns per-segment summaries of active alerts "
            "(currently non-normal) and resolved alerts (cleared in the window), plus confirmed incident "
            "counts. Designed for operator handover, shift summaries, and 'what happened in the last hour?' "
            "questions. ONE call gives a complete picture — no pagination needed."
        ),
        parameters={
            "type": "object",
            "properties": {
                "since_mins": {"type": "integer", "description": "Look-back window in minutes (default 60)"},
            },
            "required": [],
        },
    ),
]

_TOOLS = types.Tool(function_declarations=_TOOL_DECLARATIONS)


# ---------------------------------------------------------------------------
# UI command schema (unchanged)
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
- Historical/duration questions: call the relevant tool(s) first, then incorporate findings into narrative.
"""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def call_gemini_api(message: str, history: list, status_data: dict, db=None):
    import datetime as _dt
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")

    client = genai.Client(api_key=api_key)

    # Compute server local UTC offset for the LLM to display local times
    now_local  = _dt.datetime.now(_dt.timezone.utc).astimezone()
    utc_offset = now_local.strftime("%z")          # e.g. "-0700"
    tz_name    = now_local.strftime("%Z")           # e.g. "PDT"
    local_time = now_local.strftime("%H:%M %Z")    # e.g. "10:34 PDT"

    system_prompt = f"""You are an expert TMC (Traffic Management Center) operator assistant for Highway 401 westbound in Toronto.
You are NOT a chatbot. You are a co-pilot that reads live traffic data and drives the dashboard while you talk.

TIMESTAMP CONTEXT:
- Current server local time: {local_time}
- UTC offset: {utc_offset} ({tz_name})
- All timestamps in tool results are UTC. Tool results from get_corridor_handover_summary include pre-formatted
  human_time fields (e.g. \"first_alert_time\": \"17:02 UTC\") — convert these to local time for your narrative.
- To convert UTC to local: apply the UTC offset. With offset {utc_offset}, subtract the offset hours.
  Example: 00:14 UTC with offset -0700 → 17:14 {tz_name}.

LIVE CORRIDOR DATA (assembled at query time — use ONLY these numbers in your narrative):
{json.dumps(status_data, indent=2)}

Segment anchor coordinates:
{json.dumps(SEGMENT_LOCATIONS, indent=2)}

{QUERY_INTENTS}

{UI_COMMAND_SCHEMA}

TOOL USE GUIDELINES:
- You have access to 10 data-fetching tools. Call them when the user's question requires historical data
  that is NOT in the live corridor snapshot above (e.g. "how long has this been going on?",
  "how did it propagate?", "what did the corridor look like 15 minutes ago?").
- For handover briefs / shift summaries, call get_corridor_handover_summary first — it returns everything
  in one shot without pagination.
- For simple status/triage questions, use the live data above — do NOT call a tool unnecessarily.
- You may call multiple tools in sequence (up to {_MAX_TOOL_ROUNDS} rounds). After getting tool results,
  incorporate them directly into your narrative with specific timestamps and numbers.

CRITICAL RULES:
1. Never invent numbers. Every speed, risk score, or timestamp MUST come from live data or tool results.
2. If a UI command references a segment that doesn't exist, use clearHighlights and narrate the gap.
3. narrative[] and uiCommands[] must always have EXACTLY the same length.
4. Return ONLY the raw JSON object — no markdown, no preamble.
5. TIMESTAMPS: Always cite specific local times for events. Never say 'earlier' or 'recently' without a clock time.
   Convert UTC tool timestamps to local using the UTC offset above.
   Use the human_time fields from handover results as a starting point, then convert: \"began at 17:02 {tz_name}\"
   Do NOT show UTC in the narrative — local time only.
6. DURATION: Always include duration in minutes when describing historical events.
   e.g. "S9 was critical for 1.6 minutes (17:28–17:30 {tz_name})"
7. SEVERITY DURATION — NEVER HALLUCINATE: `total_alert_mins` covers the ENTIRE alerting period across ALL
   severity levels. It does NOT mean the segment was critical (or any single severity) for that whole time.
   To state how long a specific severity lasted, use `peak_severity_window.duration_mins` and its
   `from_time`/`to_time` from the handover result, OR call get_alert_history(segment_id=X) to get
   the exact transition log. NEVER say "was critical for X minutes" using total_alert_mins.

Response schema (strict):
{{
  "narrative": ["step 0 text", "step 1 text", ...],
  "uiCommands": [
    {{ "type": "...", ... }},
    ...
  ]
}}
"""

    # Build initial contents from history
    contents = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
    contents.append({"role": "user", "parts": [{"text": message}]})

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=[_TOOLS],
        temperature=0.2,
        # NOTE: response_mime_type cannot be set when tools are active.
        # JSON output is enforced via system prompt + post-processing only.
    )

    logger.debug("=== GEMINI IN ===")
    logger.debug("USER MESSAGE: %s", message)
    logger.debug("HISTORY TURNS: %d", len(history))

    # ---------------------------------------------------------------------------
    # Tool call loop
    # ---------------------------------------------------------------------------
    from tools import execute_tool

    for round_num in range(_MAX_TOOL_ROUNDS + 1):
        response = client.models.generate_content(
        model="gemini-3-flash-preview",
            contents=contents,
            config=config,
        )

        candidate = response.candidates[0]
        parts = candidate.content.parts

        # Check if any part is a function call
        function_calls = [p for p in parts if hasattr(p, "function_call") and p.function_call]

        if not function_calls:
            # No tool call — this is the final text response
            break

        if round_num == _MAX_TOOL_ROUNDS:
            logger.warning("Hit max tool rounds (%d), forcing final response", _MAX_TOOL_ROUNDS)
            break

        # Append model's tool-call response to contents
        contents.append(candidate.content)

        # Execute each tool call and append results
        tool_response_parts = []
        for part in function_calls:
            fc   = part.function_call
            args = dict(fc.args) if fc.args else {}
            logger.debug("[TOOL CALL #%d] %s(%s)", round_num + 1, fc.name, args)

            if db is None:
                result = {"error": "No database session available for tool calls"}
            else:
                result = execute_tool(fc.name, args, db)

            logger.debug("[TOOL RESULT] %s → %s", fc.name,
                         str(result)[:300] + ("…" if len(str(result)) > 300 else ""))

            tool_response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name,
                        response={"result": result},
                    )
                )
            )

        contents.append(types.Content(role="tool", parts=tool_response_parts))

    # ---------------------------------------------------------------------------
    # Parse final text response
    # ---------------------------------------------------------------------------
    response_text = ""
    for part in response.candidates[0].content.parts:
        if hasattr(part, "text") and part.text:
            response_text += part.text

    response_text = response_text.strip()
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
    commands   = parsed.get("uiCommands", [])
    length     = max(len(narratives), len(commands))

    while len(narratives) < length:
        narratives.append("")
    while len(commands) < length:
        commands.append({"type": "clearHighlights"})

    result = {"narrative": narratives, "uiCommands": commands}
    logger.debug("=== GEMINI PARSED === steps=%d", len(narratives))
    for i, (n, c) in enumerate(zip(narratives, commands)):
        logger.debug("  [%d] cmd=%-18s  %s", i, c.get("type", "?"), n[:80])
    return result
