# Corpus parse-display scorecard — all 110 works (:4176, first unit page each)
Gate: `node tests/corpus-scorecard.mjs` → corpus-scorecard.csv + assets/corpus-scorecard.json.
Per work M1 maxRows(=1 collapsed) · M2 dupRows · M3 cjkLeaks · M4 m4Bad · M5 glossMax · EXP chip round-trip + carded% (strict-hit proxy), densityPx. Grade D ⇒ any display red; else A/B/C by carded%.

## Result: **A=27 B=18 C=65 D=0** · median carded% 32.3
Display reds before fix: 2/110 (`pali-abhidhamma-ya`, `-patthana`, EXP `expand 1→1`).
Root cause (src/render.ts registerCol): columns register while DETACHED (parseCards runs pre-attach), so the
synchronous `length>64 → isConnected` prune discarded freshly pushed columns wherever one form repeats >64×/page;
their 「另有 N 解」 chip expanded every OTHER instance of the form while staying collapsed itself (forensics:
click → glob=49 cols expanded, clicked col rowsNow=1). Fix = deferred coalesced macrotask prune (`queueColPrune`);
re-measured expOk ✓ on both; parse-audit ALL GREEN; tsc ✓ build ✓.

WORST 10 (all data-bound, zero display reds): pali-patisambhidamagga 6.0% · pali-vinaya-bi 6.1% ·
pali-anguttara-nikaya 6.3% · pali-vinaya-cv 6.5% · pali-theragatha 7.1% · pali-vinaya-pc 7.1% ·
pali-abhidhamma-patthana 7.3% (30 350 tok/page) · pali-buddhavamsa 7.6% · pali-therigatha 7.9% · pali-vinaya-pvr 8.2%

Pattern analysis:
- Sparse data dominates the bad picture (65/110 <50% carded): ENTIRE Pali Canon 6–21% (no pi morph shards);
  Sanskrit laggards are Upaniṣads/Rigveda/darśana-sūtras (13–39%) — honest empty columns per R4 gate + 覆盖有限 note → DATA lane, not UI.
- Display regressions: 0 after fix — maxRows=1 everywhere, dupRows=0, cjkLeaks=0, m4Bad=0, glossMax≤121,
  EXP ok ×110 (chips up to 1 634/page).
- Compound-heavy mega-prose (Yamaka 393 tok/unit, Paṭṭhāna 1 012) broke only the expansion registry (fixed);
  remaining density outliers (27k/16k px) are source unit segmentation → pipeline concern.

display-green count 110/110, honest-gap count 65 (listed in CSV grade=C, carded%<50)
