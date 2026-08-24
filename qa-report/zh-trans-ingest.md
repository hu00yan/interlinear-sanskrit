# 中文古典佛典译本摄取报告 (zh-trans-ingest), 2026-08-24

All 7 works ingested under `public/data/trans-zh/<workId>.json`, catalog `translationZh` added per work (RMW, byte-style preserved: compact `, `/`: ` separators). Sources: zh.wikisource.org (PD) exclusively — no CBETA XML used, so **no NC caveat applies**. No modern translations / 白话译文 anywhere.

| workId | canon edition chosen | source | unit coverage | alignment verdict |
|---|---|---|---|---|
| heart-sutra | T251 玄奘譯 (649) | wikisource 般若波羅蜜多心經 (玄奘) | 6/8 (75%) — T251 lacks opening homage & closing colophon; refs omitted by design | full |
| diamond-sutra | T235 鳩摩羅什 (~402), 江味農校定本 (敦煌底本) | wikisource 金剛般若波羅蜜經 (鳩摩羅什) | 85/89 (95.5%) — 昭明32分 redistributed onto Vaidya paragraph units via content anchors; omitted: namo(2), monks' salutation(4), 2nd dharmatā verse(77), formula tag(87) | partial |
| sukhavativyuha-smaller | T366 鳩摩羅什 (402) | wikisource 佛說阿彌陀經 | 27/28 (96.4%) — paragraph-for-paragraph; ref 1 homage absent from T366 | full |
| sukhavativyuha | T360 康僧鎧 (trad. 252; 归属存疑—noted in file+catalog source) | wikisource 佛說無量壽經 | 134/134 (100%) section-level thematic | partial |
| buddhacarita | T190 曇無讖 (~420) — see anomaly #1 | wikisource 佛所行讚 | 791/1033 (76.6%) sequential gatha-flow over extant cantos 1–14 | partial |
| lalitavistara | T187 地婆訶羅 (683) — see anomaly #2 | wikisource 方廣大莊嚴經 | 756/2571 (29.4%) chapter-level ~130-char sentence chunks on leading units of each of the 27 chapters | partial |
| pali-dhammapada | T210 維祇難等 (吳, trad. 224) | wikisource 法句經 (simplified page → s2t converted) | 26/423 (6.1%) chapter-level ONLY, whole 品 attached to each vagga's first unit | partial |

## Mapping basis (documented in each file's `note`)

- **sukhavatiyuha-larger**: Fujita-edition Sanskrit renders Dharmākara's aspirations as *unnumbered conditional formulas* (`mā tāvad abhisaṃbudhyeyaṃ…`, refs 21–41); order differs from the Chinese numbered 48愿 → zh vows distributed sequentially-proportionally (~2–3 vows/ref across refs 21–40; closing verse 我建超世誓 on 41). 五惡五痛五燒 discourse has no Sanskrit counterpart and is not represented. Prisoner-in-golden-chains simile ↔ ref 120; other-field bodhisattva counts ↔ refs 122–127.
- **diamond-sutra**: includes the 62-char 魏譯 supplement (爾時慧命須菩提…, ref 69) carried by the 江味農 collation — it matches Sanskrit text missing from Kumārajīva's original, improving alignment.
- **lalitavistara**: T187 chosen over T186 普曜經 because T186 counts 30品 vs our 27 parivartas; T187's 27品 map 1:1 by name/content (兜率天宮=Samutsāha, 音樂發悟=Sañcodanā, 頻婆娑羅=Bimbisāra, 商人蒙記=Trapuṣabhallika, 大梵天王勸請=Adhyeṣaṇā…). Chunks attach to leading units only; trailing (mostly verse) units fall back to English per-unit. SK ch.0 (homage) unrepresented.

## Anomalies / deviations from task spec

1. **buddhacarita edition swap (verified)**: Task preferred T191 宝云《佛本行經》 claiming 28品→28 cantos. Verification against the wikisource text showed **T191 has 31品** (因缘品第一…八王分舍利品第三十一) — a different recension, premise false. Per the task's own "verify canto count matches Sanskrit 28" instruction, switched to **T190 曇無讖《佛所行讚》**, verified at exactly 28品 matching Aśvaghoṣa's 28 cantos. Structural divergences handled and noted: T190 品12 covers BOTH teachers → split proportionally across SK cantos 12 (Ārāḍa)/13 (Udraka); T190 品13+14 jointly cover SK canto 14. 宝云 attribution debate is therefore moot for this ingest but remains documented here.
2. **lalitavistara coverage 29.4%** is by design (chapter-level chunking; contract permits per-unit fallback). Verse-level mapping was rejected: T187 prose/verse interleave does not track Vaidya units reliably.
3. **dhammapada coverage 6.1%** is mandated ("chapter-level mapping only"): recensions differ (39品/~752偈 vs 26 vaggas/423 verses). Full overlap table embedded in file note. T210-only chapters (無常/教學/多聞/篤信/戒慎/惟念/慈仁/言語/利養/泥洹/生死/道利/吉祥) unrepresented; every Pali vagga received a counterpart.
4. T210 wikisource page is simplified-Chinese with sparse punctuation; converted s→t (OpenCC) per repo's traditional style. Wikisource punctuation elsewhere is rough in places (accepted per source-priority instructions).
5. Wikisource T251/T235 pages carry later prefaces/liturgical front matter (明太祖序, 開經偈, 往生咒 etc.) — all stripped; sutra-proper only.

## Validation

`.zh-work/validate.py` sweep (final run): all 7 files PASS — no dangling refs, no duplicates, no empty texts, schema `{workId, translator, year, license, alignment, note, units:[{ref,text}]}` mirrored, catalog entries point at existing files with `license:"PD"`.

## Commits pushed (7 + this report)

1. `dfb2d77` heart-sutra (+catalog)
2. `48f50c0` sukhavativyuha-smaller
3. `957a0b1` diamond-sutra
4. `91dc268` sukhavativyuha (larger)
5. `81aad3c` lalitavistara
6. `b0f6cff` buddhacarita
7. `629b7e0` pali-dhammapada
8. this report
