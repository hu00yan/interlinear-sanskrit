# pipeline/stages — text processing as ONE assembly line

    sources ─▶ 10-fetch ─▶ 20-normalize ─▶ 30-tokenize ─▶ 40-align ─▶
              50-analyze ─▶ 60-gloss ─▶ 70-emit ─▶ 90-qa ─▶ publish

* One idempotent script per stage: `stages/<NN-name>/stage.py --in <path>
  --out <path> --work <id> --config <manifest>`; exit ≠0 on failure.
  (`--out` is a directory for 70-emit; 90-qa takes `<run>/artifacts.json`.)
* Work-level wiring lives in `../works/<workId>.json`: declared sources,
  per-stage enable/params, expected counts for the QA gate.
* Run everything: `python3 pipeline/worker.py pali-dn pali-mn bhagavata`
  (`--apply` publishes to public/data after QA passes).
* Failure policy: `../ERRORS.md`. Morph lane status:
  `50-analyze/MORPH-PENDING-MIGRATION.md`; reserved FST adapter:
  `50-analyze/FST-PORT-CONTRACT.md`.
* Legacy builders are WRAPPED, not rewritten — behaviour lives in
  `adapters/<lane>.py` importing the original modules verbatim.
