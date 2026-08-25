# QA: DCS → site morphology shards — 2026-08-25

**Verdict: SUCCESS.** `pipeline/build_morph_dcs.py` merged 11-work DCS CoNLL-U (1,585,450 word tokens) into `public/data/morph/`: shards 8,265 → **124,298 keys, 14.8 MB** (letter-sharded as before); `_surface_index.json` rebuilt corpus-wide: **322,300 tokens, 13.2 MB**; idempotence verified (2nd pass adds 0 keys).

## Per-work resolution (site tokens → index → shard)

| work | % | | work | % |
|---|---|---|---|---|
| ramayana | 95.8 | | manusmrti | 94.6 |
| meghaduta | 95.5 | | arthasastra | 94.3 |
| mahabharata | 95.3 | | kamasutra | 94.1 |
| hitopadesa | 94.9 | | kiratarjuniya | 93.6 |
| tantrakhyayika | 92.4 | | buddhacarita | 91.7 |

All 11 ≥90%. Bonus spill-over on uncovered works: bhagavadgita 95.8% (was 93.5), pancatantra 93.6, lalitavistara 87.7, raghuvamsa 88.8, sisupalavadha 87.3, rigveda ~85 (Vedic forms vs classical DCS).

## Tag mapping + anomalies
- UPOS→{noun,verb,part,indecl}: NOUN/ADJ/NUM→noun; VERB/AUX Fin(UD omits VerbForm=Fin — bug found+fixed)→`verb` with lakāra/person/number/pada in Devanagari Samsaadhanii style (`लङ्;प्रथम;बहु`); Part/Gdv/Inf→part; Conv→indecl; PRON/DET→part (BhG precedent); ADV/PART/CONJ/SCONJ/ADP/INTJ→indecl. Feats: case=1–7 digits, पुं/स्त्री/नपुं, एक/द्वि/बहु; unmapped extras verbatim (`Cpd`, `s`). Old BhG entries kept first per key; exact-dup dedupe skipped 1.44M.
- **Raghuvaṃśa/Śiśupālavadha/Pañcatantra absent from DCS mirror** — covered only via shared vocabulary (87–94%), stay uncovered for dedicated parses.
- Size guard: shards under 15MB & lazy-loaded per letter (largest a.json 2.4MB) — no split needed. `_surface_index.json` is one fixed-name upfront fetch (13.2MB raw, ≈3–4MB gzipped): minimal loader change IF needed later = slice it to `morph/_surface/<letter>.json` and have `api.ts surfaceKey()` fetch only needed slices; NOT done (src/** read-only).
- Spot-checked 15 analyses by eye (e.g. अबध्नन्→√bandh impf 3pl, राजा→राजन् nom sg, कर्तव्यं gerundive) — all sound; residual DCS lemma quirks kept verbatim.
