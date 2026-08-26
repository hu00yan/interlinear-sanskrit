#!/usr/bin/env python3
"""Superseded shim — the SA search index moved to a pipeline stage.

The old monolithic public/data/search-index-sa.json (Devanagari-exact keys,
BhG-only coverage) is replaced by the greek-reader-parity sharded index:

    pipeline/stages/80-searchindex/build_search_index.py

which covers ALL 110 catalog works, folds Devanagari AND IAST queries into
one ascii key space ("राम" ≡ "rāma"), includes the Pali corpus, and emits
    public/data/search-index-sa/_meta.json + <letter>.json shards
    public/data/search-index-trans.json
Validated by pipeline/stages/90-qa/check_search_index.py.

This shim keeps the historical command working; it prints where the real
builder lives and delegates to it.
"""
import os
import runpy
import sys

REAL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "pipeline", "stages", "80-searchindex",
                    "build_search_index.py")

print("scripts/build-search-index-sa.py is superseded — delegating to "
      "pipeline/stages/80-searchindex/build_search_index.py", file=sys.stderr)
runpy.run_path(REAL, run_name="__main__")
