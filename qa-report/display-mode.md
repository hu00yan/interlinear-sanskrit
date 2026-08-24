# QA: display mode (IAST ⇄ Devanagari) — 2026-08-24

- `tsc --noEmit` ✓, `npm run build` ✓; Playwright pass on http://localhost:4176 (dev server left running): 20/20 checks.
- Default view renders IAST tokens (first `.w` = "dharmakṣetre" for धर्मक्षेत्रे); toolbar button labelled "देवनागरी".
- Toggle → all tokens/lemmas switch to Devanagari live, body.dev-script set, line-height measured 1.90 (≥1.9); label flips to "IAST".
- localStorage `interlinear-sanskrit.display` = "dev"; survives reload; toggle back returns to IAST.
- Home: Bhagavadgītā card links runtime catalog route `#/tlg9000/bhagavadgita`; muted "Start with the Bhagavad Gītā." line present.
- No dead links: Iliad/Anabasis/Symposium starters and dead `#/paste` card removed; no Greek-reader copy remains on home.
- Search placeholder: "Search in IAST or Devanagari".
- translit.ts: 18 corpus-style pairs round-trip exactly (incl. ṛ/ṝ/ḷ/ṅ/ñ/ś/ṣ, anusvāra, visarga, avagraha, virama clusters).
- Note: fonts.googleapis.com unreachable from sandbox (ERR_CONNECTION_CLOSED) → serif fallback engaged; favicon 404 fixed via existing icon asset.
