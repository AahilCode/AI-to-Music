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

VERSION = "0.1"

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
    """Run one command. Returns (status, payload-string)."""
    if command == "ping":
        return "ok", "pong"
    return "err", "unknown_command:%s" % command


def OnSysEx(msg):
    msg.handled = True  # don't let FL Studio do anything else with this
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
