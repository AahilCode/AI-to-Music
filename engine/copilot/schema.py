"""Schema and validation rules for high-level copilot actions."""

VALID_ACTIONS = {
    "set_tempo": {
        "required": ["bpm"],
        "bpm_range": (10, 999)
    },
    "play": {
        "required": []
    },
    "stop": {
        "required": []
    },
    "record": {
        "required": []
    },
    "set_step_pattern": {
        "required": ["channel", "steps"],
        "step_range": (0, 15)
    },
    "clear_channel": {
        "required": ["channel"]
    },
    "play_layered_progression": {
        "required": ["sections"]
    }
}
