#!/usr/bin/env python3
"""50-analyze — morphology adapters: dcs | fst-samsaadhanii | fst-port.

STATUS (2026-08-26):
  * dcs              PENDING-MIGRATION — pipeline/build_morph_dcs.py is
                     mid-diagnosis in another workstream; its step mapping
                     lives in MORPH-PENDING-MIGRATION.md. DO NOT EDIT that
                     builder from the pipeline refactor.
  * fst-samsaadhanii RESERVED — legacy .cache-fst-sa evaluation lane, not a
                     stage yet.
  * fst-port         RESERVED for the user's optimized Samsaadhanii port.
                     The binary drops into this stage without rework; the
                     exact I/O contract it must satisfy is
                     FST-PORT-CONTRACT.md.

Until an adapter lands here this stage is invoked only with
--adapter <name>; without one it fails loudly (never silently passes)."""
import argparse
import os
import sys

STAGES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STAGES)
import lib  # noqa: E402

ADAPTERS = {
    "dcs": None,               # PENDING-MIGRATION (build_morph_dcs.py)
    "fst-samsaadhanii": None,  # RESERVED
    "fst-port": None,          # RESERVED (contract in FST-PORT-CONTRACT.md)
}


def main() -> None:
    ap = lib.base_parser("50-analyze: morphology adapter lane")
    ap.add_argument("--adapter", choices=sorted(ADAPTERS), required=True)
    args = ap.parse_args()
    if ADAPTERS[args.adapter] is None:
        lib.fail(f"adapter {args.adapter} not migrated yet "
                 f"(see stages/50-analyze/*.md); manifest must keep "
                 f"\"analyze\" disabled for now")


if __name__ == "__main__":
    main()
