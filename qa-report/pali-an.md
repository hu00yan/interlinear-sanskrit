# pali-an — Aṅguttara Nikāya build report

Built by `pipeline/build_pali_anguttara.py` mirroring `build_pali_nikaya.py` (dn/mn) schema exactly; sparse checkout extended to `root/pli/ms/sutta/an` + `translation/en/sujato/sutta/an` (11 nipātas, 1,408 files each side, key parity verified per file).
Units: **2,035** (= 2,033 bilara key-prefix entries + 2 split sub-units an 3.70.0/.1, an 10.24.0/.1 at X.0 headings); refs `an 1.1`…`an 11.x`; per-nipāta: 449/194/184/278/271/125/101/96/82/212/43.
Alignment: segment-key match **100%** (root/trans sorted keys asserted equal for all 1,408 file pairs; unit ref sets equal). EN coverage of kept segments 88.48% (32,757/37,024) — Sujato's designed peyyāla elisions, kept Pali-only per dn/mn deviation note; no entry fully untranslated.
Drops: headings 4,748 · pe-only 6 · colophons 61 · empty-Pali 4.
Spot-checks: an 1.1 opens "Evaṁ me sutaṁ— ekaṁ samayaṁ bhagavā sāvatthiyaṁ" / "So I have heard"; an 5.77–5.88 present with full content (Anāgata-bhaya/Thera series — not Ādhipateyya as queried); an 10.1 Cetanā ("famous lists") verified; range-unit an 6.170-649 carries the Rāgapeyyāla word list.
Anomaly: nominal canon ~9,557 suttas vs 2,033 units — SC/bilara collapses peyyāla repeat-groups into single ranged entries (`an 6.170-649`), refs kept in SC range form rather than fabricating repeated content.
Incremental: 11 batches (one per nipāta), each committed + pushed with `pull --rebase --autostash` retry loop; catalog appended one work `pali-anguttara-nikaya` 增支部经典 under existing "Pali Canon" group via `update_catalog_nikaya.py`.
