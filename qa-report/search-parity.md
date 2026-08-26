# search-parity (home full-text, greek-reader port) — 2026-08-26
- Diff→closed: word-index was BhG-only/Deva-exact → now ALL 110 works, IAST⇄Devanagari one-key fold (`rāma`≡`राम`, house-mandatory), Pali roman searchable, sandhi probe रामः→राम; added greek "In translations:" snippets with <mark>; title/titleZh filter untouched.
- Index: `search-index-sa/` 565,144 forms / 110 works in 22 letter shards max 4.4MB (lazy) + `search-index-trans.json` 42,821 snips / 51 works, 4.6MB; old monolith deleted.
- Bench (Chromium :4176, keystroke→render incl. 60ms debounce): rāma cold 101ms · राम warm 94ms · धर्मक्षेत्रे cold-d 94ms · dhammo warm 94ms · arjuna trans-cold 109ms.
- Gate `stages/90-qa/check_search_index.py`: G1 coverage 110/110 OK · G2 dual-script fold OK · G3 5 spot probes (incl. Devanagari + Pali) OK · G5 trans OK; wired into `worker.py --apply`.
- Regression: tests/search-parity.mjs 11/11 PASS · parse-audit.mjs ALL GREEN · zh/IAST title search green · pali toggle unaffected. Known pre-existing fail: untracked bilingual-titles-verify.mjs B1 stale `[data-start-card]` selector (repro'd without my changes).
