# build_morph_dcs.py → stage mapping (PENDING-MIGRATION)

⚠️ `pipeline/build_morph_dcs.py` and `public/data/morph/**` are owned by an
active diagnosis workstream — the pipeline refactor does NOT touch them.
This note records where its steps will land once that round lands, so the
future migration is a mechanical wrap (like the two pilots), not a rewrite.

| legacy step (function) | future stage | notes |
|---|---|---|
| `.cache-dcs*/<Work>/*.conllu` presence + DCS_EXTRA_SRC resolution | 10-fetch | add per-tree checksum sidecars; retry policy already external (`qa-report/dcs-retry.md`) |
| `conllu_analyses()` row parsing, `_strip_apostrophes`, avagraha handling | 20-normalize | CoNLL-U → canonical analysis records |
| `map_pos` / `map_feats` UD→site tag vocabulary; `form_keys`/`_canonical_keys` slp1 keying | 30-tokenize | keys MUST stay `[a-z~]+` and match client `canonicalKeysFor` |
| sandhi-fusion span composition gated on `site_key_allowlist` | 40-align | "align" here = surface-token ↔ analysis-row correspondence |
| `merge()` (existing parses first, deduped append), `load_existing` | 50-analyze | this becomes the `dcs` adapter beside `fst-port` (see FST-PORT-CONTRACT.md) |
| `emit_shards`, `emit_surface_index`, `emit_surface_slices` | 70-emit | byte-format freeze: compact JSON, slice bucketing must mirror src/api.ts DEV_SLICE |
| `validate`, `spot_check`, `spot_check_new`, idempotence probe | 90-qa | second-pass new_keys=0 assertion becomes a standing gate |

## What changes when the current diagnosis round lands

1. Wrap only — functions move behind an adapter module; main() stays runnable
   until parity is proven (same hash proof as the pilots).
2. The merge target (`public/data/morph`) gains a manifest
   (`pipeline/works/morph-sa.json`) declaring shards + surface slices as
   publish artifacts.
3. The `fst-port` adapter (external Samsaadhanii binary) merges through the
   SAME 70-emit path with provenance stripped from shipped shards — no
   pipeline rework needed (FST-PORT-CONTRACT.md).
