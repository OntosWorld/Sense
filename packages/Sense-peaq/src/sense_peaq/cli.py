"""Command-line utilities for the Sense peaq adapter."""

from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence

from sense_ai import ContextMachine, capability, gte

from .publisher import PeaqEventPublisher


def _build_live_transition(machine_id: int):
    machine = ContextMachine(machine_ref=f"peaq:{machine_id}")
    machine.define_capability(
        capability("sense.live.check", requires=[gte("battery.level_pct", 20)])
    )
    machine.observe("battery.level_pct", 80)
    machine.evaluate("sense.live.check")
    machine.observe("battery.level_pct", 10)
    machine.evaluate("sense.live.check")

    transition = machine.last_transition("sense.live.check")
    if transition is None:
        raise RuntimeError("Sense did not produce the expected capability transition")

    return machine, transition


def _verify_live(args: argparse.Namespace) -> int:
    try:
        from dotenv import load_dotenv
        from peaq_os_sdk import PeaqosClient
    except ImportError as exc:
        print(f"ERROR: missing runtime dependency: {exc}", file=sys.stderr)
        return 2

    load_dotenv()

    raw_machine_id = args.machine_id or os.getenv("SENSE_PEAQ_MACHINE_ID")
    if not raw_machine_id:
        print(
            "ERROR: machine ID is required. Pass --machine-id or set "
            "SENSE_PEAQ_MACHINE_ID.",
            file=sys.stderr,
        )
        return 2

    try:
        machine_id = int(raw_machine_id)
    except ValueError:
        print("ERROR: machine ID must be a base-10 integer.", file=sys.stderr)
        return 2

    if machine_id <= 0:
        print("ERROR: machine ID must be a positive integer.", file=sys.stderr)
        return 2

    try:
        client = PeaqosClient.from_env()
    except Exception as exc:
        print(f"ERROR: peaq client configuration failed: {exc}", file=sys.stderr)
        return 2

    wallet_address = getattr(client, "address", None)
    rpc_url = os.getenv("PEAQOS_RPC_URL", "(configured by peaq client)")
    deployment_id = os.getenv("TOKENOMICS_DEPLOYMENT_ID", "(default/legacy configuration)")

    print("peaq client loaded")
    print(f"wallet address: {wallet_address or '(not exposed by client)'}")
    print(f"machine ID: {machine_id}")
    print(f"RPC: {rpc_url}")
    print(f"deployment: {deployment_id}")

    try:
        machine, transition = _build_live_transition(machine_id)
        publisher = PeaqEventPublisher(client, machine_id=machine_id)
    except Exception as exc:
        print(f"ERROR: Sense preflight failed: {exc}", file=sys.stderr)
        return 2

    print("Sense preflight: PASSED")
    print("transition: AVAILABLE -> UNAVAILABLE")

    if not args.yes:
        try:
            answer = input(
                "This will submit a real peaq Activity Event and may spend gas. "
                "Continue? [y/N]: "
            ).strip().lower()
        except EOFError:
            answer = ""

        if answer not in {"y", "yes"}:
            print("Cancelled before transaction submission.")
            return 0

    try:
        result = publisher.publish_transition(
            transition,
            snapshot=machine.snapshot().publishable_view(),
            metadata={"verification": "sense-live-test"},
        )
    except Exception as exc:
        print(f"ERROR: live peaq submission failed: {exc}", file=sys.stderr)
        return 1

    print("Live peaq verification: PASSED")
    print(f"Transaction hash: {result.tx_hash}")
    print(f"Data hash: {result.data_hash_hex}")
    print(f"Network RPC: {rpc_url}")
    print(f"Machine ID: {machine_id}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sense-peaq",
        description="Sense peaq adapter utilities.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    live = subparsers.add_parser(
        "verify-live",
        help="Run preflight checks and submit one real Sense Activity Event.",
    )
    live.add_argument(
        "--machine-id",
        help="peaq machine ID. Defaults to SENSE_PEAQ_MACHINE_ID.",
    )
    live.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip the interactive transaction confirmation.",
    )
    live.set_defaults(handler=_verify_live)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
