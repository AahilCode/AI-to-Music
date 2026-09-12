"""AI Planning layer for translating natural language into validated music actions."""

import json
import os
from groq import Groq

SYSTEM_PROMPT_TEMPLATE = """You are a world-class music composer and FL Studio Copilot (specialized in Sufi, Bollywood, Lo-Fi, and Trap).
You MUST respond with a valid JSON object containing an "actions" list.

### AVAILABLE CHANNELS IN THE USER'S PROJECT:
{channels_list}

### CURRENT PROJECT TEMPO:
{current_tempo} BPM

### VALID ACTION TYPES:
1. set_tempo: {{"type": "set_tempo", "bpm": 86}}
2. set_step_pattern: {{"type": "set_step_pattern", "channel": "<exact channel name>", "steps": [0, 6, 8, 11]}}
3. clear_channel: {{"type": "clear_channel", "channel": "<exact channel name>"}}
4. record: {{"type": "record"}}
5. play: {{"type": "play"}}
6. stop: {{"type": "stop"}}
7. play_layered_progression:
   {{"type": "play_layered_progression", "sections": [
     {{"bass": [26, 38], "chords": [50, 57, 62, 64, 69], "lead": [[62, 0.6, 75], [64, 0.4, 80], [65, 0.5, 85], [69, 0.8, 95]]}},
     {{"bass": [22, 34], "chords": [46, 53, 58, 62, 65], "lead": [[65, 0.5, 80], [69, 0.4, 85], [70, 0.4, 90], [74, 0.9, 105]]}},
     {{"bass": [24, 36], "chords": [48, 55, 60, 64, 67], "lead": [[72, 0.5, 85], [74, 0.4, 90], [76, 0.9, 110], [74, 0.5, 90]]}},
     {{"bass": [21, 33], "chords": [45, 52, 57, 61, 64], "lead": [[69, 0.5, 85], [67, 0.4, 80], [65, 0.5, 80], [62, 1.2, 70]]}}
   ]}}

### MUSIC RULES:
- For Sufi/Bollywood (A.R. Rahman/Pritam): Tempo 82-90 BPM.
  - Tabla Dha/Dholak: [0, 8] or [0, 10]
  - Tabla Na: [4, 12]
- Flow: set_tempo -> set drum patterns -> record -> play -> play_layered_progression.
- Output ONLY the JSON object.
"""


def generate_action_plan(user_prompt, available_channels, current_tempo=130.0):
    """Call Groq AI to translate natural language into structured actions."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is not set.")

    client = Groq(api_key=api_key)

    channels_formatted = "\n".join("- %s" % name for name in available_channels)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.replace(
        "{channels_list}", channels_formatted
    ).replace("{current_tempo}", str(current_tempo))

    # Try fast model first, fallback to 120b if needed
    for model_name in ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            raw_content = response.choices[0].message.content
            data = json.loads(raw_content)
            if "actions" in data and isinstance(data["actions"], list):
                return data["actions"]
        except Exception:
            continue

    raise ValueError("Failed to generate valid plan from AI. Please try a simpler prompt.")
