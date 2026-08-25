# pali-abhidhamma ingest

7 treatises, all 1102 upstream bilara files (`root/pli/ms/abhidhamma/`, sparse-checkout extended): ds 92 · vb 133 · dt 41 · pp 25 · kv 256 · ya 203 · patthana 1032 = **1782 units**; refs mirror bilara stems (`ds 2.1.10`, `ya 10.2.1`, chunk suffix `.N` when >150 segs).
EN translations ABSENT upstream (no `translation/en/*/abhidhamma` tree) → text-only works, catalog `"translation": null` + CC0 bilara root note (bhagavata-skandha pattern); no trans files shipped.
Mātikā/0-comp headings KEPT as content ("Tikamātikä", "1. Kusalattika"); drops limited to bare `…pe…` + short unquoted niṭṭhitā/samatto colophons (487 total; exactly one per kathā in kv). kv "Āmantā." debate replies (808×) kept.
Markup: 328 PTS paragraph cross-refs `(<b>…</b>)` removed whole; 2544 inline `<b>` terms unwrapped; no other tags/entities.
Paṭṭhāna split at matrix/vāra boundaries into part01–03 (3.9/3.2/3.5MB, all ≤8MB); range-file anomaly `patthana2.6-7` handled.
Validation: JSON round-trip ×9 files ✓; catalog unitCount↔files exact ×7 ✓; Dhs opening mātikā spot-check "Kusalā dhammā./Akusalā/Abyākatā" ✓; refs unique ✓.
Commits pushed incrementally: 3e11606 ds · 364a1cd vb · 3608ab9 dt · e842994 pp · 4a85731 kv · 1916130 ya · 05f3250 patthana.
