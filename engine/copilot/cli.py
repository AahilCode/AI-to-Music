"""Command-line interface for the bridge (Phase 1 & Phase 2).

Run from the engine/ directory:
    python -m copilot.cli list-ports
    python -m copilot.cli ping [--count 20]
    python -m copilot.cli send <command> [args...]
    python -m copilot.cli execute '<json_string>'
"""

import argparse
import json
import sys
import time

from . import transport
from . import actions


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
    print("listening on '%s', sending on '%s'" % (in_name, out_name))
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
                print("PONG from FL Studio in %.1f ms (req #%d)"
                      % (ms, i + 1))
            else:
                print("unexpected reply: %r" % payload)
        print("%d/%d pings succeeded" % (ok, args.count))
        return 0 if ok == args.count else 1
    finally:
        bridge.close()


def cmd_send(args):
    bridge = _open_bridge(args)
    try:
        payload = bridge.request(args.command, *args.args,
                                 timeout=args.timeout)
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
        print("Example of valid JSON:")
        print("  '{\"actions\": [{\"type\": \"set_tempo\", \"bpm\": 140}]}'")
        return 1
        
    if "actions" not in data:
        print("Error: JSON must contain an 'actions' key containing a list of actions.")
        return 1
        
    batch = data["actions"]
    if not isinstance(batch, list):
        print("Error: 'actions' must be a list.")
        return 1
        
    bridge = _open_bridge(args)
    try:
        print("Resolving channel names and validating batch actions...")
        results = actions.execute_batch(batch, bridge)
        print("\n--- Execution Summary ---")
        for idx, (act, res) in enumerate(results):
            act_type = act["type"]
            if act_type == "set_tempo":
                print(" [%d] Set tempo to %s BPM -> OK (%s)" % (idx + 1, act["bpm"], res))
            elif act_type == "set_step_pattern":
                print(" [%d] Wrote drum pattern to '%s' -> OK" % (idx + 1, act["channel"]))
            elif act_type == "set_step":
                print(" [%d] Set step %s to %s on '%s' -> OK" % (idx + 1, act["step"], act["value"], act["channel"]))
            elif act_type == "clear_channel":
                print(" [%d] Cleared channel '%s' -> OK" % (idx + 1, act["channel"]))
            else:
                print(" [%d] Executed %s -> OK (%s)" % (idx + 1, act_type, res))
        print("All %d actions completed successfully!" % len(results))
        return 0
    except (ValueError, transport.BridgeError) as e:
        print("\nExecution Failed: %s" % e)
        return 1
    finally:
        bridge.close()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="AI-to-Music bridge CLI (Phase 1 & Phase 2)")
    parser.add_argument("--cmd-port", default="Copilot CMD",
                        help="output port name (substring match)")
    parser.add_argument("--rsp-port", default="Copilot CMD",
                        help="input port name (substring match)")
    parser.add_argument("--timeout", type=float, default=2.0,
                        help="seconds to wait per response")
    sub = parser.add_subparsers(dest="subcommand", required=True)
    sub.add_parser("list-ports", help="show MIDI ports on this machine")
    
    ping = sub.add_parser("ping", help="SysEx ping/pong with FL Studio")
    ping.add_argument("--count", type=int, default=1)
    
    send = sub.add_parser("send", help="send a raw command")
    send.add_argument("command")
    send.add_argument("args", nargs="*")
    
    execute = sub.add_parser("execute", help="execute a batch of high-level actions")
    execute.add_argument("json_string", help="JSON string representing a list of actions")
    
    args = parser.parse_args(argv)
    try:
        if args.subcommand == "list-ports":
            cmd_list_ports(args)
            return 0
        if args.subcommand == "ping":
            return cmd_ping(args)
        if args.subcommand == "send":
            return cmd_send(args)
        return cmd_execute(args)
    except transport.BridgeTimeout as e:
        print("TIMEOUT: %s" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
