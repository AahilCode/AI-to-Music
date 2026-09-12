"""AI Planning layer for translating natural language into validated music actions."""

import json
import os
from groq import Groq

SYSTEM_PROMPT_TEMPLATE = """You are an elite music producer and FL Studio AI Copilot.
Your job is to translate the user's natural language music request into a structured JSON list of DAW actions.

### AVAILABLE CHANNELS IN THE USER'S PROJECT:
{channels_list}

### CURRENT PROJECT TEMPO:
{current_tempo} BPM

### ALLOWED ACTION TYPES:
1. set_tempo: {"type": "set_tempo", "bpm": <number between 10 and 999>}
2. set_step_pattern: {"type": "set_step_pattern", "channel": "<exact channel name>", "steps": [<step numbers 0-15>]}
3. clear_channel: {"type": "clear_channel", "channel": "<exact channel name>"}
4. play: {"type": "play"}
5. stop: {"type": "stop"}
6. play_chords: {"type": "play_chords", "chords": [[60, 63, 67], [56, 60, 63]], "chord_duration": 1.2}
7. play_melody: {"type": "play_melody", "notes": [48, 60, 63, 67, 72, 67, 63, 60], "note_duration": 0.2, "velocity": 85}

### MUSIC THEORY KNOWLEDGE:
- MIDI Note Numbers: C3=48, D#3=51, G3=55, C4=60, D4=62, D#4/Eb4=63, F4=65, G4=67, G#4/Ab4=68, A#4/Bb4=70, C5=72.
- Dark Trap / Sad Piano Progression in C Minor:
    - Chord 1 (C Minor): [48, 60, 63, 67]
    - Chord 2 (Ab Major): [44, 56, 60, 63, 68]
    - Chord 3 (Eb Major): [46, 58, 63, 67]
    - Chord 4 (Bb Major): [46, 58, 62, 65]
- Arpeggiated Melodies: Rapid flowing sequence of notes from the scale (duration 0.15 - 0.25s).
- Drums (16 steps):
    - Kick: [0, 4, 8, 12] (4-on-floor) or [0, 6, 8, 11] (Trap)
    - Clap / Snare: [4, 12]
    - Hi-Hats: [0, 2, 4, 6, 8, 10, 12, 14] (2-step) or [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15] (fast 16th)

### RULES:
1. Match exact channel names for drum patterns.
2. If the user asks for a melody, piano, guitar, or chords, include `play_melody` or `play_chords`.
3. If user wants the beat to play, include `{"type": "play"}` before playing the melody.
4. Output ONLY valid JSON containing the "actions" list.
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
        raise ValueError("Failed to parse AI JSON response: %s" % e)
