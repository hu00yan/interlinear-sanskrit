# pali-sn — Saṃyutta Nikāya QA

Source: .cache-bilara/bilara-data (CC0, Mahāsaṅgīti root + Sujato EN); builder `pipeline/build_pali_sn.py` mirrors `build_pali_nikaya.py` (DN/MN). **1,940 units** / 56 saṃyuttas (3,024 numbered sutta slots; range files `snX.Y-Z` compress peyyāla series → one unit per stem, ref by start number). Key match text↔EN **100%** (segment-exact); unit-level EN coverage **99.90%** — only `sn 40.10.1` (source elision) and `sn 46.165` (Pali-only cross-ref + uddāna) lack EN; per-segment EN 83.0% because Sujato elides repeat formulas inside peyyāla units (Pali kept, cf. DN/MN deviation note). Drops: headings 5,699 · bare-pe 18 · colophons 62 · empty 2. Sub-splits (>150 kept segs): `sn 22.85`, `sn 40.10`, `sn 42.13` (.0/.1). Full rebuild idempotent (byte-identical).

| sam | 1-10 | 11-20 | 21-30 | 31-40 | 41-50 | 51-56 |
|-----|------|-------|-------|-------|-------|-------|
| units | 81/30/25/25/10/15/22/12/14/12 | 25/94/11/39/20/13/31/14/21/12 | 12/160/46/35/10/10/10/10/12/6 | 6/9/27/33/218/31/34/16/2/12 | 10/14/44/11/130/87/55/80/5/10 | 37/24/5/20/74/109 |

Canon-table check against bilara file structure: every saṃyutta spans 1..max contiguously (sn1 Devatā 81 … sn35 248, sn45 180, sn56 Sacca 131 ✓). Spot checks: `sn 1.1` Oghataraṇa (Pali *ogha*, EN "flood") ✓; `sn 56.11` Dhammacakkappavattana (dhammacakka/wheel, no heading residue) ✓.
