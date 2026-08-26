#!/usr/bin/env python3
"""90-qa — per-stage validation gate run AFTER emit, BEFORE publish.
--in points at <run_dir>/artifacts.json written by worker.py:
{"stage-name": "artifact-path", ..., "emit": "<out-dir>"}. Fails (exit≠0)
on any violated gate so worker never publishes a bad build."""
import os
import sys

STAGES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STAGES)
import lib  # noqa: E402


def main() -> None:
    args = lib.base_parser("90-qa: validation gates").parse_args()
    manifest = lib.read_json(args.config) if args.config else {}
    lane = lib.adapter_of(args.work, manifest)
    adapter = lib.load_adapter(lane, lib.HOOKS)
    if not hasattr(adapter, "qa"):
        lib.fail(f"adapter {lane} has no qa hook")
    artifacts = lib.read_json(args.inp)
    adapter.qa(args.work, lib.Cfg(manifest, "qa"), artifacts, args.out)


if __name__ == "__main__":
    main()
