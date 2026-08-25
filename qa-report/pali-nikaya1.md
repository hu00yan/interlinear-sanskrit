# Pali Nikāya 1 ingest — DN + MN (bilara-data, CC0)
- DN: all 34 suttas / 3 vaggas → **178 units**; MN: all 152 suttas / 3 paṇṇāsas (50/50/52) → **221 units**; text↔trans refs identical.
- Split convention: suttas >150 kept segments subdivide at canonical `X.0` section headings (min chunk 60), hard cap ~180 segs at parent-numbering edges; ordinal sub-index from 0 (`dn N.0…`).
- Drops: headings (0-component; DN 484 + MN 350), bare `…pe…` (20), colophons incl. internal enders like "Cūḷasīlaṁ niṭṭhitaṁ." (DN 72 + MN 196); mn65 "niṭṭhitacīvaro" narrative verified kept.
- DEVIATION: Sujato's empty-segment repeat formulas (~12–15%) KEPT to preserve root text — SC renders them Pali-only too; EN coverage DN 87.9%, MN 85.2% vs structural key-match 100% (key sets verified equal per sutta).
- Range segment ids (`mn10:18-23.1`, `dn10:1.12.1-1.27`) sorted by start components; alignment stays segment-exact.
- Spot checks pass: dn 1 evaṁ-me-sutaṁ Brahmajāla opening, dn 22 full satipaṭṭhāna pabbas, mn 1 Ukkaṭṭhā opening, mn 152 ends Indriyabhāvanā.
- Catalog: appended pali-dn (长部经典) + pali-mn (中部经典) under existing Pali Canon group, unitCount 178/221.
- Owned only: texts/pali/{dn,mn}.json, trans/pali-{dn,mn}-sujato.json, catalog.json, this report; builders pipeline/build_pali_nikaya.py + update_catalog_nikaya.py.
- Anomalies: none blocking — sparse clone extended in place (dn/mn root+trans trees); max unit 2024 words within shipped precedent (snp 1153).
