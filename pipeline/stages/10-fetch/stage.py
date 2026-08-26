#!/usr/bin/env python3
"""10-fetch — verify declared sources exist, byte-for-byte, BEFORE any
transform runs. No network in the default path: sources are repo-local
caches (.cache-*); a `fetch:` command in a source declaration is executed
only with --allow-fetch (retry: 3 attempts, exponential backoff 2/8/30s,
final failure = stage failure).

Source kinds (manifest fetch.sources[]):
  {"name","kind":"file", "path"}                       single file
  {"name","kind":"tree", "base", "glob",
   "expect_files":N}                                   glob under base

Integrity: sha256 sidecars live in pipeline/works/checksums/<workId>-<name>.sha256
("<sha256>  <relpath>" lines, relpath relative to base / '-' for file kind).
Default mode VERIFIES against them; --record-checksums (re)writes them.
A missing sidecar passes with a warning in "unchecked" (bootstrap), unless
manifest fetch.require_checksums is true.
"""
import argparse
import glob as globmod
import json
import os
import subprocess
import sys
import time

STAGES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STAGES)
import lib  # noqa: E402


def sidecar_path(work: str, name: str) -> str:
    return os.path.join(lib.REPO, "pipeline", "works", "checksums",
                        f"{work}-{name}.sha256")


def run_fetch_cmd(cmd: str, errors: list) -> bool:
    for attempt, delay in enumerate((0, 2, 8, 30)):
        if delay:
            time.sleep(delay)
        rc = subprocess.call(cmd, shell=True, cwd=lib.REPO)
        if rc == 0:
            return True
        errors.append(f"attempt {attempt + 1} failed rc={rc}: {cmd}")
    return False


def verify_source(work, src, record, unchecked, mismatches, missing):
    name, kind = src["name"], src["kind"]
    sc = sidecar_path(work, name)
    if kind == "file":
        path = os.path.join(lib.REPO, src["path"])
        if not os.path.exists(path):
            missing.append(f"{name}: source file absent ({src['path']})")
            return {"name": name, "kind": kind, "files": 0,
                    "verified": False}
        entries = {"-": path}
    else:
        base = os.path.join(lib.REPO, src["base"])
        files = sorted(globmod.glob(os.path.join(base, src["glob"])))
        exp = src.get("expect_files")
        if exp is not None and len(files) != exp:
            missing.append(f"{name}: {len(files)} files != expect_files {exp}")
        entries = {os.path.relpath(f, base): f for f in files}
    want = {}
    if os.path.exists(sc):
        for line in open(sc, encoding="utf-8"):
            line = line.strip()
            if line:
                h, relp = line.split(None, 1)
                want[relp.strip()] = h
    elif record:
        pass
    else:
        unchecked.append(name)
        if src.get("require_checksum"):
            missing.append(f"{name}: checksums sidecar absent")
    got = {relp: lib.sha256_file(p) for relp, p in entries.items()}
    if record:
        os.makedirs(os.path.dirname(sc), exist_ok=True)
        with open(sc, "w", encoding="utf-8") as fh:
            for relp in sorted(got):
                fh.write(f"{got[relp]}  {relp}\n")
        return {"name": name, "kind": kind, "files": len(entries),
                "recorded": sc}
    bad = [r for r in sorted(set(got) | set(want))
           if got.get(r) != want.get(r)]
    if bad:
        mismatches.append(f"{name}: {len(bad)} changed/missing e.g. {bad[:3]}")
    return {"name": name, "kind": kind, "files": len(entries),
            "verified": not bad}


def main() -> None:
    ap = lib.base_parser("10-fetch: source presence + checksum verification")
    ap.add_argument("--record-checksums", action="store_true")
    ap.add_argument("--allow-fetch", action="store_true")
    args = ap.parse_args()
    manifest = lib.read_json(args.config) if args.config else {}
    cfg = lib.Cfg(manifest, "fetch")
    sources = cfg.get("sources") or []
    if not sources:
        lib.fail(f"manifest for {args.work} declares no fetch.sources")

    errors, unchecked, mismatches, missing = [], [], [], []
    if args.allow_fetch:
        for src in sources:
            if src.get("fetch") and not run_fetch_cmd(src["fetch"], errors):
                lib.fail(f"source {src['name']} fetch failed after retries")
    report = {"workId": args.work, "mode": "record" if args.record_checksums
              else "verify",
              "sources": [verify_source(args.work, s, args.record_checksums,
                                        unchecked, mismatches, missing)
                          for s in sources],
              "warnings": [f"no sidecar, unchecked: {n}" for n in unchecked],
              "errors": errors}
    if mismatches or missing:
        report["errors"] += mismatches + missing
        lib.write_json(args.out, report)
        lib.fail("; ".join((mismatches + missing)[:4]))
    lib.write_json(args.out, report)
    print(f"[fetch:{args.work}] {len(report['sources'])} sources "
          f"{'recorded' if args.record_checksums else 'verified'}"
          + (f" ({len(unchecked)} unchecked)" if unchecked else ""))


if __name__ == "__main__":
    main()
