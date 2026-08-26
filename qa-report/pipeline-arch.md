# pipeline-arch: text processing unified into ONE assembly line

```
sources(.cache-*) ─▶ 10-fetch ─▶ 20-normalize ─▶ 30-tokenize ─▶ 40-align ─▶
50-analyze ─▶ 60-gloss ─▶ 70-emit ─▶ 90-qa ─▶ --apply▶ public/data
worker.py reads works/<id>.json → runs stages → structured log
{stage,status,duration,errors[],artifacts[]} → stops-on-fail | skip-with-log
(ERRORS.md); uniform stage CLI --in/--out/--work, exit≠0 on failure.
```

**Pilot byte-proof** (wrap legacy builders, don't rewrite): pali-dn/mn +
bhagavata via worker = **16/16 outputs sha256-identical** to shipped files,
dry-run AND `--apply`; rerun idempotent. e.g. `dn.json
6b37a3ff7a9d…`, `bhagavata-10.json 41e21a9fc1a4…` unchanged; legacy fns
(load_sutta/split_chunks/parse/tokenize/suffix_refs) imported verbatim.

| backlog builder(s) | target stages | note |
|---|---|---|
| build_morph_dcs.py | 50-analyze `dcs` adapter + emit/qa | PENDING-MIGRATION, owned by diagnosis round (see stages/50-analyze/MORPH-PENDING-MIGRATION.md) |
| fst-port (external Samsaadhanii) | 50-analyze RESERVED | contract frozen in FST-PORT-CONTRACT.md |
| build_glosses.py | 60-gloss | wrap like pilots |
| build_pali_{sn,kn_books,kn2,anguttara,vinaya,abhidhamma,dhammapada}.py | 20→30→40→70 clones of pali_nikaya lane | share one lane module |
| build_{epics,buddhist,rigveda,upanishads,kavya*,translations_sa,translation}.py | same 20→70 shape | per-work manifests + expected counts |
| update_catalog_* / grammar_ref / verify_fixes | 90-qa / sidecars | catalog = derived artifact |

Morph lane untouched by design; `.bhg-work/build_bhagavata.py` still
untracked upstream — commit when adopting that manifest. Logs:
qa-report/logs/<workId>.json.
