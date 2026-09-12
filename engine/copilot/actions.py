"""Action engine for translating and executing high-level music commands."""

from .schema import VALID_ACTIONS
from .transport import BridgeError

def validate_action(action):
    """Validate a single action dict against the schema rules."""
    if not isinstance(action, dict):
        raise ValueError("Action must be a dictionary")
    
    act_type = action.get("type")
    if not act_type:
        raise ValueError("Action missing 'type' field")
        
    if act_type not in VALID_ACTIONS:
        raise ValueError("Unknown action type: %s" % act_type)
        
    rules = VALID_ACTIONS[act_type]
    
    # Check required fields
    for req in rules["required"]:
        if req not in action:
            raise ValueError("Action '%s' missing required field: '%s'" % (act_type, req))
            
    # Validate BPM
    if act_type == "set_tempo":
        try:
            bpm = float(action["bpm"])
        except (ValueError, TypeError):
            raise ValueError("BPM must be a number")
        low, high = rules["bpm_range"]
        if not (low <= bpm <= high):
            raise ValueError("BPM must be between %g and %g (got %r)" % (low, high, action["bpm"]))
            
    # Validate step and value limits
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
                
    return True

def resolve_channel(channel_identifier, available_channels):
    """Resolve a channel name (like '808 Kick') or index to a valid channel index.
    
    Returns integer index, or raises ValueError if not found.
    """
    # If already a valid int index
    if isinstance(channel_identifier, int) and not isinstance(channel_identifier, bool):
        if 0 <= channel_identifier < len(available_channels):
            return channel_identifier
        raise ValueError("Channel index %d out of range (0 to %d)" % (channel_identifier, len(available_channels) - 1))
        
    # Treat as string name
    target = str(channel_identifier).strip().lower()
    for idx, name in enumerate(available_channels):
        if name.strip().lower() == target:
            return idx
            
    raise ValueError("Channel '%s' not found. Available channels: %s" 
                     % (channel_identifier, ", ".join(available_channels)))

def execute_action(action, bridge, resolved_channel_idx=None):
    """Translate and send a single action to the bridge."""
    act_type = action["type"]
    
    if act_type == "play":
        return bridge.request("play")
        
    elif act_type == "stop":
        return bridge.request("stop")
        
    elif act_type == "set_tempo":
        return bridge.request("set_tempo", str(action["bpm"]))
        
    elif act_type == "set_step":
        if resolved_channel_idx is None:
            raise ValueError("Channel must be resolved before execution")
        return bridge.request("set_step", str(resolved_channel_idx), str(action["step"]), str(action["value"]))
        
    elif act_type == "set_step_pattern":
        if resolved_channel_idx is None:
            raise ValueError("Channel must be resolved before execution")
        # Turn off all other steps and turn on the listed steps
        for step in range(16):
            val = "1" if step in action["steps"] else "0"
            bridge.request("set_step", str(resolved_channel_idx), str(step), val)
        return "pattern_set"
        
    elif act_type == "clear_channel":
        if resolved_channel_idx is None:
            raise ValueError("Channel must be resolved before execution")
        for step in range(16):
            bridge.request("set_step", str(resolved_channel_idx), str(step), "0")
        return "channel_cleared"
        
    raise ValueError("Unsupported execution action: %s" % act_type)

def execute_batch(actions, bridge):
    """Fetch current channels, validate all actions, resolve names, and execute them."""
    if not isinstance(actions, list):
        raise ValueError("Batch must be a list of actions")
        
    # 1. Fetch available channels first
    channels_payload = bridge.request("get_channels")
    available_channels = [ch.strip() for ch in channels_payload.split(",") if ch.strip()]
    
    # 2. Validate all actions and pre-resolve channel names
    resolved_channels = []
    for action in actions:
        validate_action(action)
        
        # Pre-resolve channels if action targets a channel
        if "channel" in action:
            resolved_idx = resolve_channel(action["channel"], available_channels)
            resolved_channels.append(resolved_idx)
        else:
            resolved_channels.append(None)
            
    # 3. Execute all actions sequentially
    results = []
    for i, action in enumerate(actions):
        res = execute_action(action, bridge, resolved_channel_idx=resolved_channels[i])
        results.append((action, res))
        
    return results
