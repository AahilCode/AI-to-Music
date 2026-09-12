"""Action engine for translating and executing high-level music commands."""

import time
import random
import mido
from .schema import VALID_ACTIONS
from .transport import BridgeError

def validate_action(action):
    """Validate a single action dict against schema rules."""
    if not isinstance(action, dict):
        raise ValueError("Action must be a dictionary")
    
    act_type = action.get("type")
    if not act_type:
        raise ValueError("Action missing 'type' field")
        
    if act_type not in VALID_ACTIONS:
        raise ValueError("Unknown action type: %s" % act_type)
        
    rules = VALID_ACTIONS[act_type]
    
    for req in rules["required"]:
        if req not in action:
            raise ValueError("Action '%s' missing required field: '%s'" % (act_type, req))
            
    if act_type == "set_tempo":
        try:
            bpm = float(action["bpm"])
        except (ValueError, TypeError):
            raise ValueError("BPM must be a number")
        low, high = rules["bpm_range"]
        if not (low <= bpm <= high):
            raise ValueError("BPM must be between %g and %g (got %r)" % (low, high, action["bpm"]))
            
    if act_type == "set_step":
        step = action["step"]
        if not isinstance(step, int) or isinstance(step, bool):
            raise ValueError("Step must be an integer")
        low, high = rules["step_range"]
        if not (low <= step <= high):
            raise ValueError("Step must be between %d and %d (got %r)" % (low, high, step))
        val = action["value"]
        if val not in (0, 1):
            raise ValueError("Value must be 0 or 1 (got %r)" % val)
            
    if act_type == "set_step_pattern":
        steps = action["steps"]
        if not isinstance(steps, list):
            raise ValueError("Steps must be a list of integers")
        low, high = rules["step_range"]
        for s in steps:
            if not isinstance(s, int) or isinstance(s, bool):
                raise ValueError("Pattern step must be an integer")
            if not (low <= s <= high):
                raise ValueError("Pattern step must be between %d and %d (got %r)" % (low, high, s))
                
    if act_type in ("play_chords", "play_melody"):
        items = action.get("chords") or action.get("notes")
        if not isinstance(items, list):
            raise ValueError("%s requires a list" % act_type)
            
    return True

def resolve_channel(channel_identifier, available_channels):
    """Resolve a channel name (like '808 Kick') to a valid channel index."""
    if isinstance(channel_identifier, int) and not isinstance(channel_identifier, bool):
        if 0 <= channel_identifier < len(available_channels):
            return channel_identifier
        raise ValueError("Channel index %d out of range (0 to %d)" % (channel_identifier, len(available_channels) - 1))
        
    target = str(channel_identifier).strip().lower()
    for idx, name in enumerate(available_channels):
        if name.strip().lower() == target:
            return idx
            
    raise ValueError("Channel '%s' not found. Available channels: %s" 
                     % (channel_identifier, ", ".join(available_channels)))

def _play_single_note(bridge, note, velocity=80, duration=0.2):
    """Play a single expressive note via bridge."""
    vel = max(30, min(120, velocity + random.randint(-6, 6)))
    bridge.send_raw_midi(mido.Message('note_on', note=int(note), velocity=vel))
    time.sleep(duration * 0.85)
    bridge.send_raw_midi(mido.Message('note_off', note=int(note), velocity=0))
    time.sleep(duration * 0.15)

def execute_action(action, bridge, resolved_channel_idx=None):
    """Translate and execute a single action."""
    act_type = action["type"]
    
    if act_type == "play":
        return bridge.request("play")
        
    elif act_type == "stop":
        return bridge.request("stop")
        
    elif act_type == "set_tempo":
        return bridge.request("set_tempo", str(action["bpm"]))
        
    elif act_type == "set_step":
        return bridge.request("set_step", str(resolved_channel_idx), str(action["step"]), str(action["value"]))
        
    elif act_type == "set_step_pattern":
        for step in range(16):
            val = "1" if step in action["steps"] else "0"
            bridge.request("set_step", str(resolved_channel_idx), str(step), val)
        return "pattern_set"
        
    elif act_type == "clear_channel":
        for step in range(16):
            bridge.request("set_step", str(resolved_channel_idx), str(step), "0")
        return "channel_cleared"
        
    elif act_type == "play_melody":
        duration = float(action.get("note_duration", 0.2))
        vel = int(action.get("velocity", 80))
        for n in action["notes"]:
            _play_single_note(bridge, n, velocity=vel, duration=duration)
        return "melody_played"
        
    elif act_type == "play_chords":
        duration = float(action.get("chord_duration", 1.0))
        for chord in action["chords"]:
            notes = chord if isinstance(chord, list) else chord.get("notes", [60, 64, 67])
            for n in notes:
                bridge.send_raw_midi(mido.Message('note_on', note=int(n), velocity=80))
            time.sleep(duration * 0.85)
            for n in notes:
                bridge.send_raw_midi(mido.Message('note_off', note=int(n), velocity=0))
            time.sleep(duration * 0.15)
        return "chords_played"
        
    raise ValueError("Unsupported execution action: %s" % act_type)

def execute_batch(actions, bridge):
    """Fetch channels, validate actions, resolve names, and execute."""
    if not isinstance(actions, list):
        raise ValueError("Batch must be a list of actions")
        
    channels_payload = bridge.request("get_channels")
    available_channels = [ch.strip() for ch in channels_payload.split(",") if ch.strip()]
    
    resolved_channels = []
    for action in actions:
        validate_action(action)
        if "channel" in action:
            resolved_idx = resolve_channel(action["channel"], available_channels)
            resolved_channels.append(resolved_idx)
        else:
            resolved_channels.append(None)
            
    results = []
    for i, action in enumerate(actions):
        res = execute_action(action, bridge, resolved_channel_idx=resolved_channels[i])
        results.append((action, res))
        
    return results
