# Pipeline error policy (pipeline/ERRORS.md)

Every stage is a subprocess `stages/<NN-name>/stage.py --in <path> --out
<path> --work <id> [--config manifest.json]`; **exit 0 = pass, exit ≠0 =
fail**. The worker (`pipeline/worker.py`) records every stage in a
structured log `{stage,status,duration_ms,errors[],warnings[],artifacts[]}`
(plus `reason` when skipped) at `qa-report/logs/<workId>.json`.

## Abort vs log-and-skip

| situation | class | behaviour |
|---|---|---|
| source file missing / checksum mismatch / count ≠ expect_files | ABORT | 10-fetch exits ≠0; worker stops the work's chain (on_fail=abort default), publishes nothing |
| root↔translation key mismatch, missing sutta file | ABORT | normalize exits ≠0 (same as legacy builders' SystemExit) |
| QA gate violated (counts, coverage, spot checks, refs) | ABORT | 90-qa exits ≠0; run dir outputs are NEVER published |
| per-item soft defect: empty verse, non-IAST token dropped, duplicate-ref recension variant | LOG-AND-SKIP | item skipped with reason recorded in the stage artifact's `warnings[]` + log; build continues (matches legacy WARN-print behaviour) |
| stage not enabled in manifest (analyze, gloss …) | SKIP-WITH-LOG | `{status:"skipped", reason}` in the log; chain continues on last good artifact |
| stage fails with `"on_fail": "skip"` in its manifest section | FAILED-SKIP | logged as failed, chain continues; publish still requires qa to have passed |

Rule of thumb: **anything that would corrupt output data aborts; anything
that only loses one item logs-and-skips — but every skipped item must be
counted somewhere reachable from qa-report** (artifact warnings → structured
log). A silent skip is a bug.

## Idempotence & publishing

Stages are pure functions of (input artifact, manifest): re-running yields
byte-identical artifacts (proven for both pilots, see
qa-report/pipeline-arch.md). Outputs land in `.pipeline-run/<workId>/out/`
preserving repo-relative layout; they reach `public/data/` ONLY via
`worker.py --apply` after 90-qa passes.
