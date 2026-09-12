"""MIDI transport: carries protocol messages between engine and FL Studio.

Uses `mido` (with the `python-rtmidi` backend) to talk to the virtual MIDI
buses created in Audio MIDI Setup:
  - OUT -> "Copilot CMD"  (commands to FL Studio)
  - IN  <- "Copilot RSP"  (responses from FL Studio)

Design note for learners: the Bridge takes already-opened port objects
instead of opening them itself ("dependency injection"). That is what lets
us unit-test all the request/response logic with FAKE ports, no MIDI
hardware or FL Studio needed. Real ports are opened by the CLI.
"""

import time

from . import protocol


class BridgeTimeout(TimeoutError):
    """No matching response arrived before the deadline."""


def open_ports(cmd_port_name="Copilot CMD", rsp_port_name="Copilot CMD"):
    """Open the real virtual-MIDI ports. Call only from the CLI / app."""
    try:
        import mido
    except ImportError:
        raise SystemExit(
            "The 'mido' package is missing. Run:\n"
            "    pip install -r requirements.txt")
    return _Bridge(mido.open_output(_match(mido.get_output_names(),
                                            cmd_port_name, "output")),
                   mido.open_input(_match(mido.get_input_names(),
                                           rsp_port_name, "input")))


def list_ports():
    """Return (inputs, outputs) available on this machine (for debugging)."""
    import mido
    return mido.get_input_names(), mido.get_output_names()


def _match(available, wanted, kind):
    for name in available:
        if wanted in name:  # substring: macOS may decorate IAC port names
            return name
    raise SystemExit(
        "Could not find %s MIDI port containing %r.\n"
        "Available %s ports: %s\n"
        "Fix: create/enable the IAC buses (docs/phase-1-plan.md, step A1) "
        "and check the spelling." % (kind, wanted, kind, available))


def _mido_sysex_factory(data):
    """Build a real mido SysEx message (imported lazily so unit tests
    never need mido installed)."""
    import mido
    return mido.Message("sysex", data=data)


class _Bridge:
    """Request/response client over two one-way MIDI ports."""

    def __init__(self, out_port, in_port, sysex_factory=None):
        self._out = out_port
        self._in = in_port
        # Tests inject a fake factory; real use builds mido messages.
        self._make_sysex = sysex_factory or _mido_sysex_factory
        self._next_id = 0

    @property
    def port_names(self):
        return (getattr(self._in, "name", "?"),
                getattr(self._out, "name", "?"))

    def request(self, command, *args, timeout=2.0):
        """Send one command, wait for the matching response.

        Returns the response payload string on "ok", raises BridgeError
        on "err", raises BridgeTimeout if nothing arrives in time.
        """
        self._next_id = (self._next_id % protocol.MAX_REQ_ID) + 1
        req_id = self._next_id
        wire = protocol.encode_request(req_id, command, *args)
        self._send_sysex(wire)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BridgeTimeout(
                    "no response to '%s' (req #%d) within %.1fs. "
                    "Is FL Studio running with the bridge script selected "
                    "as Controller type?" % (command, req_id, timeout))
            msg = self._recv_sysex(timeout=remaining)
            if msg is None:
                continue
            try:
                decoded = protocol.decode_message(msg)
            except protocol.ProtocolError:
                continue  # someone else's SysEx on the bus — ignore
            if (decoded["direction"] != "response"
                    or decoded["req_id"] != req_id):
                continue  # stale / foreign message — ignore
            if decoded["status"] == "ok":
                return decoded["payload"]
            raise BridgeError(decoded["payload"])

    def close(self):
        for port in (self._in, self._out):
            close = getattr(port, "close", None)
            if callable(close):
                close()

    # -- low-level send/receive (mido-specific, isolated here) ---------

    def _send_sysex(self, wire: bytes):
        # mido wants SysEx data WITHOUT the F0/F7 framing bytes.
        self._out.send(self._make_sysex(wire[1:-1]))

    def _recv_sysex(self, timeout):
        msg = self._in.poll()
        if msg is None:
            # poll() is non-blocking; sleep briefly instead of busy-spin.
            time.sleep(0.005)
            return None
        if msg.type != "sysex":
            return None
        return bytes((protocol.SYSEX_START, *msg.data,
                      protocol.SYSEX_END))


class BridgeError(Exception):
    """FL Studio replied with err:<code>:<message>."""
