# Credits audit — translator/year metadata (作者+年代)

| Metric | Count | Detail |
|---|---|---|
| Catalog works w/ translation/translationZh | 56 refs / 47 works | 40 EN `translation` + 16 ZH `translationZh` blocks |
| Files audited (top-level translator+year) | 69 | trans/*.json (53) + trans-zh/*.json (16) — **all present & non-empty** |
| Gaps found | 4 | bhagavadgita cat=Arnold1885 vs file=Telang1882 · tantrakhyayika & vetalapancavimsati recension notes missing in file · kamasutra "Sir" prefix divergence |
| Gaps fixed | 4 | cat→Telang 1882 SBE8 (per data-audit.md flip); files→"Arthur W. Ryder (Panchatantra/Twenty-Two Goblins, parallel recension)"; cat→"Sir Richard F. Burton…" |
| Post-fix mismatches | **0** | all 56 catalog↔file pairs identical; years numeric everywhere |
| Remaining unknowns | 0 | every translation carries exact year (no era fallbacks needed); 康僧鎧252/那連提耶舍565 keep prior "(trad./debated)" caveats |

Notes: 11 orphaned EN files have valid credits but no catalog wiring yet — Hume Upaniṣads ×10 (isa katha prasna mundaka mandukya aitareya taittiriya chandogya brhadaranyaka kena) + alternate `bhagavadgita-arnold.json` (674 units; catalog serves Telang 700-unit build). Griffith spelled "Ralph T.H." (RV, per REF-NOTES.md) vs "Ralph T. H." elsewhere — intentional per-work docs.
