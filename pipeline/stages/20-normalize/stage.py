#!/usr/bin/env python3
"""20-normalize — script/encoding normalization + source-format parsing
into a canonical per-work record stream. Adapter dispatch on --work;
see pipeline/ERRORS.md for the abort vs log-and-skip policy."""
import os
import sys

STAGES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STAGES)
import lib  # noqa: E402


def main() -> None:
    args = lib.base_parser(
        "20-normalize: parse sources into canonical records").parse_args()
    manifest = lib.read_json(args.config) if args.config else {}
    lane = lib.adapter_of(args.work, manifest)
    adapter = lib.load_adapter(lane, lib.HOOKS)
    if not hasattr(adapter, "normalize"):
        lib.fail(f"adapter {lane} has no normalize hook (pending migration)")
    adapter.normalize(args.work, lib.Cfg(manifest, "normalize"),
                      args.inp, args.out)


if __name__ == "__main__":
    main()
