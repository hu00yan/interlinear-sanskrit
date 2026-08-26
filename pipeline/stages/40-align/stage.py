#!/usr/bin/env python3
"""40-align — pair units with their translation refs; emit coverage stats.
Pilots are segment-exact by construction (root/trans share segment keys,
verified in 20-normalize); this stage quantifies EN coverage and freezes it
for the QA gate."""
import os
import sys

STAGES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STAGES)
import lib  # noqa: E402


def main() -> None:
    args = lib.base_parser("40-align: translation alignment stats").parse_args()
    manifest = lib.read_json(args.config) if args.config else {}
    lane = lib.adapter_of(args.work, manifest)
    adapter = lib.load_adapter(lane, lib.HOOKS)
    if not hasattr(adapter, "align"):
        lib.fail(f"adapter {lane} has no align hook (pending migration)")
    adapter.align(args.work, lib.Cfg(manifest, "align"), args.inp, args.out)


if __name__ == "__main__":
    main()
