# Pali DPD morphology ingest — Pass A shipped — 2026-08-26

**Shipped.** `pipeline/stages/50-analyze/pali_dpd.py` builds `public/data/morph-pali/**` (schema mirrors `morph/**`, plus `_provenance` top-level on every file: `{source:"dpd", license:"CC BY-NC-SA 4.0", upstream:"digitalpalidictionary/dpd-db v0.4.20260728"}`). Source: dpd.db 2.29 GB SQLite (`dpd_headwords` 89,280; `lookup` reverse index 1,281,569) + `deconstructor_output.json` 99.9 MB — cached in `.cache-dpd/` (gitignored).

**Key normalization (documented choice):** corpus ṁ (U+1E41) AND DPD ṃ (U+1E43) both fold to ṃ → lowercase-SLP1 shard key (`cakkaṁva`≡`cakkaṃva`→`cakkamva`); punctuation stripped from keys, kept in `_surface` slices; long/short vowels collide per house slp1 convention.

**Pass A scope:** flat inflections only — feats = gender (m./f./n.), verb tense from DPD pos (pres./aor./…), person+number when the headword's grammar line spells it ("aor 2nd pl"); NO inflection_templates expansion (Pass B). Compound fallback: exact full-form deconstructor matches whose EVERY member hits lookup → `m` chains like the Sanskrit shards; partial splits dropped (explicit nulls stay null).

**Coverage (full corpus, 2,767,903 tokens / 36 works):** **88.9%** token-weighted (94,099/145,022 distinct keys via lookup + 30,529 more via deconstructor). Worst: patthana 76.3%, abhidhamma-dt 80.4%, paṭisambhidāmagga 81.0%; best: udāna 96.3%. vs scorecard carded% baselines (6.0–14.7% pali works, e.g. dhp 14.1→~90% expected, mn 10.4%, an 6.3%) — expected uplift is roughly ×6–8 where display density allows.

**QA gate** `stages/90-qa/check_morph_pali.py` (wired into worker.py post-publish, self-skips when absent): shard shape + non-empty analyses + provenance on every file; sampled per-work coverage floors (overall ≥20%, per-work ≥5%; measured PASS at 93.4%/84.3%); ṁ↔ṃ swap probes must hit identically (200/200).

**Loader switch needed (do NOT ship UI yet):** src/api.ts hardcodes `data/morph/`; roman path also can't pass surfaceKeyTrusted (punctuation kept, ā≠a mismatch). Minimal diff documented in `pipeline/stages/50-analyze/PALI-LOADER-SWITCH.md` (~6 lines across api.ts/translit.ts/main.ts).

**License ⚠️ CC BY-NC-SA 4.0:** derived shards bind to BY + NC + SA — site MUST display DPD attribution and stay non-commercial; needs project-owner sign-off before the loader switch ships these publicly. Watch UD_Pali-PaliCanon (CC BY-SA, no NC) as replacement lane.
