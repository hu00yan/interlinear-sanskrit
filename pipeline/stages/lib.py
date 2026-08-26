#!/usr/bin/env python3
"""Shared helpers for pipeline/stages/* scripts (stdlib only).

Stage CLI contract (uniform, see pipeline/ERRORS.md):

    python3 stages/<NN-name>/stage.py --in <path> --out <path> --work <id> \
        [--config <manifest.json>] [--param k=v ...]

  * --in / --out are files for transform stages; --out is a DIRECTORY for
    multi-artifact emit stages.
  * exit 0 = pass; any failure exits non-zero with a one-line message on
    stderr. Soft problems are recorded in the output artifact under
    "warnings" and never abort the run.
  * stages are idempotent: same inputs + config => byte-identical outputs.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def rel(path: str) -> str:
    """Repo-relative display form of a path."""
    return os.path.relpath(path, REPO)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)


def load_builder_module(path: str):
    """Import a legacy builder by file path (dirs like .bhg-work are not
    importable packages). The original module stays untouched; stages wrap
    its functions verbatim so behaviour cannot drift."""
    spec = importlib.util.spec_from_file_location(
        "legacy_" + os.path.splitext(os.path.basename(path))[0], path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.dirname(os.path.abspath(path)))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.pop(0)
    return mod


def base_parser(desc: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=desc)
    p.add_argument("--in", dest="inp", required=True,
                   help="input artifact path")
    p.add_argument("--out", required=True,
                   help="output artifact path (directory for emit stages)")
    p.add_argument("--work", required=True, help="workId from works/<id>.json")
    p.add_argument("--config", help="work manifest JSON path")
    p.add_argument("--repo", default=REPO, help="repo root override")
    return p


def fail(msg: str) -> "None":
    print(f"FATAL [{os.path.basename(sys.argv[0])}] {msg}", file=sys.stderr)
    sys.exit(1)


def adapter_of(work_id: str, manifest: dict) -> str:
    """Adapter lane for a workId: manifest 'adapter' field wins, else a
    small prefix table (new works must declare 'adapter')."""
    if manifest and manifest.get("adapter"):
        return manifest["adapter"]
    table = {"pali-dn": "pali_nikaya", "pali-mn": "pali_nikaya",
             "bhagavata": "bhagavata"}
    if work_id not in table:
        fail(f"no adapter lane for work {work_id!r}; "
             f"declare \"adapter\" in its manifest")
    return table[work_id]


def load_adapter(name: str, hooks_dir: str):
    """Import stages/adapters/<name>.py and return the module."""
    path = os.path.join(hooks_dir, name + ".py")
    if not os.path.exists(path):
        fail(f"adapter {name!r} not found at {rel(path)}")
    spec = importlib.util.spec_from_file_location("stage_adapter_" + name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


HOOKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "adapters")


class Cfg:
    """Merged view of the work manifest section for this stage."""

    def __init__(self, manifest: dict, section: str):
        self.manifest = manifest or {}
        self.section = (self.manifest.get(section) or {}) if section else {}

    def __getitem__(self, k):
        return self.section[k]

    def get(self, k, default=None):
        return self.section.get(k, self.manifest.get(k, default))
