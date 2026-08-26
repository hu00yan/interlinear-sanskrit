#!/usr/bin/env python3
"""60-gloss — dictionary linkage (Monier-Williams glosses onto lemmas).
PENDING-MIGRATION: pipeline/build_glosses.py wraps to this slot. Invoking
it before migration fails loudly; manifests keep \"gloss\" disabled."""
import os
import sys

STAGES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STAGES)
import lib  # noqa: E402


def main() -> None:
    args = lib.base_parser("60-gloss: dictionary linkage").parse_args()
    manifest = lib.read_json(args.config) if args.config else {}
    lane = lib.adapter_of(args.work, manifest)
    adapter = lib.load_adapter(lane, lib.HOOKS)
    if not hasattr(adapter, "gloss"):
        lib.fail(f"adapter {lane} has no gloss hook "
                 f"(pending migration of build_glosses.py)")


if __name__ == "__main__":
    main()
