#!/usr/bin/env python3
"""80-searchindex — corpus-wide home-search index build (greek-reader
parity). Unlike the per-work stages, this stage reads the WHOLE committed
corpus, so worker.py runs it once per publish rather than per work (its
section is absent from per-work manifests -> auto-skipped there; run it
directly or via `worker.py --stages searchindex ...`).

    python3 stages/80-searchindex/stage.py --in <any> --out <dir> \
        [--work <id-or-ALL>]

Outputs (under --out, which must be the publish root):
    search-index-sa/_meta.json + <letter>.json shards   word index
    search-index-trans.json                             translation snippets

Validation of the BUILT artifacts lives in 90-qa/check_search_index.py.
"""
import os
import sys

STAGES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STAGES)
import lib  # noqa: E402


def main() -> None:
    args = lib.base_parser("80-searchindex: corpus home-search index").parse_args()
    # --out IS the publish root for this stage (directory, like 70-emit)
    out_root = args.out if os.path.isdir(args.out) else \
        os.path.dirname(args.out) or "."
    data_dir = args.inp if os.path.isdir(args.inp) and \
        os.path.exists(os.path.join(args.inp, "catalog.json")) else out_root
    builder = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "build_search_index.py")
    mod = lib.load_builder_module(builder)
    saved_argv = sys.argv[1:]
    sys.argv[1:] = ["--out-root", out_root, "--data-dir", data_dir]
    try:
        mod.main()
    finally:
        sys.argv[1:] = saved_argv


if __name__ == "__main__":
    main()
