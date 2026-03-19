import os
import json
from google import genai
from google.genai import types

def call_gemini_api(message: str, history: list, status_data: dict):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
        
    client = genai.Client(api_key=api_key)
    
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
S1: 43.7280, -79.5120
S2: 43.7265, -79.5280
S3: 43.7255, -79.5420
S4: 43.7242, -79.5580
S5: 43.7228, -79.5740

Only include noteworthy segments in talking_points.
Always include all 5 segments in highlights.
Do not include markdown formatting, just the raw JSON.
"""

    contents = []
    for msg in history:
        # Parse standard role (user/assistant) into user/model
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    
    contents.append({"role": "user", "parts": [{"text": message}]})

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            temperature=0.2,
        )
    )
    
    response_text = response.text.strip()
    
    if response_text.startswith("```json"):
        response_text = response_text[7:]
    if response_text.startswith("```"):
        response_text = response_text[3:]
    if response_text.endswith("```"):
        response_text = response_text[:-3]
        
    return json.loads(response_text.strip())
