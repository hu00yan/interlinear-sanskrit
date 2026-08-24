# Kena + Muṇḍaka ingest — QA report (2026-08-24)

- Texts: sa.wikisource raw wikitext (born-digital Devanagari, CC BY-SA 3.0) → IAST → words[] tokenized per build_upanishads rules. Files: `texts/upanishads/{kenopanishad,mundakopanishad}.json`.
  - IDs deviate from task brief (`kena`+`mundaka`): catalog id `mundaka-upanishad` is already occupied by a **mislabeled Māṇḍūkya** entry (12 units, pre-existing bug, untouched) → used symmetric standard names `kenopanishad`/`mundakopanishad`; trans filenames `*-muller.json` because `trans/kena.json`+`trans/mundaka.json` hold earlier Hume OCR files.
- Translations: Max Müller SBE vol 1 (1879, Talavakāra) / vol 15 (1884), archive.org `upanishads01mluoft` / `wg915` djvu.txt, PD.
- Counts: Kena 36 units (śānti + 35 verses, 4 khaṇḍas 9/5/12/9); Muṇḍaka 65 units (śānti + 64 verses, old 3-muṇḍaka division 9+13+10+11+10+11 — sources use 3 maṇḍakas, not the 2 assumed in the brief; matches Müller's print).
- Alignment: refs constructed identically both sides → Kena 35/35 (100%), Muṇḍaka 64/64 (100%). Śāntipāṭha Sanskrit-only (Müller didn't translate invocations).
- Spot-checks vs sanskritdocuments (read-only): Kena 1.1 exact match; 2.3, 4.8, 4.9 canonical ✓. Muṇḍaka 1.1.1, 1.1.5, 2.1.10, 2.2.1, 2.2.4 (praṇavo dhanuḥ), 3.1.1 (dvā suparṇā), 3.2.11 canonical ✓.
- OCR repairs: page-break footnote suspension (restored truncated MuU 2.1.6, Kena verse tails), `ii.`→11 disambiguation via expected-next (MuU 3.2.11), one mis-ordered footnote trimmed from MuU 3.1.10 (Müller's own note, verified against print), italic-garbage token map (~15 forms), candrabindu→anusvara for sibling consistency.
- Known minor variants kept source-faithful: wikisource `śāro` (std. śaro) MuU 2.2.4; doubled `pratitiṣṭhati` Kena 4.9 (in source).
- License fields: text `CC BY-SA 3.0 (sa.wikisource)`; translation `Public domain (SBE 1|15)` (PD, sibling-style wording). Catalog RMW appended 2 works to existing `upanishads` author group (now 10 works).
