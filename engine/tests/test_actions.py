"""Unit tests for Phase 2 action validation and resolution."""

import unittest
from copilot import actions, schema


class FakeBridge:
    def __init__(self, channels_payload="808 Kick, 808 Clap, 808 HiHat, 808 Snare"):
        self.channels_payload = channels_payload
        self.calls = []

    def request(self, command, *args, **kwargs):
        self.calls.append((command, list(args)))
        if command == "get_channels":
            return self.channels_payload
        if command == "get_tempo":
            return "140.00"
        return "ok"


class TestActionEngine(unittest.TestCase):

    def test_validate_tempo_bounds(self):
        # Valid tempo
        self.assertTrue(actions.validate_action({"type": "set_tempo", "bpm": 140}))
        # Invalid tempo (too high)
        with self.assertRaises(ValueError):
            actions.validate_action({"type": "set_tempo", "bpm": 5000})
        # Invalid tempo (too low)
        with self.assertRaises(ValueError):
            actions.validate_action({"type": "set_tempo", "bpm": 2})

    def test_validate_step_bounds(self):
        # Valid step
        self.assertTrue(actions.validate_action({"type": "set_step", "channel": "808 Kick", "step": 0, "value": 1}))
        # Invalid step (> 15)
        with self.assertRaises(ValueError):
            actions.validate_action({"type": "set_step", "channel": "808 Kick", "step": 16, "value": 1})
        # Invalid value (not 0 or 1)
        with self.assertRaises(ValueError):
            actions.validate_action({"type": "set_step", "channel": "808 Kick", "step": 4, "value": 2})

    def test_resolve_channel_by_name(self):
        available = ["808 Kick", "808 Clap", "808 HiHat", "808 Snare"]
        # Case insensitive match
        self.assertEqual(actions.resolve_channel("808 kick", available), 0)
        self.assertEqual(actions.resolve_channel("808 Clap", available), 1)
        # Missing channel
        with self.assertRaises(ValueError):
            actions.resolve_channel("Cowbell", available)

    def test_batch_execution(self):
        bridge = FakeBridge()
        batch = [
            {"type": "set_tempo", "bpm": 140},
            {"type": "set_step_pattern", "channel": "808 Kick", "steps": [0, 4, 8, 12]},
            {"type": "play"}
        ]
        results = actions.execute_batch(batch, bridge)
        self.assertEqual(len(results), 3)
        # Ensure get_channels was called first
        self.assertEqual(bridge.calls[0], ("get_channels", []))


if __name__ == "__main__":
    unittest.main()
