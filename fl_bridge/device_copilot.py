# name=AI Copilot Bridge
# url=https://github.com/AahilCode/AI-to-Music

import device
import general
import transport
import mixer
import patterns
import channels
import playlist
import ui
import midi

VERSION = "0.3.3"

_SYSEX_START = 0xF0
_SYSEX_END = 0xF7
_MANUFACTURER_ID = 0x7D
_SIG_A = 0x41
_SIG_C = 0x43
_PROTO_VERSION = 0x01
_DIR_REQUEST = 0x01
_DIR_RESPONSE = 0x02


def OnInit():
    print("[AICopilot] bridge v%s init" % VERSION)
    print("[AICopilot] API version: %s" % general.getVersion())
    try:
        print("[AICopilot] device: %s / port %s / output assigned: %s"
              % (device.getName(), device.getPortNumber(), device.isAssigned()))
    except Exception as e:
        print("[AICopilot] device info error: %s" % e)
    print("[AICopilot] ready, waiting for SysEx commands")


def OnDeInit():
    print("[AICopilot] bridge stopped")


def _parse_request(raw):
    if not raw:
        return None, None, None
    if raw[0] == _SYSEX_START:
        raw = raw[1:]
    if raw and raw[-1] == _SYSEX_END:
        raw = raw[:-1]
    if len(raw) < 6:
        return None, None, None
    if raw[0] != _MANUFACTURER_ID or raw[1] != _SIG_A or raw[2] != _SIG_C:
        return None, None, None
    if raw[3] != _PROTO_VERSION or raw[4] != _DIR_REQUEST:
        return None, None, None

    req_id = raw[5]
    try:
        text = raw[6:].decode("ascii")
    except Exception:
        return req_id, "err", ["invalid_ascii"]

    if ":" in text:
        tokens = text.split(":")
    else:
        tokens = text.split()

    if not tokens:
        return req_id, "err", ["empty_command"]
    return req_id, tokens[0], tokens[1:]


def _send_response(req_id, status, payload):
    if not device.isAssigned():
        print("[AICopilot] ERROR: no output device linked")
        return
    text = "%s:%s" % (status, payload)
    msg = bytes((_SYSEX_START, _MANUFACTURER_ID, _SIG_A, _SIG_C,
                 _PROTO_VERSION, _DIR_RESPONSE, req_id))
    msg += text.encode("ascii")
    msg += bytes((_SYSEX_END,))
    device.midiOutSysex(msg)


def _dispatch(command, args):
    if command == "ping":
        return "ok", "pong"
    if command == "get_tempo":
        raw_tempo = mixer.getCurrentTempo()
        bpm = raw_tempo / 1000.0 if raw_tempo > 1000 else float(raw_tempo)
        return "ok", "%.2f" % bpm
    if command == "set_tempo":
        if not args:
            return "err", "set_tempo requires a BPM argument"
        try:
            bpm = float(args[0])
            mixer.setCurrentTempo(int(bpm * 1000))
            return "ok", "%.2f" % bpm
        except ValueError:
            return "err", "invalid BPM value: %s" % args[0]
    if command == "play":
        # Ensure Pattern Mode is active (0 = Song, 1 = Pattern)
        try:
            transport.setLoopMode(1)
        except Exception:
            pass
        transport.start()
        return "ok", "playing"
    if command == "record":
        try:
            transport.setLoopMode(1)
        except Exception:
            pass
        transport.record()
        return "ok", "recording"
    if command == "stop":
        transport.stop()
        return "ok", "stopped"
    if command == "is_playing":
        return "ok", "true" if transport.isPlaying() else "false"
    if command == "get_channels":
        count = channels.channelCount()
        names = [channels.getChannelName(i) for i in range(count)]
        return "ok", ",".join(names)
    if command == "get_pattern":
        num = patterns.patternNumber()
        name = patterns.getPatternName(num)
        return "ok", "num:%d,name:%s" % (num, name)
    if command == "set_pattern_steps":
        if len(args) < 2:
            return "err", "set_pattern_steps requires <channel_index> <steps_csv>"
        try:
            ch = int(args[0])
            steps_csv = args[1]
            bars = int(args[2]) if len(args) > 2 else 4
            step_indices = [int(s) for s in steps_csv.split(",") if s.strip()]
            
            for s in range(bars * 16):
                channels.setGridBit(ch, s, 0)
            
            for b in range(bars):
                offset = b * 16
                for s in step_indices:
                    channels.setGridBit(ch, offset + s, 1)
            return "ok", "ch:%d,bars:%d" % (ch, bars)
        except Exception as e:
            return "err", "set_pattern_steps error: %s" % e
    if command == "clear_channel":
        if not args:
            return "err", "clear_channel requires <channel_index>"
        try:
            ch = int(args[0])
            for s in range(64):
                channels.setGridBit(ch, s, 0)
            return "ok", "cleared:%d" % ch
        except Exception as e:
            return "err", "clear_channel error: %s" % e
    return "err", "unknown_command:%s" % command


def _is_sysex(msg):
    status = getattr(msg, "status", None)
    midi_id = getattr(msg, "midiId", None)
    return status == _SYSEX_START or midi_id == _SYSEX_START


def OnMidiMsg(msg):
    if _is_sysex(msg):
        msg.handled = True
        _handle_sysex(msg)


def OnSysEx(msg):
    msg.handled = True
    _handle_sysex(msg)


def _handle_sysex(msg):
    raw = getattr(msg, "sysex", None)
    if raw is None:
        return
    req_id, command, args = _parse_request(raw)
    if req_id is None:
        return
    if command == "err":
        _send_response(req_id if req_id else 0, "err", args[0])
        return
    try:
        status, payload = _dispatch(command, args)
    except Exception as e:
        status, payload = "err", "exception:%s" % e
    _send_response(req_id, status, payload)
    print("[AICopilot] %s %s -> %s:%s" % (command, args, status, payload))
