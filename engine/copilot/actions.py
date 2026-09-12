"""Action engine for translating and executing high-level music commands."""

import time
import random
import mido
from .schema import VALID_ACTIONS
from .transport import BridgeError

def validate_action(action):
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
                
    if act_type == "play_layered_progression":
        sections = action.get("sections")
        if not isinstance(sections, list) or len(sections) == 0:
            raise ValueError("play_layered_progression requires a non-empty list of sections")
            
    return True

def resolve_channel(channel_identifier, available_channels):
    if isinstance(channel_identifier, int) and not isinstance(channel_identifier, bool):
        if 0 <= channel_identifier < len(available_channels):
            return channel_identifier
        raise ValueError("Channel index %d out of range" % channel_identifier)
        
    target = str(channel_identifier).strip().lower()
    for idx, name in enumerate(available_channels):
        if name.strip().lower() == target:
            return idx
            
    raise ValueError("Channel '%s' not found. Available: %s" 
                     % (channel_identifier, ", ".join(available_channels)))

def _play_layered_section(bridge, section):
    """Play a single bar containing sustained bass, sustained pad chord, and rhythmic lead notes."""
    bass_notes = section.get("bass", [])
    chord_notes = section.get("chords", [])
    lead_notes = section.get("lead", [])
    
    # 1. Trigger Bass & Pad Chords (Hold them throughout the section)
    sustained = bass_notes + chord_notes
    for note in sustained:
        vel = max(40, min(120, 85 + random.randint(-4, 4)))
        bridge.send_raw_midi(mido.Message('note_on', note=int(note), velocity=vel))
        
    # 2. Play the expressive lead melody notes
    for item in lead_notes:
        if isinstance(item, list) and len(item) >= 2:
            note = int(item[0])
            duration = float(item[1])
            vel = int(item[2]) if len(item) > 2 else 90
        else:
            note = int(item)
            duration = 0.25
            vel = 90
            
        note_vel = max(40, min(127, vel + random.randint(-4, 4)))
        bridge.send_raw_midi(mido.Message('note_on', note=note, velocity=note_vel))
        time.sleep(duration * 0.85)
        bridge.send_raw_midi(mido.Message('note_off', note=note, velocity=0))
        time.sleep(duration * 0.15)
        
    # 3. Release sustained bass & pad notes
    for note in sustained:
        bridge.send_raw_midi(mido.Message('note_off', note=int(note), velocity=0))
    time.sleep(0.08)

def execute_action(action, bridge, resolved_channel_idx=None):
    act_type = action["type"]
    
    if act_type == "play":
        return bridge.request("play")
    elif act_type == "stop":
        return bridge.request("stop")
    elif act_type == "record":
        return bridge.request("record")
    elif act_type == "set_tempo":
        return bridge.request("set_tempo", str(action["bpm"]))
    elif act_type == "set_step_pattern":
        steps_csv = ",".join(str(s) for s in action["steps"]) if action["steps"] else ""
        return bridge.request("set_pattern_steps", str(resolved_channel_idx), steps_csv, "4")
    elif act_type == "clear_channel":
        return bridge.request("clear_channel", str(resolved_channel_idx))
    elif act_type == "play_layered_progression":
        for section in action["sections"]:
            _play_layered_section(bridge, section)
        return "transcendent_progression_recorded"
        
    raise ValueError("Unsupported action: %s" % act_type)

def execute_batch(actions, bridge):
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
