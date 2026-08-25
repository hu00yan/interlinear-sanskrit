# QA: DCS → site morphology, round 2 (+21 works) — 2026-08-25
**Verdict: SUCCESS.** 22 catalog↔DCS matches evaluated, **21 passed validation & merged** (`NEW_WORKS` in `pipeline/build_morph_dcs.py`; source cache `.cache-dcs-ext/` sibling of repo, override via `DCS_EXTRA_SRC`): shards 124,298 → **164,119 keys (+39,821), 18.9 MB**; `_surface_index.json` 441,490 tokens (19.2 MB), 40 letter + 74 by-work slices; idempotent rerun adds 0 keys. Per-work numbers: `morph-dcs2-resolution.csv`.
**Key fix:** `slp1_key()` normalizes Devanagari vs roman ai/au differently (वै→`ve` vs vai→`vai`) so such keys never met; new `_canonical_keys()` derives both flavors for DCS forms *and* site-token lookups — prerequisite for most gains below.
| matched work (DCS dir) | % was→now | | work | % was→now |
|---|---|---|---|---|
| rigveda-mandala01–10 (Ṛgveda) | ~85→98.8–99.4 | | yoga-sutra / nyaya-sutra | 24.5→91.3 / 23.1→92.6 |
| bhagavata-01..12 (Bhāgavatapurāṇa) | 61–74→90.2–95.2 | | astasahasrika / lankavatara | 66.9→94.9 / 58.1→93.6 |
| svetasvatara / kausitaki-upanishad† | 58.6→95.1 / 50.0→88.1 | | kumarasambhava / gitagovinda | 62.4→95.8 / 59.5→99.2 |
| satakatraya / rtusamhara / caurapancasika | 66.3→96.1 / 93.4→96.3 / 91.5→94.5 | | 6 upaniṣads (kaṭha/muṇḍaka/ait/tait/bṛh/chān) | 86.4–91.1→90.8–94.9 |
| sankhya-karika / saddharmapundarika | 32.4→86.7 / 87.8→90.4 | | Spillover-only (no DCS match): vetalapancavimsati 73.1→95.1, maitri-up 39.2→83.1, brahma-sutra 40.2→87.9, kenopanishad 82.1→84.0, raghuvamsa 88.8→91.9, mundaka(Māṇḍūkya) 83.6→86.8 |
**Excluded:** `vetalapancavimsati` ↔ DCS VetPV — recension mismatch despite name match (different maṅgala/frame story vs our Śaśāṅkavatī text; only 3 shared token hits). †kausitaki = partial DCS (ch.1–2 of 4); identity verified verse-by-verse.
Spot-checked 14 analyses by eye across all groups (RV `abhaiṣuḥ`→भी aor 3pl+'s', KumSaṃ `akṣṇaḥ`→अक्षि नपुं;5;एक, GG `kālavatī`→कलावत् स्री;1;एक, YS `anaṣṭaṃ`→अनष्ट नपुं;1;एक, BṛhU `abhavann`→भू लङ्;प्रथम;बहु …) — all sound; residual DCS quirks (occasional missing lakāra) kept verbatim.
