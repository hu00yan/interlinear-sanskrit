# Pali sister-site feasibility (reusing the greek-reader / interlinear-sanskrit architecture)

Question: can build-time morphological precompute → static JSON shards → static
frontend be reused for **Pali**, alongside the existing Sanskrit vertical?
Verdict up front: **YES for a minimum vertical (Sutta Piṭaka core + Vinaya)** —
and on *licensing* Pali beats Sanskrit outright: the entire canonical corpus has
a CC0 machine-readable edition (`suttacentral/bilara-data`, segmented and
aligned to CC0 translations), plus a **CC0 lemmatized five-witness critical
edition of the whole canon** (`tipitaka.critical`). The weak layer is
morphology: there is **no DCS-equivalent human-tagged Pali corpus and no
production FST/analyzer** — only dictionary-driven inflection templates
(DPD, CC BY-NC-SA), one academic prototype (Alfter 2015), and a canon-wide
form→lemma index. Rule-based analysis is *easier* than Sanskrit (sandhi is
shallow, verbal system small), but we lose DCS-style ground truth to verify
against.

Research date: 2026-08. Companion studies: `qa-report/sanskrit-feasibility.md`
(greek-reader repo), `research/pd-translations-and-smyth.md`.

## Layer 1 — Texts (Pali source)

| Project | License | Format | Coverage | Integration effort |
|---|---|---|---|---|
| **SuttaCentral `bilara-data`** (github.com/suttacentral/bilara-data) | Root texts: ancient text, PD; Mahāsaṅgīti Tipiṭaka Buddhavasse 2500 waiver statement (CC0-style, "free of known restrictions"); translations CC0 | JSON per segment, **Pali↔translation segment-aligned** (median ~9 words/segment), UTF-8 Roman | Complete Sutta + Vinaya Piṭaka (root/pli), many languages; Khuddaka incl. Dhp, Ud, Iti, Thag/Thig | **Trivial**: this IS our shard format problem already solved — segments map 1:1 onto interlinear lines |
| **`tipitaka` R package** (CRAN, Zigmond 2026) | **CC0** | R data frames: full VRI CST4 canon, word frequency, Pali sort order | Entire Tipiṭaka, VRI Chaṭṭha Saṅgāyana v4 base | **Low**: one-off extraction into our text shards |
| **`tipitaka.critical` R package** (CRAN, Zigmond 2026) | **CC0** | R data frames + sparse DTM: surface form + DPD-lemma per token | Five-witness collation (**PTS/GRETIL, SuttaCentral/Mahāsaṅgīti, VRI CST4, BJT, Thai Royal**) — 5,777 text units, ~2.8 M tokens | **Low**: gives us redistributable collated text AND a canon-wide form→headword index (see Layer 3) |
| **GRETIL Pali section** (gretil.sub.uni-goettingen.de, `2_pali.zip`) | ⚠️ Mixed & stricter than Sanskrit side: PTS-edition files "(C) PTS & Dhammakaya Foundation", CC BY-SA 4.0 + "scholarly purposes only"; SLTP/BJT files by Sri Lanka Tripitaka Project; site-wide "ANY COMMERCIAL USE EXPLICITLY EXCLUDED"; B2FIND lists CC BY-NC-SA 4.0 | Normalized Unicode HTML/txt (+ TEI conversions) | Whole Tipiṭaka (PTS + BJT editions); paracanonical: Netti, Peṭakopadesa, **Milindapañha** (PTS+BJT), Suttasaṅgaha (missing); chronicles: **Dīpavaṃsa, Mahāvaṃsa**, Dhātuvaṃsa; commentaries: Samantapāsādikā, **Buddhaghosa's Visuddhimagga** (PTS+BJT); Jātaka vols I–V (PTS/Dhammakaya); grammars: Balāvatāra, Kaccāyanasuttaniddesa, Kaccāyanadhātumañjūsā, Moggallāna-vyākaraṇa, Padamañjarī, minor grammars (several input by A. Ruiz-Falqués); **Abhidhānappadīpikā** | **Medium**: conversion trivial (same Velthuis→IAST tooling as Sanskrit), but license means prefer CC0 sources for anything canonical |
| **tipitaka.org / CST4 (VRI Chattha Sangayana)** | No formal license: "digital reproduction of the authenticated Tipiṭaka… encourage use… for academic, personal, monastic research", cite requirement; VRI asserts the edition; freely distributed since CSCD era | Proprietary-ish XML/RTF per volume, multi-script (Roman/Devanagari/Myanmar…), Windows software + web | Tipiṭaka **+ Aṭṭhakathā + Ṭīkā + other Pali texts** (217 vols) — unique depth in commentarial literature | **Skip as primary**: no explicit license; use only as reference witness (already inside `tipitaka.critical`'s collation). Commentaries would need separate permission |
| **VRI CSCD3/CST4 desktop** (vridhamma.org) | same as above | same | same | Skip |

Notes:
- Non-canonical wishlist check against GRETIL holdings: **Milindapañha ✔,
  Visuddhimagga ✔ (PTS+BJT), Jātaka ✔ (vols I–V), Dīpavaṃsa ✔, Mahāvaṃsa ✔,
  Abhidhānappadīpikā ✔** — all present, all under the GRETIL/SLTP scholarly-only
  umbrella rather than clean licenses.
- "Pali Platform": no such analyzer/tool found — closest real artifacts are the
  Pariyatti app (devotional word-a-day, no data release) and CST4. Treat the
  name as a misremembering of CST4/Pariyatti.
- Aleix Ruiz-Falqués (not "Ruiz de Villa") — Cambridge PhD 2016 on Kaccāyana
  tradition; personally digitized several Pali grammars for GRETIL
  (Kaccāyanasuttaniddesa, Kaccāyanabheda, Saddatthabhedacintā, Kaccāyanasāra),
  but has shipped **no analyzer/FST**.

## Layer 2 — Translations (license-critical)

| Translation | License | Status confirmed? | Coverage |
|---|---|---|---|
| **Bhikkhu Sujato, complete Sutta Piṭaka** (SC editions) | **CC0 — CONFIRMED**: `bilara-data/LICENSE.md` ("All translations created in Bilara and supported by SuttaCentral are dedicated to the Public Domain … CC0"); per-sutta `(i)` panel states CC0 waiver published from Australia | ✅ Yes, both repo-level and per-work statements | DN, MN, SN, AN + Khuddaka (Dhp, Ud, Iti, Snp, Thag, Thig, Vv, Pv, etc.), segment-aligned to Pali |
| **Bhikkhu Brahmali, Theravāda Collection on Monastic Law (Vinaya)** | **CC0 — CONFIRMED** (per-volume copyright page + bilara-data tree `translation/en/brahmali/vinaya`; first complete modern Vinaya English) | ✅ Yes | Complete Vinayapiṭaka, 6 vols |
| Legacy PTS translations: Rhys Davids DN ("Dialogues", 1899–1921), Woodward/Rhys Davids SN ("Kindred Sayings"), Woodward/Hare AN ("Gradual Sayings"), Horner MN ("Middle Length Sayings"), Horner Vinaya ("Book of the Discipline") | **CC BY-NC 4.0 / 3.0** via PTS's own relicensing program (palitextsociety.org/copyright-information) — explicitly listed works; older ones additionally PD-by-age in US (pre-1930 unrenewed), but rely on the PTS grant where listed | ✅ Yes (2023 announcement) | Four Nikāyas + Vinaya — redundant fallback given CC0 Sujato/Brahmali; useful for variant renderings |
| Jātaka: Chalmers, Rouse, Francis, Neil, Cowell (1895–1907) | **Public domain** — SC hosts them stating "These translations are in the public domain"; sacred-texts digitization | ✅ Yes | All ~550 stories (6 vols) |
| Dhammapada: Max Müller (SBE 10, 1881) | PD (US pre-1929, no renewal known) | ✅ | Complete |
| Dhammapada: T. Maxwell (1970s?) / Narada / Buddharakkhita | Maxwell ©; Buddharakkhita CC BY-NC-ND (Access to Insight); Narada © — skip, Sujato covers it CC0 | — | — |
| Milindapañha: T.W. Rhys Davids, "Questions of King Milinda" (SBE 35–36, 1890–94) | PD (pre-1929) | ✅ | Complete |
| **Mahāvaṃsa: Wilhelm Geiger** (PTS/OUP 1912, tr. assisted by M.H. Bode) | **PD — Internet Archive "NOT_IN_COPYRIGHT", no notice/no renewal**; Wikisource transcription underway; lakdiva.org web edition (non-commercial grant only — use IA scan instead) | ✅ Yes | Mahāvaṃsa chs 1–37; Cūḷavaṃsa (Geiger/Rickmers 1929–30) also PD-era |
| Dīpavaṃsa: Hermann Oldenberg (1879, text + tr.) | PD | ✅ | Complete |
| Visuddhimagga: Ñāṇamoli, "Path of Purification" (1956/2010 BPS) | **© BPS — blocked**; no PD complete English exists | ❌ | — |
| Abhidhamma: Rhys Davids Dhammasaṅgaṇī (1900), Points of Controversy etc. | Pre-1929 volumes PD; later PTS Abhidhamma trs. covered by CC BY-NC program where listed | Partially ✅ | Kathāvatthu (Aung/Rhys Davids 1915, PD), Dhammasaṅgaṇī (1900, PD) |
| Bhikkhu Bodhi SN/AN/MN revisions, DPPN-adjacent modern works | © — do not touch | ❌ | — |

Net: **the largest interlinear target (Nikāyas + Vinaya + Dhammapada + Jātaka +
Milindapañha + Mahāvaṃsa) is fully licensable**, mostly CC0/PD — strictly
better than the Sanskrit kāvya situation (where Clay CSL etc. are closed).

## Layer 3 — Morphology (the hard layer)

| Candidate | What it actually is | License | Machine-readable? | Usability |
|---|---|---|---|---|
| **Digital Pāli Dictionary (DPD)** — github.com/digitalpalidictionary/dpd-db (Blake Walsh et al., active, monthly releases) | Pāli-English dict (~30k+ headwords) **plus**: inflection-template engine, **deconstructor** (sandhi/compound splitter used in production on dpdict.net & suttacentral.net), grammar dictionary, roots dictionary, frequency lists | **CC BY-NC-SA 4.0** (README + docs site) | ✅ SQLite + TSV exports, Python API, GoldenDict builds; integrated into SC, Simsapa, dhamma.gift | Best-in-class machinery, **NC constraint** (same posture as Huet Heritage dict in the Sanskrit study): fine at build time for a non-commercial static site; cannot ship its definitions verbatim in a commercial context |
| **`tipitaka.critical` lemmatization** (Zigmond) | Canon-wide **surface-form → DPD-headword** mapping over the collated text | **CC0** | ✅ R data frames | Our Morpheus-shards analogue at lemma level: reuse directly as the backbone index, then add case/number tags ourselves |
| **digitalpalitools/inflection-generator** | Rust/PowerShell generator producing SQLite of Pali declension/conjugation schema from a master spreadsheet | CC BY-NC-SA 4.0 | ✅ .db/.sql releases | Small project (2★); paradigm data source worth mining, not a dependency |
| **Alfter 2015, "Analyzer and generator for Pali"** (arXiv:1510.01570, bachelor thesis) | Rule-based morphological analyzer+generator: inflectional paradigms + lexical DB, generator→lookup-table analyzer, rule fallback when OOV | Paper CC BY 4.0; **code not found published** | ❌ (paper only) | Blueprint only — validates the generate-and-index approach we'd use |
| Tagged corpus (DCS-style) | **Does not exist for Pali.** No UD treebank, no LDC-scale POS-tagged canon. Closest: `tipitaka.critical` lemma index (above); Joy Bose 2026 stylometry work uses bilara CC0 corpora but adds no morph tags | — | — | This is the single biggest gap vs our Sanskrit pipeline (DCS gave us 5.66M hand-tagged words) |
| VRI tools | Lookup/search software only (CST4, PCED dictionaries); no morph engine | — | — | Nothing to integrate |
| **Kaccāyana digital implementations** | **None executable found.** Only: kaccayana.github.io — Chris Tham's CC0 English translation of the Kaccāyanavyākaraṇa, self-described status "Idea"; GRETIL hosts the grammar-tradition texts themselves (Balāvatāra, Moggallāna-vyākaraṇa, Kaccāyana commentaries) as e-texts | Translation CC0; GRETIL texts scholarly-only | Text yes, parser no | Use Kaccāyana/Warder paradigms as the spec for our own ending rules, as planned for Pāṇini in Sanskrit |

### How bad is Pali sandhi + inflection vs Sanskrit, really?

- **Sandhi: substantially easier.** Pali external sandhi is dominated by simple
  vowel coalescence/elision and gemination (n'atthi < na atthi, evaṃ me sutaṃ
  type joins), with a bounded rule set — nothing like Sanskrit's class-based
  assimilation cascades. Canonical prose compounds are short (commentaries are
  worse). DPD's deconstructor already solves this in production and can seed a
  build-time splitter; expect higher split accuracy than Sanskrit from day one.
- **No padapāṭha escape hatch** (unlike Ṛgveda): the Tipiṭaka has no canonical
  word-separated recension; aṭṭhakathā padasoḷhā glosses exist only for
  commented passages. So every text needs splitting — but easy splitting.
- **Inflection: smaller paradigm space than Sanskrit, messier stems.** 8 cases ×
  2 numbers; vowel stems are regular; consonant stems (-ant/-at/-ar/-as/-in,
  rājā/brahmā-type) alternate irregularly; verbs have ~7 present classes, aorist
  (suppletive/irregular), future, imperative, optative + participles — no
  periphrastic perfect/benedictive inventory. A Warder/Kaccāyana-derived
  ending+FST table is a few hundred rules, not thousands. The catch: **no gold
  tagged corpus** to measure against, so precision claims must come from our own
  spot-audit (like greek-reader's eval battery) plus cross-checking against the
  CC0 lemma index.

## Layer 4 — Dictionaries (machine-readable)

| Dictionary | License | Format | Notes |
|---|---|---|---|
| **PTS Pali-English Dictionary (PED)**, Rhys Davids & Stede 1921–25 | © PTS, but **released by PTS under CC BY-NC 4.0** (listed in their relicensing announcement); UChicago DSAL hosts digitized DB (updated 2021); dpd `other-dictionaries` repo packages it | DSAL database; GoldenDict/MDict builds via dpd-other-dictionaries; gandhari.org online | Usable non-commercially with attribution — good enough for our LSJ-panel equivalent |
| **Margaret Cone, A Dictionary of Pāli** (3 vols, 2001/2010/2020+) | **© PTS, "by permission" only** (gandhari.org display); in print, actively sold | Online at gandhari.org (permission-based); exporter exists in dpd `other-dictionaries` but redistribution unlicensed | **Blocked** for our shards; treat as editorial reference only |
| **Critical Pāli Dictionary (CPD/NCPED)**, Copenhagen | Freely available online digital edition (royal academy project); no explicit open-data license found | Web + dpd packaging (`cpd`) | Gray-zone usable; cite generously |
| **Nyanatiloka, Buddhist Dictionary: Manual of Buddhist Terms & Doctrines** | Author d. 1957; widely redistributed (budsas "free distribution by arrangement with publisher", BPS); **no renewal found, but no clean waiver either** — murky-PD | HTML/e-text + dpd packaging | Acceptable risk tier below PED; optional supplement |
| Concise Pali-English Dictionary (Buddhadatta CPED) | Provenance murky (see SC sc-data#11 discussion: unclear publisher/licence) but universally redistributed; CPED included in Digital Pali Reader (GPLv2) ecosystem | Multiple digitizations | Backup tier only |
| **DPD** itself | CC BY-NC-SA 4.0 | SQLite/TSV/GoldenDict/API | The practical default: best coverage of canonical vocabulary incl. compounds/variants/roots/frequency |
| **Abhidhānappadīpikā** (Pali-Pali thesaurus-grammar) | GRETIL e-text (SLTP input, scholarly-only) | HTML | Reference only; no English glosses |
| DPPN (Malalasekera, Dictionary of Pāli Proper Names, 1937–38) | Old; dpd repo ships an exporter (`dppn`); widely mirrored | e-text | Proper-noun card support; license age-PD-ish, verify before shipping |
| "sabda-mala" | **No Pali dictionary by this name found** (sabdamala.com = Nepali alphabet course; BuddhistDoor "śabdamālā" = generic entry page). Likely a misremembering — nearest analogue is DPD's family/root organization | — | — |

## Minimum viable vertical (recommended)

1. **Dhammapada + selected Nikāya suttas (DN 1–2, MN 1, SN 56.11, AN corpus
   highlights)** — bilara-data CC0 root + Sujato CC0 translation, already
   segment-aligned → interlinear rendering nearly free. Text layer: done day 1.
2. **Complete four Nikāyas then Vinaya** — same stack; Brahmali Vinaya CC0.
3. **Jātaka book 1 + Milindapañha** — PD translations (Chalmers/Rhys Davids)
   aligned to GRETIL/BJT-derived text (use `tipitaka.critical` collated stream
   where possible to stay CC0 on the Pali side).
4. **Mahāvaṃsa (Geiger)** — stretch goal; PD translation, GRETIL Pali text
   (license note needed), verse-heavy so prosody-free interlinear is fine.
5. Morphology: own rule engine (Kaccāyana/Warder paradigms, ~300 endings) →
   generate-and-index exactly like the Greek FST spike; bootstrap lexicon from
   the **CC0 `tipitaka.critical` form→lemma index** (whole-canon recall floor);
   enrich with **DPD (BY-NC-SA)** deconstructor + inflections at build time for
   a non-commercial deployment; ship PED cards under PTS CC BY-NC.

## Coverage estimate vs our Sanskrit pipeline

- Text+translation licensing: **~100% of MVP corpus clean** (vs Sanskrit where
  GRETIL attribution-license sufficed but kāvya translations were closed).
  Alignment: bilara gives sentence-segment parallelism for free — Sanskrit
  needed verse-grid alignment built by hand.
- Morphology: expect **~85–90% of tokens with confident case/number/POS** on
  canonical prose (regular stems + function words dominate), dropping to
  **~75–80% on verses/archaic forms (Dhp, Thag, Jātaka gāthās)** without a
  tagged corpus to tune against — versus Sanskrit's estimated ~85–95% (BhG/Upaniṣads
  riding on DCS gold data). Lemma-level (form→headword) coverage will be
  **higher** than Sanskrit thanks to the CC0 canon-wide index (~95%+ of running
  tokens resolve to some headword).
- Overall: a Pali MVP lands **close to the Sanskrit site's quality bar with less
  licensing friction but more morphology uncertainty** — the uncertainty is
  verifiable cheaply because the corpus is small enough (2.8M tokens) to audit.

## Hardest gaps, ranked

1. **No gold-standard tagged corpus / no mature analyzer** — must build the
   rule engine ourselves (Alfter-style generate-and-index) and invent our own
   eval harness; mitigation: CC0 lemma index + DPD templates as priors.
2. **Consonant-stem & aorist irregularity** in verse texts — the long tail of
   wrong-analysis risk; mitigate like Greek unknown-word UX ("—" card, ranked
   candidates).
3. **Commentaries/sub-commentaries locked up** — CST4 has them but VRI grants
   no explicit license; Ñāṇamoli's Visuddhimagga © — no clean path to a
   Visuddhimagga vertical (contrast: Milinda/Jātaka/chronicles fine).
4. **DPD's NC license** — best dictionary + splitter can't be shipped verbatim
   in any commercial future; keep a clean-room path (lemma index + PED BY-NC +
   own paradigm engine).
5. Minor: script/edition variance (five witnesses disagree; `tipitaka.critical`
   resolves most), and Abhidhamma translations largely © (only 1900s PTS
   volumes PD).
