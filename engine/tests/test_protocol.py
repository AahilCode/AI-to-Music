"""Unit tests for the SysEx protocol + bridge logic.

Pure Python, no MIDI hardware, no FL Studio needed:
    cd engine && python -m unittest discover -s tests -t .
"""

import unittest

from copilot import protocol
from copilot.transport import _Bridge


class ProtocolTest(unittest.TestCase):
    def test_request_roundtrip(self):
        wire = protocol.encode_request(3, "set_tempo", "145")
        self.assertEqual(wire[0], 0xF0)
        self.assertEqual(wire[-1], 0xF7)
        decoded = protocol.decode_message(wire)
        self.assertEqual(decoded, {"direction": "request", "req_id": 3,
                                   "command": "set_tempo", "args": ["145"]})

    def test_response_roundtrip(self):
        wire = protocol.encode_response(9, "ok", "pong")
        decoded = protocol.decode_message(wire)
        self.assertEqual(decoded, {"direction": "response", "req_id": 9,
                                   "status": "ok", "payload": "pong"})

    def test_error_response_keeps_colons(self):
        wire = protocol.encode_response(1, "err", "unknown_command:foo")
        decoded = protocol.decode_message(wire)
        self.assertEqual(decoded["status"], "err")
        self.assertEqual(decoded["payload"], "unknown_command:foo")

    def test_all_data_bytes_are_7bit(self):
        # SysEx data bytes must be < 0x80 or MIDI drivers mangle them.
        wire = protocol.encode_request(1, "ping")
        for byte in wire[1:-1]:
            self.assertLess(byte, 0x80)

    def test_rejects_non_ascii(self):
        with self.assertRaises(protocol.ProtocolError):
            protocol.encode_request(1, "set_name", "café")

    def test_rejects_oversize_payload(self):
        with self.assertRaises(protocol.ProtocolError):
            protocol.encode_request(1, "x" * 300)

    def test_rejects_bad_req_id(self):
        for bad in (0, 127, 999):
            with self.assertRaises(protocol.ProtocolError):
                protocol.encode_request(bad, "ping")

    def test_rejects_foreign_sysex(self):
        with self.assertRaises(protocol.ProtocolError):
            protocol.decode_message(bytes((0xF0, 0x41, 0x10, 0x42, 0xF7)))

    def test_tolerates_missing_framing(self):
        # FL may hand us msg.sysex with or without F0/F7 — accept both.
        wire = protocol.encode_request(5, "ping")
        self.assertEqual(protocol.decode_message(wire[1:-1])["req_id"], 5)


class FakePort:
    """Pretends to be a mido port (records sends, replays queued input)."""

    def __init__(self, name):
        self.name = name
        self.sent = []
        self.incoming = []

    def send(self, msg):
        self.sent.append(msg)

    def poll(self):
        return self.incoming.pop(0) if self.incoming else None


class FakeSysexMsg:
    def __init__(self, data):
        self.type = "sysex"
        self.data = data


class BridgeTest(unittest.TestCase):
    def test_request_matches_response_by_id(self):
        out, inp = FakePort("out"), FakePort("in")
        bridge = _Bridge(out, inp, sysex_factory=FakeSysexMsg)
        # Queue a STALE response (wrong id) then the correct one.
        inp.incoming.append(FakeSysexMsg(
            protocol.encode_response(99, "ok", "stale")[1:-1]))
        inp.incoming.append(FakeSysexMsg(
            protocol.encode_response(1, "ok", "pong")[1:-1]))
        self.assertEqual(bridge.request("ping", timeout=1.0), "pong")
        self.assertEqual(len(out.sent), 1)  # exactly one SysEx sent

    def test_ignores_non_sysex_traffic(self):
        out, inp = FakePort("out"), FakePort("in")
        bridge = _Bridge(out, inp, sysex_factory=FakeSysexMsg)

        class NoteMsg:
            type = "note_on"

        inp.incoming.append(NoteMsg())
        inp.incoming.append(FakeSysexMsg(
            protocol.encode_response(1, "ok", "pong")[1:-1]))
        self.assertEqual(bridge.request("ping", timeout=1.0), "pong")

    def test_error_response_raises(self):
        from copilot.transport import BridgeError
        out, inp = FakePort("out"), FakePort("in")
        bridge = _Bridge(out, inp, sysex_factory=FakeSysexMsg)
        inp.incoming.append(FakeSysexMsg(
            protocol.encode_response(1, "err", "unknown_command:bogus")
            [1:-1]))
        with self.assertRaises(BridgeError):
            bridge.request("bogus", timeout=1.0)

    def test_timeout_when_fl_silent(self):
        from copilot.transport import BridgeTimeout
        bridge = _Bridge(FakePort("out"), FakePort("in"), sysex_factory=FakeSysexMsg)
        with self.assertRaises(BridgeTimeout):
            bridge.request("ping", timeout=0.05)


if __name__ == "__main__":
    unittest.main()
