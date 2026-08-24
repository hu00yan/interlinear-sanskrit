# QA report — Sanskrit translations, wave 2 (2026-08-24)

Builder: `pipeline/build_translations_sa.py` (re-runnable; sources cached in
`.cache-trans-epics/`, `.cache-trans-buddh/`, `.cache-trans-kavya/`, all
gitignored). Outputs: `public/data/trans/<workId>.json`, contract shape
`{workId, translator, year, license, alignment:"loose", units:[{ref,text}]}`,
plus `public/data/trans/REF-NOTES-SA-WAVE2.md` (ref-scheme table for the
collector). No git operations; no writes outside owned paths.

| workId | translator / year | units | words | status | source |
|---|---|---|---|---|---|
| ramayana | Ralph T. H. Griffith 1875 | 493 | 335k | GO | PG #24869 (typed) |
| mahabharata | Kisari Mohan Ganguli 1896 | 2101 | 2544k | GO | PG #15474–77 (typed); all 18 parvans |
| buddhacarita | E. B. Cowell 1894 | 1360 | 46k | GO | SBE 49 via Wayback (`sacred-texts.com/bud/sbe49/sbe4903–919`) |
| sukhavativyuha-larger | F. Max Müller 1894 | 291 | 18k | GO | SBE 49 sbe4924 (Wayback) |
| sukhavativyuha-smaller | F. Max Müller 1894 | 20 | 2.2k | GO | SBE 49 sbe4927 (Wayback) |
| vajracchedika | F. Max Müller 1894 | 32 | 8.2k | GO | SBE 49 sbe4929 (Wayback) |
| heart | F. Max Müller 1894 | 12 | 0.4k | GO | SBE 49 sbe4931 = Smaller Prajñā-pāramitā-hṛidaya |
| meghaduta | H. H. Wilson 1814 | 166 | 5.8k | GO | archive.org `mghadtaorcloudm00wilsgoog` djVu OCR |
| hitopadesha | Sir Edwin Arnold 1861 | 38 | 26k | GO | PG #13268 (typed anthology incl. Book of Good Counsels) |
| pancatantra | Arthur W. Ryder 1925 | 77 | 93k | GO | archive.org `the-panchatantra` djVu OCR |
| arthashastra | R. Shamasastry 1915 | 153 | 160k | GO | archive.org `Arthasastra_English_Translation` |
| manusmriti | Georg Bühler 1886 | 2681 | 82k | GO | `sacred-texts.com/hin/manu/manu01–12` (Wayback) |
| lalitavistara | — | — | — | SKIP | no clean PD English full text exists (Foucaux 1877/1887 is French; Mitra's "Lalita Vistara" 1877 is a Bengali-parallel edition of limited completeness — left out per brief) |

Totals: 12 files, 7424 units, ≈3.36M words, ≈19.1 MB JSON.

License notes: Griffith (1875), Ganguli (1883–96), SBE 49 (1894), Bühler/SBE 25
(1886), Shamasastry (1915), Wilson (1814), Arnold (1861) are pre-1929 US
publications → public domain. Ryder 1925 is PD in the USA since 2021-01-01:
maximum copyright term for a 1925 work is 95 years, so it expired on that date
whether or not the copyright was renewed. All texts fetched from PD-hosting
mirrors (Project Gutenberg / archive.org scans / Wayback snapshots of
sacred-texts.com, which blocks direct curl).

Validation performed: JSON schema + unique refs per file; famous-line spot
checks pass (R 1.1 Nárad opening; M 1.1 "Om! Having bowed down to Narayana and
Nara"; BC 1.1 "That Arhat is here saluted"; MS 1.1 "The great sages approached
Manu"; heart contains the gate mantra). Known noise, documented in
REF-NOTES-SA-WAVE2.md: sacred-texts glyph loss (`S râvastî`, `gñ`), djVu OCR
artifacts in the three scanned volumes, Ganguli/Shamasastry section divisions
differing from critical editions (alignment stays "loose").

workId spelling note: brief said "sukhavativyuhu-*"; files use standard
`sukhavativyuha-larger/-smaller` — rename with the catalog if the texts lane
chose a different id.
