"""SysEx wire protocol v0 — shared semantics with fl_bridge/device_aicopilot.py.

Both sides speak the same bytes. This module is the ENGINE-side
implementation (pure Python, no MIDI library needed), so it is fully
unit-testable without FL Studio or MIDI hardware.

Wire format:
    F0 7D 41 43 01 <dir> <req_id> <ASCII payload...> F7
Requests:  payload = "<command>" or "<command>:<arg1>:<arg2>..."
Responses: payload = "ok:<result>" or "err:<code>:<message>"

Phase-1 limits (deliberate, documented, revisited in Phase 2):
  - ASCII-only payloads (SysEx data bytes must be < 0x80)
  - single SysEx frame per message (no chunking yet; max ~200 payload bytes)
"""

SYSEX_START = 0xF0
SYSEX_END = 0xF7
MANUFACTURER_ID = 0x7D  # reserved for development / non-commercial use
SIG_A = 0x41            # 'A'
SIG_C = 0x43            # 'C'
PROTO_VERSION = 0x01
DIR_REQUEST = 0x01
DIR_RESPONSE = 0x02

MAX_REQ_ID = 126
MAX_PAYLOAD_BYTES = 200


class ProtocolError(ValueError):
    """Raised when bytes on the wire aren't a valid v0 message."""


def encode_request(req_id: int, command: str, *args: str) -> bytes:
    """Build one request SysEx message (engine -> FL Studio)."""
    _check_req_id(req_id)
    payload = ":".join([command, *[str(a) for a in args]])
    return _frame(DIR_REQUEST, req_id, payload)


def encode_response(req_id: int, status: str, payload: str) -> bytes:
    """Build one response SysEx message (FL Studio -> engine).

    The FL script implements this same logic; this copy exists so tests
    and future tools can craft/verify responses.
    """
    _check_req_id(req_id)
    if status not in ("ok", "err"):
        raise ProtocolError("status must be 'ok' or 'err', got %r" % status)
    return _frame(DIR_RESPONSE, req_id, "%s:%s" % (status, payload))


def decode_message(raw: bytes) -> dict:
    """Parse one SysEx message into a dict.

    Returns e.g. {"direction": "request", "req_id": 3,
                   "command": "set_tempo", "args": ["145"]}
    or         {"direction": "response", "req_id": 3,
                "status": "ok", "payload": "pong"}.

    Raises ProtocolError if the message isn't ours.
    """
    data = bytes(raw)
    if data[:1] == bytes((SYSEX_START,)):
        data = data[1:]
    if data[-1:] == bytes((SYSEX_END,)):
        data = data[:-1]
    if len(data) < 7:
        raise ProtocolError("message too short (%d bytes)" % len(data))
    header = (MANUFACTURER_ID, SIG_A, SIG_C, PROTO_VERSION)
    if tuple(data[:4]) != header:
        raise ProtocolError("not an AI-Copilot message (bad header)")
    direction = data[4]
    if direction == DIR_REQUEST:
        kind = "request"
    elif direction == DIR_RESPONSE:
        kind = "response"
    else:
        raise ProtocolError("bad direction byte: %#x" % direction)
    req_id = data[5]
    try:
        text = data[6:].decode("ascii")
    except UnicodeDecodeError:
        raise ProtocolError("payload is not ASCII")
    parts = text.split(":")
    if kind == "request":
        return {"direction": kind, "req_id": req_id,
                "command": parts[0], "args": parts[1:]}
    if len(parts) < 2 or parts[0] not in ("ok", "err"):
        raise ProtocolError("malformed response payload: %r" % text)
    return {"direction": kind, "req_id": req_id,
            "status": parts[0], "payload": ":".join(parts[1:])}


def _check_req_id(req_id: int) -> None:
    if not 1 <= req_id <= MAX_REQ_ID:
        raise ProtocolError(
            "req_id must be 1..%d, got %r" % (MAX_REQ_ID, req_id))


def _frame(direction: int, req_id: int, payload: str) -> bytes:
    try:
        payload_bytes = payload.encode("ascii")
    except UnicodeEncodeError:
        raise ProtocolError("payload must be ASCII-only in protocol v0: %r"
                            % payload)
    if len(payload_bytes) > MAX_PAYLOAD_BYTES:
        raise ProtocolError(
            "payload too large for v0 single frame (%d > %d bytes)"
            % (len(payload_bytes), MAX_PAYLOAD_BYTES))
    return (bytes((SYSEX_START, MANUFACTURER_ID, SIG_A, SIG_C,
                   PROTO_VERSION, direction, req_id))
            + payload_bytes + bytes((SYSEX_END,)))
