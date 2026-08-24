# trans/REF-NOTES-SA-WAVE2.md — ref schemes for the wave-2 Sanskrit translations

Written by the translation-acquisition lane (wave 2), 2026-08-24.
Companion to `trans/REF-NOTES.md`. Sources cached under `.cache-trans-epics/`,
`.cache-trans-buddh/`, `.cache-trans-kavya/`; builder is
`pipeline/build_translations_sa.py` (re-runnable). All files carry
`alignment:"loose"`.

| workId | translator / year | ref shape | notes |
|---|---|---|---|
| ramayana | Ralph T. H. Griffith 1875 | `<kanda>.<sarga>` (1.1–6.130) | Kandas 1–6 only: Griffith never rendered Book VII into verse (his prose argument exists but is not unit-aligned). sarga = Griffith's canto numbering, which occasionally merges canonical sargas. |
| mahabharata | Kisari Mohan Ganguli 1896 | `<parvan>.<section>` (1.1–18.6) | section = Ganguli's printed SECTION number (vols 3–4 use bare arabic markers). His sections ≠ critical-edition adhyāyas in places. Bhagavad-Gītā chapters sit inside parvan 6 flagged `[(Bhagavad Gita Chapter N)]`. |
| buddhacarita | E. B. Cowell 1894 | `<canto>.<verse>` (1.1–17.n) | SBE 49 abridged rendering; omitted verses are source ellipses. Cowell's base differs from Petrach/Eastern recensions. |
| sukhavativyuha-larger | F. Max Müller 1894 | flat `1..N` | Prose sūtra, no internal numbering in source → sequential paragraph refs. |
| sukhavativyuha-smaller | F. Max Müller 1894 | Müller's § numbers (`1..20`) | |
| vajracchedika | F. Max Müller 1894 | Müller's roman sections as arabic (`1..32`) | Müller's Sanskrit base ≠ Kumârajîva's 32-section Chinese arrangement. |
| heart | F. Max Müller 1894 | flat `1..12` | Smaller Prajñā-pāramitā-hṛidaya (= Heart Sūtra). Larger Hṛidaya also exists in SBE 49 if a separate workId is ever needed. |
| meghaduta | H. H. Wilson 1814 | flat sequential stanza-blocks `1..169` | Wilson's own marginal tags count lines, not verses — refs are positional; remap against Sanskrit verse order (Purva+Uttara continuous). OCR of the 1814 scan. |
| hitopadesha | Sir Edwin Arnold 1861 | `<book>.<story>`, story `.0` = book frame | Books = Arnold's Winning of Friends / Parting of Friends / War / Peace. Not canonical story numbering — remap via story titles/order. |
| pancatantra | Arthur W. Ryder 1925 | `<book>.<story>`, `.0` = book prologue | Ryder's all-caps story headings in order; his verse interpolations kept inline. Tantrakhyayika recension. |
| arthashastra | R. Shamasastry 1915 | `<book>.<chapter>` | Shamasastry's own 1915 division (= close to, but not identical with, Kangle's later books). A few OCR-lost headings merge neighbours. |
| manusmriti | Georg Bühler 1886 | `<chapter>.<verse>` (1.1–12.131) | Bühler's printed verse numbers; bracketed exegetical footnotes dropped. |

## Known quirks
- sacred-texts pages lost several special glyphs (`Śrâvastî` → `S râvastî`,
  `jñ` → `gñ`) — diacritic noise, not words, was lost.
- Wayback snapshots used: `https://web.archive.org/web/<ts>id_/<url>`; archive.org
  djVu OCR for the three scans (Wilson, Ryder, Shamasastry).
