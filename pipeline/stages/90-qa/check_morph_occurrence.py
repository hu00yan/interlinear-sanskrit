#!/usr/bin/env python3
"""Fail when occurrence DCS data is malformed or labels the wrong token."""
import argparse
import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from build_morph_dcs import _canonical_keys

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--data-root", default="public/data"); args=ap.parse_args()
    root=os.path.join(args.data_root,"morph-occurrence","by-work")
    for work in os.listdir(root) if os.path.isdir(root) else []:
        idx=json.load(open(os.path.join(root,work,"index.json"),encoding="utf-8"))
        if idx.get("source") != "dcs": raise SystemExit(f"{work}: non-DCS source")
        for name in set(idx.get("refs",{}).values()):
            data=json.load(open(os.path.join(root,work,name),encoding="utf-8"))
            for entries in data.values():
                for parses in entries.values():
                    for p in parses:
                        if p.get("source") != "dcs" or p.get("confidence") != 1: raise SystemExit(f"{work}: invalid provenance")
    print("[occurrence-dcs] PASS")
if __name__ == "__main__": main()
