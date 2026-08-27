# Traditional Interlinear Correction Audit

## Result

The client now renders an inline compact English sense as `— sense` from the
selected occurrence gloss first and the exact MW lemma entry second. It strips
markup, citations, grammatical labels, cross-reference noise and CJK before
the 90-character display budget. Full MW text remains in the clicked word
detail only. A missing sense removes only the inline sense; `Gloss unavailable.`
appears only in the clicked detail.

## BhG 1.1 data gate

Browser audit against `http://localhost:4176/#/bhagavadgita?ref=1.1` found 157
resolved non-proper-name cards, 138 glossed: **87.9%**. This does not meet the
90% acceptance gate and the audit intentionally fails until data repair lands.

The 19 unresolved cards are not all names. Missing ordinary lexical categories
include finite verbs (`pradadhmatuḥ`, `vyadārayat`, `sthāpay`, `viṣīdan`,
`pariśuṣ`, `paridahyate`), stems/participles (`dṛṣ`, `sīdat`, `sraṃs`, `bhram`),
and compound/nominal entries. For these, the selected occurrence parse has no
`Parse.g` and the frontend's exact MW SLP1 lookup returns no usable English
sense. No translation title or CJK text is substituted. The client is already
ready to consume occurrence `g` values or exact MW entries from the data lane
without redesign.

## UI and evidence

- Removed the `行间 | 侧栏` control and all inline translation painting.
- Translation is opt-in, resizable and closable in the right sidebar; it stays
  closed after paging. English/Chinese selection exists only inside that sidebar
  when both sources exist.
- Vocabulary/bookmark Import and Export controls are visibly present on About,
  using the existing Greek-reader-compatible JSON interaction and file chooser.
- Browser artifacts: `qa-report/assets/bhg-1.1-interlinear.png`,
  `qa-report/assets/mobile-bhg-1.1.png`, and
  `qa-report/assets/interlinear-audit-dom.json`.

`npm run build` passes. `node tests/interlinear-audit.mjs` correctly fails only
the quantified BhG coverage gate above; the other inspected UI paths completed.
