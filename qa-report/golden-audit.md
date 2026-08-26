# Golden Audit — BhG vs qa-report/golden-spec.md

Sample: pages 1–3 × 20 tokens (60), click-through (word click ⇒ expansion,
as readers do). Before = HEAD build served :4177; After = fixed build :4176.

## Compound blocks (spec §3)
- BEFORE: 13 blocks — 7 BOGUS sandhi-fusion spans rendered as 「复合词成分」:
  च→ca+ā · अथ→atha+ā · तत्रापश्यत्→tatra+apaśyat · सहसैवाभ्यहन्यन्त→
  sahasā+eva+abhyahanyanta · भीमाभिरक्षितम् span-chain · अनार्यजुष्टम्→
  an+ārya+juṣṭam (wrong split) · (p2 dup) — 54% of displayed blocks wrong.
- AFTER: 10 blocks — 0 bogus. Gate (first member Cpd + inflected nominal head)
  kills every span; anārya+juṣṭam resolves to the genuine chain; कुरुक्षेत्रे
  honestly shows NO block (shard carries no chain).
- Deviations on 60-token sample: **7 → 0**.

## CJK discipline (spec header contract)
Full-page text-node sweeps incl. side panel: p1 162 / p2 344 / p3 547 CJK
occurrences under parse surfaces — 100% sanctioned chrome (`另有 N 解`,
`复合词成分 Samāsa · N`); unsanctioned = **0** (was: bogus headers).

## Merged rows (spec §2, post-0c0a30a confirmed LIVE)
kṣetra case-alternates (du./sg.) + compound reading merge into ONE row,
「·」 separators, repeat-gloss suppression active, ≤4 segments, chip math
correct via aria-label. Not a stale build: dist rebuilt + re-served.

## Empty states (spec §5)
1 honest empty column per page 1/3 sampled (no card, slot kept); 无词条
never rendered as text anywhere in the sample.

## Fixes shipped
- src/compound.ts: isGenuineSamasa() gate applied in membersOf() (all surfaces).
- src/api.ts: dedupeParses keeps the m-chain variant of a display triplet
  (dharmakṣetre regression — chain was being deduped away).
- src/render.ts: collapsed merged cards now append the samāsa block too.

tsc clean; vite build ok. Auditor: tests/golden-audit.mjs <baseUrl> <out>.
