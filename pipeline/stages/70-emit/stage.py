#!/usr/bin/env python3
"""70-emit — shard/file emission. --out is a DIRECTORY; the adapter writes
final artifacts under it preserving repo-relative layout (e.g.
texts/pali/dn.json). Serialization profiles (separators!) belong to the
adapter and MUST match the shipped files byte-for-byte."""
import os
import sys

STAGES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STAGES)
import lib  # noqa: E402


def main() -> None:
    args = lib.base_parser(
        "70-emit: write final artifacts under --out dir").parse_args()
    manifest = lib.read_json(args.config) if args.config else {}
    lane = lib.adapter_of(args.work, manifest)
    adapter = lib.load_adapter(lane, lib.HOOKS)
    if not hasattr(adapter, "emit"):
        lib.fail(f"adapter {lane} has no emit hook")
    os.makedirs(args.out, exist_ok=True)
    written = adapter.emit(args.work, lib.Cfg(manifest, "emit"),
                           args.inp, args.out)
    print(f"[emit:{args.work}] {len(written)} files: {written[:4]}{' …' if len(written) > 4 else ''}")


if __name__ == "__main__":
    main()
