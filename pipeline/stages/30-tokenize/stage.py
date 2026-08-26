#!/usr/bin/env python3
"""30-tokenize — unit segmentation: canonical records -> display units with
ref + words[] (+ optional daṇḍa bounds). Unit ceilings and split rules come
from the legacy builder functions via the work's adapter."""
import os
import sys

STAGES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STAGES)
import lib  # noqa: E402


def main() -> None:
    args = lib.base_parser("30-tokenize: segment into units").parse_args()
    manifest = lib.read_json(args.config) if args.config else {}
    lane = lib.adapter_of(args.work, manifest)
    adapter = lib.load_adapter(lane, lib.HOOKS)
    if not hasattr(adapter, "tokenize"):
        lib.fail(f"adapter {lane} has no tokenize hook (pending migration)")
    adapter.tokenize(args.work, lib.Cfg(manifest, "tokenize"),
                     args.inp, args.out)


if __name__ == "__main__":
    main()
