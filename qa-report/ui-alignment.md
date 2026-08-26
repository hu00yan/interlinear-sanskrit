# UI alignment: interlinear-sanskrit → greek-reader (canonical)

Sanctioned additions counted, NOT deviations: IAST⇄Devanagari dual display + script toggle; titleZh/nameZh bilingual cards; संस्कृत|पालि toggle w/ Latin sublabels; draggable sidebar w/ tier badges; word-lookup box; approved parse-compact grammar (group rows, 2-line gloss clamp, 另有N解 chip, samāsa block, honesty notes, zh-layer). **9 sanctioned surfaces, 11 deviations found → 11 fixed.**

| dimension | greek-reader | sanskrit was | action |
|---|---|---|---|
| drawer squeeze | `#app` gets width:auto + max-width clamp when drawer/panel open (bug-3 fix) | margin only → text slid under drawers | fixed, verified gap=0 at 1440 |
| controls overflow guard | `.controls > *` max-width/min-width (bug-4) | missing | added |
| mobile ≤30rem bar | compact gap/padding/font block | missing (390 bar full-size) | added |
| pcard glyph guard | min-height 1.2em + overflow visible; base gloss wrap | missing | added (mw-gloss clamp preserved) |
| vocab highlight gating | body.vocab-highlight class + CSS rule | missing both | added both |
| repeated refs | uniqueDomRef → 1.2a/1.2b suffixes | raw dup data-ref in DOM | ported |
| resume tracking | setFocusedRef/getFocusedRef wired: init, jumpToRef, scroll | absent; scroll-save guard matched `#/author/work` — never true on `#/work` routes → position saved only at open | ported + guard fixed for `#/work` & `#/pali/work`; verified ref updates on scroll |
| error state | unknown work → `.unparsed-note` | used `.crumbs` | unified |
| about page | "Your vocabulary & bookmarks" export/import | missing (CSS hooks already shipped) | ported verbatim |
| panel close | single classList.remove | duplicated line | cleaned |
| control order | back·crumbs·spacer·gloss·expand·collapse·vocab·★·[tr]·lexicon·A±·[script]·theme | same + sanctioned inserts at same slots | verified equal, no change |

**Audits:** parse-audit ALL GREEN after each cluster; golden-audit 4×`A7 chip aria` byte-identical at pre-session c9e54bb (audit regex wants "analyses", sanctioned chip says "readings" — tests/ out of scope, not a regression). OverflowX=0 at 1440/1024/390 × {IAST, Devanagari} × {行间, 侧栏} on BhG, Pali-Dhp, home; drawer/panel squeeze verified.

**Remaining gaps (capability ports, not grammar deviations):** greek TTS (per-line 🔊 + Play/Pause — needs sa voice pipeline), per-line AI assist + LLM panel, prosody/scansion, home full-text search hits (data/search-index-sa.json exists but index shape differs from greek's `{v,w,e}` contract), about "fork guide" section. Commits: b7379ab, cc3d329, 0945dde.
