import os
import json
from anthropic import Anthropic

def call_claude_api(message: str, history: list, status_data: dict):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
    client = Anthropic(api_key=api_key)
    
    system_prompt = f"""You are an AI assistant for a Traffic Management Centre operator monitoring Highway 401 westbound in Toronto.
Current segment status data:
{json.dumps(status_data, indent=2)}

Respond ONLY with a valid JSON object matching this exact schema:
{{
  "narrative": "string — 2-4 sentence plain English status summary",
  "talking_points": [
    {{
      "id": number,
      "segment_id": "S1"|"S2"|"S3"|"S4"|"S5",
      "severity": "normal" | "watch" | "warning" | "critical",
      "confidence": float 0–1,
      "text": "string — one sentence, specific and actionable",
      "anchor": {{ "lat": float, "lng": float }}
    }}
  ],
  "highlights": [
    {{
      "segment_id": "S1"|"S2"|"S3"|"S4"|"S5",
      "color": "green" | "yellow" | "amber" | "red",
      "pulse": boolean
    }}
  ]
}}

Segment locations for anchors:
S1: 43.7157, -79.5264
S2: 43.7178, -79.5076
S3: 43.7199, -79.4936
S4: 43.7226, -79.4818
S5: 43.7271, -79.4624

Only include noteworthy segments in talking_points.
Always include all 5 segments in highlights.
Do not include markdown formatting, just the raw JSON.
"""

    messages = []
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1000,
        system=system_prompt,
        messages=messages
    )
    
    response_text = response.content[0].text.strip()
    
    if response_text.startswith("```json"):
        response_text = response_text[7:]
    if response_text.startswith("```"):
        response_text = response_text[3:]
    if response_text.endswith("```"):
        response_text = response_text[:-3]
        
    return json.loads(response_text.strip())
