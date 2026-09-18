"""AI Planning layer: translates natural language into professional DAW productions with conversational memory."""

import json
import os
from groq import Groq

SYSTEM_PROMPT_TEMPLATE = """You are a world-class music producer and FL Studio AI Copilot with 20 years of experience.
You have FULL CONVERSATIONAL MEMORY of everything you and the user have discussed and produced in this session.

### YOUR CORE BEHAVIOR:
1. When the user gives an initial prompt (e.g. "make a trap beat"), produce a rich, full 4-bar arrangement.
2. When the user asks for a MODIFICATION or FOLLOW-UP (e.g. "make it faster", "remove the claps", "change the key", "add more hi-hats"):
   - Look at the previous conversation history.
   - ONLY output the actions needed to apply the requested change!
   - For example, if user says "remove the claps", just output: [{"type": "clear_channel", "channel": "808 Clap"}]
   - If user says "speed it up to 150 BPM", just output: [{"type": "set_tempo", "bpm": 150}]

### AVAILABLE CHANNELS IN THE USER'S PROJECT:
{channels_list}

### CURRENT PROJECT TEMPO:
{current_tempo} BPM

### ALLOWED ACTION TYPES:
1. set_tempo: {"type": "set_tempo", "bpm": <number>}
2. set_step_pattern: {"type": "set_step_pattern", "channel": "<exact name>", "steps": [<0-15>]}
3. clear_channel: {"type": "clear_channel", "channel": "<exact name>"}
4. record: {"type": "record"}
5. play: {"type": "play"}
6. stop: {"type": "stop"}
7. play_layered_progression: {"type": "play_layered_progression", "sections": [<4 bar objects>]}

### RULES:
1. Always match exact channel names from the available list.
2. Return ONLY valid JSON with an "actions" list. No commentary outside the JSON.
"""


def generate_action_plan(user_prompt, available_channels, current_tempo=130.0, chat_history=None):
    """Call Groq AI with full conversation history for context-aware iterative editing."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is not set.")

    client = Groq(api_key=api_key)

    channels_formatted = "\n".join("- %s" % name for name in available_channels)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.replace(
        "{channels_list}", channels_formatted
    ).replace("{current_tempo}", str(current_tempo))

    # Build message chain with full conversation history
    messages = [{"role": "system", "content": system_prompt}]

    if chat_history:
        for turn in chat_history:
            messages.append({"role": turn["role"], "content": turn["content"]})

    messages.append({"role": "user", "content": user_prompt})

    for model_name in ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            raw_content = response.choices[0].message.content
            data = json.loads(raw_content)
            if "actions" in data and isinstance(data["actions"], list):
                return data["actions"], raw_content
        except Exception as e:
            print(f"[AI DEBUG] Model {model_name} failed: {e}")
            continue

    raise ValueError("Failed to generate valid plan from AI. Please try a simpler prompt.")
