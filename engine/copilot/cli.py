"""Command-line interface for the bridge (Phase 1 test tool).

Run from the engine/ directory:
    python -m copilot.cli list-ports
    python -m copilot.cli ping [--count 20]
    python -m copilot.cli send <command> [args...]
"""

import argparse
import sys
import time

from . import transport


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


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="AI-to-Music bridge CLI (Phase 1)")
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
    args = parser.parse_args(argv)
    try:
        if args.subcommand == "list-ports":
            cmd_list_ports(args)
            return 0
        if args.subcommand == "ping":
            return cmd_ping(args)
        return cmd_send(args)
    except transport.BridgeTimeout as e:
        print("TIMEOUT: %s" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
