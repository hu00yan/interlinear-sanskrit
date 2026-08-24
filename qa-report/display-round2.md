# Display round 2 — dual-script simultaneous display + MW gloss wiring

Storage: "interlinear-sanskrit.display" = {"iast":bool,"deva":bool}; legacy
string values ("iast"/"dev") + transitional ".scripts" object migrate on first
read. Invariant: at least one script always on (last-off auto-enables other).

Playwright matrix (.cache-tools/dual-matrix.mjs) — 4 combos × BhG(Deva-stored)
+ Īśā Upaniṣad(IAST-stored), ALL PASS:
- iast-only: single IAST line (BhG tokens transliterated: dharmakṣetre…saṃjaya)
- deva-only: single Devanagari line (Upaniṣad oṃ/sviddhanam → ओं/स्विद्धनम् —
  per-token direction detection on IAST sources works)
- BOTH: two stacked lines, Devanagari first + IAST second muted-smaller,
  grid columns aligned (pair width |Δ|<3px incl. post-fonts.ready), parse row
  spans full width beneath unchanged
- persistence: prefs survive reload on both works (dual class present)

MW gloss chain end-to-end: displayed word → devToSlp1/iastToSlp1 (+ sibilant
mirrored variants, ≥4-char prefix fallback) → lazy data/gloss/<letter>.json →
"Monier-Williams" section {lemma,gloss}; verified live hit कुरु → "m. pl. N.
of a people of India…"; silent-hide when no entry.

tsc --noEmit ✓ · npm run build ✓ · shipped in commit 6ad1f8b (origin/main).
