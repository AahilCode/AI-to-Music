"""AI Planning layer for translating natural language into validated music actions."""

import json
import os
from groq import Groq

SYSTEM_PROMPT_TEMPLATE = """You are an expert music producer and FL Studio Copilot.
Your job is to translate the user's natural language music request into a structured JSON list of DAW actions.

### AVAILABLE CHANNELS IN THE USER'S PROJECT:
{channels_list}

### CURRENT PROJECT TEMPO:
{current_tempo} BPM

### ALLOWED ACTION TYPES AND SCHEMA:
1. set_tempo: {{"type": "set_tempo", "bpm": <number between 10 and 999>}}
2. set_step_pattern: {{"type": "set_step_pattern", "channel": "<exact channel name from list>", "steps": [<list of step numbers from 0 to 15>]}}
3. set_step: {{"type": "set_step", "channel": "<exact channel name from list>", "step": <0-15>, "value": <0 or 1>}}
4. clear_channel: {{"type": "clear_channel", "channel": "<exact channel name from list>"}}
5. play: {{"type": "play"}}
6. stop: {{"type": "stop"}}

### MUSIC PRODUCTION KNOWLEDGE (16-step grid, 4/4 time):
- Steps 0, 4, 8, 12 are the 4 main beats (downbeats).
- Standard 4-on-the-floor Kick: steps [0, 4, 8, 12].
- Standard Trap / Hip-Hop Kick: syncopated patterns like [0, 6, 8, 11] or [0, 7, 10, 13] or [0, 10].
- Claps/Snares in Trap/Hip-Hop: usually hit on step 4 and step 12 (beat 2 and 4).
- 2-step Hi-Hats: [0, 2, 4, 6, 8, 10, 12, 14] (every 8th note).
- 1-step / Fast Hi-Hats: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15] (all 16th notes).

### CRITICAL RULES:
1. ONLY use channel names that exist in the available channels list. Match the exact name.
2. If the user asks for an instrument that is not loaded, pick the closest matching channel from the list (e.g. if user asks for "kick", pick "808 Kick").
3. Always return a valid JSON object with the key "actions" containing the list of action objects.
4. Do NOT output any markdown commentary outside the JSON. Return ONLY the JSON object.
"""


def generate_action_plan(user_prompt, available_channels, current_tempo=130.0):
    """Call Groq AI to translate natural language into structured actions."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY environment variable is not set. Run: export GROQ_API_KEY='your_key'"
        )

    client = Groq(api_key=api_key)

    channels_formatted = "\n".join("- %s" % name for name in available_channels)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        channels_list=channels_formatted, current_tempo=current_tempo
    )

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    raw_content = response.choices[0].message.content
    try:
        data = json.loads(raw_content)
        if "actions" not in data:
            raise ValueError("AI response missing 'actions' key")
        return data["actions"]
    except json.JSONDecodeError as e:
        raise ValueError(
            "Failed to parse AI JSON response: %s (Raw: %s)" % (e, raw_content)
        )
