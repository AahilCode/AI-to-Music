# name=AI Copilot Bridge
# url=https://github.com/AahilCode/AI-to-Music
#
# AI-to-Music: FL Studio side of the bridge (Phase 1, v0.1).
#
# WHAT THIS IS: a MIDI Controller Script. FL Studio loads it automatically
# and keeps it running. It receives commands from our external Python engine
# as MIDI SysEx messages, executes them via FL Studio's API, and sends
# responses back as SysEx.
#
# WHY SysEx: FL Studio's scripting sandbox forbids sockets/files/threads,
# so MIDI is the only channel from the outside world. SysEx messages can
# carry arbitrary bytes, which makes them our command pipe.
#
# WIRE FORMAT v0 (see engine/copilot/protocol.py — same format, both sides):
#   F0 7D 41 43 01 <dir> <req_id> <ASCII payload...> F7
#    |  |   |  |  |    |      |            |
#    |  |   |  |  |    |      |            +-- e.g. "ping" or "ok:pong"
#    |  |   |  |  |    |      +-- request id (1..126, echoes back in reply)
#    |  |   |  |  |    +-- direction: 0x01=request, 0x02=response
#    |  |   |  |  +-- protocol version
#    |  |   |  +-- 'A' 'C' signature ("AI Copilot")
#    |  +-- 0x7D = development/non-commercial manufacturer ID
#    +-- SysEx start (F7 = end, added by midiOutSysex framing)

import device
import general
import transport
import mixer
import patterns
import channels
import playlist
import ui
import midi

VERSION = "0.2"

# --- protocol constants (must match engine/copilot/protocol.py) ---
_SYSEX_START = 0xF0
_SYSEX_END = 0xF7
_MANUFACTURER_ID = 0x7D  # reserved for development / non-commercial use
_SIG_A = 0x41            # 'A'
_SIG_C = 0x43            # 'C'
_PROTO_VERSION = 0x01
_DIR_REQUEST = 0x01
_DIR_RESPONSE = 0x02


def _probe_sandbox():
    """Experiment 0: find out what this sandbox actually allows.

    Tries importing modules and reports OK/FAIL to the Script output
    window. This decideslater design (e.g. JSON vs hand-rolled protocol).
    """
    for mod in ("json", "struct", "base64", "time", "math", "sys",
                "socket", "os", "threading"):
        try:
            __import__(mod)
            print("[AICopilot] import %s: OK" % mod)
        except Exception as e:
            print("[AICopilot] import %s: FAIL (%s)" % (mod, e))


def OnInit():
    print("[AICopilot] bridge v%s init" % VERSION)
    print("[AICopilot] API version: %s" % general.getVersion())
    try:
        print("[AICopilot] device: %s / port %s / output assigned: %s"
              % (device.getName(), device.getPortNumber(),
                 device.isAssigned()))
    except Exception as e:
        print("[AICopilot] device info error: %s" % e)
    _probe_sandbox()
    for mod_name, mod in [("transport", transport), ("general", general), ("mixer", mixer), ("patterns", patterns), ("channels", channels), ("playlist", playlist), ("ui", ui), ("midi", midi)]:
        matches = [f for f in dir(mod) if "tempo" in f.lower() or "bpm" in f.lower()]
        if matches:
            print("[AICopilot] Found tempo/bpm functions in %s: %s" % (mod_name, matches))
    print("[AICopilot] ready, waiting for SysEx commands")


def OnDeInit():
    print("[AICopilot] bridge stopped")


def _parse_request(raw):
    """Parse incoming SysEx bytes -> (req_id, command, args).

    Returns (None, None, None) if the message isn't ours.
    Tolerates the F0/F7 framing being present or absent, since that
    differs across FL Studio versions (MUST-TEST in Experiment 1).
    """
    data = bytes(raw)
    if data[:1] == bytes((_SYSEX_START,)):
        data = data[1:]
    if data[-1:] == bytes((_SYSEX_END,)):
        data = data[:-1]
    header = (_MANUFACTURER_ID, _SIG_A, _SIG_C, _PROTO_VERSION,
              _DIR_REQUEST)
    if len(data) < 7 or tuple(data[:5]) != header:
        return None, None, None
    req_id = data[5]
    try:
        text = data[6:].decode("ascii")
    except Exception:
        return req_id, "err", ["non_ascii_payload"]
    parts = text.split(":")
    return req_id, parts[0], parts[1:]


def _send_response(req_id, status, payload):
    """Send a SysEx response back to the engine via the linked output."""
    if not device.isAssigned():
        print("[AICopilot] ERROR: no output device linked "
              "(set Output port = Input port in MIDI Settings)")
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
            # FL Studio expects milli-BPM (e.g. 145000 for 145 BPM)
            mixer.setCurrentTempo(int(bpm * 1000))
            return "ok", "%.2f" % bpm
        except ValueError:
            return "err", "invalid BPM value: %s" % args[0]
    if command == "play":
        transport.start()
        return "ok", "playing"
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
    if command == "set_step":
        # Usage: set_step <channel_index> <step_index> <val: 0 or 1>
        if len(args) < 3:
            return "err", "set_step requires <channel_index> <step_index> <value 0 or 1>"
        try:
            ch = int(args[0])
            step = int(args[1])
            val = int(args[2])
            channels.setGridBit(ch, step, val)
            return "ok", "ch:%d,step:%d,val:%d" % (ch, step, val)
        except Exception as e:
            return "err", "set_step error: %s" % e
    if command == "get_step":
        # Usage: get_step <channel_index> <step_index>
        if len(args) < 2:
            return "err", "get_step requires <channel_index> <step_index>"
        try:
            ch = int(args[0])
            step = int(args[1])
            val = channels.getGridBit(ch, step)
            return "ok", str(val)
        except Exception as e:
            return "err", "get_step error: %s" % e
    return "err", "unknown_command:%s" % command


def _is_sysex(msg):
    """True if this OnMidiMsg event is a SysEx message.

    Official docs: for SysEx, msg.status is 0xF0 (and msg.sysex is only
    readable for SysEx — touching it for other events can raise, so we
    check status/midiId FIRST and never sniff msg.sysex here).
    """
    try:
        if msg.status == 0xF0:
            return True
    except Exception:
        pass
    try:
        if msg.midiId == 0xF0:
            return True
    except Exception:
        pass
    return False


def OnMidiMsg(msg):
    # SysEx routing differs across FL builds: some deliver SysEx ONLY
    # here (never calling OnSysEx), some ONLY to OnSysEx, some chain
    # OnMidiMsg -> OnSysEx. Intercepting here with handled=True covers
    # the first case, and (per docs) stops propagation so chained builds
    # don't double-execute. See docs/phase-1-plan.md Experiment 1 notes.
    if _is_sysex(msg):
        msg.handled = True
        _handle_sysex(msg)
    # All other MIDI passes through untouched (handled stays False).


def OnSysEx(msg):
    msg.handled = True  # don't let FL Studio do anything else with this
    _handle_sysex(msg)


def _handle_sysex(msg):
    """Shared SysEx handler used by both OnMidiMsg and OnSysEx."""
    req_id, command, args = _parse_request(msg.sysex)
    if req_id is None:
        return  # not our message (some other SysEx on the bus) — ignore
    if command == "err":
        _send_response(req_id if req_id else 0, "err", args[0])
        return
    try:
        status, payload = _dispatch(command, args)
    except Exception as e:
        status, payload = "err", "exception:%s" % e
    _send_response(req_id, status, payload)
    print("[AICopilot] %s %s -> %s:%s" % (command, args, status, payload))