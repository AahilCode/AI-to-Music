"""Command-line interface for the AI-to-Music Copilot."""

import argparse
import json
import sys
import time

from . import transport
from . import actions
from . import ai


def cmd_list_ports(_args):
    inputs, outputs = transport.list_ports()
    print("MIDI inputs (we listen on one of these):")
    for name in inputs:
        print("  - %s" % name)
    print("MIDI outputs (we send on one of these):")
    for name in outputs:
        print("  - %s" % name)


def _open_bridge(args):
    bridge = transport.open_ports(args.cmd_port, args.rsp_port)
    in_name, out_name = bridge.port_names
    print("Connected to FL Studio bridge on '%s'" % in_name)
    return bridge


def cmd_ping(args):
    bridge = _open_bridge(args)
    try:
        ok = 0
        for i in range(args.count):
            start = time.monotonic()
            payload = bridge.request("ping", timeout=args.timeout)
            ms = (time.monotonic() - start) * 1000
            if payload == "pong":
                ok += 1
                print("PONG from FL Studio in %.1f ms (req #%d)" % (ms, i + 1))
            else:
                print("unexpected reply: %r" % payload)
        print("%d/%d pings succeeded" % (ok, args.count))
        return 0 if ok == args.count else 1
    finally:
        bridge.close()


def cmd_send(args):
    bridge = _open_bridge(args)
    try:
        payload = bridge.request(args.command, *args.args, timeout=args.timeout)
        print("ok: %s" % payload)
        return 0
    except transport.BridgeError as e:
        print("FL Studio replied with an error: %s" % e)
        return 1
    finally:
        bridge.close()


def cmd_execute(args):
    try:
        data = json.loads(args.json_string)
    except json.JSONDecodeError as e:
        print("Error: Invalid JSON format: %s" % e)
        return 1

    if "actions" not in data or not isinstance(data["actions"], list):
        print("Error: JSON must contain an 'actions' list.")
        return 1

    bridge = _open_bridge(args)
    try:
        results = actions.execute_batch(data["actions"], bridge)
        _print_summary(results)
        return 0
    except (ValueError, transport.BridgeError) as e:
        print("\nExecution Failed: %s" % e)
        return 1
    finally:
        bridge.close()


def cmd_prompt(args):
    bridge = _open_bridge(args)
    try:
        print("Reading FL Studio project state...")
        channels_payload = bridge.request("get_channels")
        available_channels = [ch.strip() for ch in channels_payload.split(",") if ch.strip()]
        tempo_payload = bridge.request("get_tempo")
        current_tempo = float(tempo_payload)

        print("  - Available channels: %s" % ", ".join(available_channels))
        print("  - Current BPM: %.2f" % current_tempo)

        print("\n[AI] Planning with Groq...")
        start_time = time.monotonic()
        plan = ai.generate_action_plan(args.user_prompt, available_channels, current_tempo)
        ai_duration = time.monotonic() - start_time
        print("[AI] Generated plan in %.2f seconds:" % ai_duration)
        print(json.dumps(plan, indent=2))

        print("\nExecuting actions in FL Studio...")
        results = actions.execute_batch(plan, bridge)
        _print_summary(results)
        return 0

    except (ValueError, transport.BridgeError) as e:
        print("\nError: %s" % e)
        return 1
    finally:
        bridge.close()


def _print_summary(results):
    print("\n--- Execution Summary ---")
    for idx, (act, res) in enumerate(results):
        act_type = act["type"]
        if act_type == "set_tempo":
            print(" [%d] Set tempo to %s BPM" % (idx + 1, act["bpm"]))
        elif act_type == "set_step_pattern":
            print(" [%d] Wrote 4-bar drum pattern to '%s' (steps: %s)" % (idx + 1, act["channel"], act["steps"]))
        elif act_type == "clear_channel":
            print(" [%d] Cleared channel '%s'" % (idx + 1, act["channel"]))
        elif act_type == "record":
            print(" [%d] Armed recording in FL Studio ⏺" % (idx + 1))
        elif act_type == "play":
            print(" [%d] Started playback ▶" % (idx + 1))
        elif act_type == "stop":
            print(" [%d] Stopped playback ⏹" % (idx + 1))
        elif act_type == "play_layered_progression":
            print(" [%d] Recorded Transcendent 4-Bar Multi-Layered Progression ✨🎹" % (idx + 1))
        else:
            print(" [%d] %s -> %s" % (idx + 1, act_type, res))
    print("All %d actions completed successfully!" % len(results))


def main(argv=None):
    parser = argparse.ArgumentParser(description="AI-to-Music Copilot CLI")
    parser.add_argument("--cmd-port", default="Copilot CMD", help="output port name")
    parser.add_argument("--rsp-port", default="Copilot CMD", help="input port name")
    parser.add_argument("--timeout", type=float, default=2.0, help="seconds to wait per response")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    sub.add_parser("list-ports", help="show MIDI ports")

    ping = sub.add_parser("ping", help="SysEx ping/pong")
    ping.add_argument("--count", type=int, default=1)

    send = sub.add_parser("send", help="send raw command")
    send.add_argument("command")
    send.add_argument("args", nargs="*")

    execute = sub.add_parser("execute", help="execute JSON batch")
    execute.add_argument("json_string")

    prompt = sub.add_parser("prompt", help="Natural language AI command")
    prompt.add_argument("user_prompt", help="e.g. 'Make a 140 BPM beat with piano'")

    args = parser.parse_args(argv)
    try:
        if args.subcommand == "list-ports":
            cmd_list_ports(args)
            return 0
        if args.subcommand == "ping":
            return cmd_ping(args)
        if args.subcommand == "send":
            return cmd_send(args)
        if args.subcommand == "execute":
            return cmd_execute(args)
        return cmd_prompt(args)
    except transport.BridgeTimeout as e:
        print("TIMEOUT: %s" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
