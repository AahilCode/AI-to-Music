"""MIDI transport: carries protocol messages between engine and FL Studio."""

import time
from . import protocol


class BridgeTimeout(TimeoutError):
    """No matching response arrived before the deadline."""


class BridgeError(Exception):
    """FL Studio replied with err:<code>:<message>."""


def open_ports(cmd_port_name="Copilot CMD", rsp_port_name="Copilot CMD"):
    """Open the real virtual-MIDI ports."""
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
    """Return (inputs, outputs) available on this machine."""
    import mido
    return mido.get_input_names(), mido.get_output_names()


def _match(available, wanted, kind):
    for name in available:
        if wanted in name:
            return name
    raise SystemExit(
        "Could not find %s MIDI port containing %r.\n"
        "Available %s ports: %s" % (kind, wanted, kind, available))


def _mido_sysex_factory(data):
    import mido
    return mido.Message("sysex", data=data)


class _Bridge:
    """Request/response client over virtual MIDI."""

    def __init__(self, out_port, in_port, sysex_factory=None):
        self._out = out_port
        self._in = in_port
        self._make_sysex = sysex_factory or _mido_sysex_factory
        self._next_id = 0

    @property
    def port_names(self):
        return (getattr(self._in, "name", "?"),
                getattr(self._out, "name", "?"))

    def send_raw_midi(self, msg):
        """Send a standard MIDI message (Note On, Note Off, etc.) directly to FL Studio."""
        self._out.send(msg)

    def request(self, command, *args, timeout=2.0):
        """Send one SysEx command, wait for the matching response."""
        self._next_id = (self._next_id % protocol.MAX_REQ_ID) + 1
        req_id = self._next_id
        wire = protocol.encode_request(req_id, command, *args)
        self._send_sysex(wire)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BridgeTimeout(
                    "no response to '%s' (req #%d) within %.1fs." % (command, req_id, timeout))
            msg = self._recv_sysex(timeout=remaining)
            if msg is None:
                continue
            try:
                decoded = protocol.decode_message(msg)
            except protocol.ProtocolError:
                continue
            if (decoded["direction"] != "response"
                    or decoded["req_id"] != req_id):
                continue
            if decoded["status"] == "ok":
                return decoded["payload"]
            raise BridgeError(decoded["payload"])

    def close(self):
        for port in (self._in, self._out):
            close = getattr(port, "close", None)
            if callable(close):
                close()

    def _send_sysex(self, wire: bytes):
        self._out.send(self._make_sysex(wire[1:-1]))

    def _recv_sysex(self, timeout):
        msg = self._in.poll()
        if msg is None:
            time.sleep(0.005)
            return None
        if msg.type != "sysex":
            return None
        return bytes((protocol.SYSEX_START, *msg.data,
                      protocol.SYSEX_END))
