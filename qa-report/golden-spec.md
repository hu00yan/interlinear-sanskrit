# Golden Spec — BhG certified reference (all works align to THIS)

Scope: reader parse surface (.parse-row/.pcol), word panel, lookup/lexicon.
Data contract: shards carry ZERO CJK; zh inside parse surfaces = sanctioned
UI chrome ONLY: `另有 N 解` chip · `复合词成分 Samāsa · N` header (genuine
samāsa) · wasm badges (`深度解析`/`未裁定`/`仅理论存在`, flag-gated). Anything
else CJK under .pcol/.pcard/.compound/.side-panel = defect.
1. TOKEN CELL — reading line stacks per prefs {iast,deva} (default IAST on):
   IAST line 0.86em of unit size, muted; Devanagari line full size above it;
   ≥1.9 line-height in deva mode. Cells wrap inline like text, never widen page.
2. PARSE CARD / MERGED ROW — one compact row per token (0c0a30a format):
   `lemma abbr-feats — gloss · lemma² feats² — gloss² …`
   • lemma: dual-script stack, IAST bold PRIMARY over deva 0.8em @0.7 opacity;
     DCS homonym digits stripped from display.
   • abbr-feats 0.72rem mono, each tag stacked IAST(600) over deva 0.78em@0.72;
     unmapped extras (Cpd/stem/dialect) → expanded detail only.
   • segments ≤4 visible (primary + 3 alts), joined by muted bold 「·」;
     overflow ⇒ `另有 N 解` chip, N = total−visible, click expands ALL candidates.
   • gloss after `— ` em-dash, capped ~90 chars; exact repeat of preceding
     gloss suppressed; miss ⇒ cell removed, NEVER a placeholder. Glosses paint
     together after lookups settle.
3. COMPOUND BLOCK — genuine samāsa only (gate: first member tagged Cpd AND
   head carries case inflection 1–7/voc, never indecl/finite-verb head).
   Sandhi-fusion spans (पश्य+एताम्, आहुः+त्वाम्+ऋषयः) must NOT render as blocks.
   Header `复合词成分 Samāsa · N`. One line PER MEMBER:
   `form(dual-script) + abbr-feats + MW gloss`; joiner 「+」 between rows;
   member gloss miss ⇒ silent removal. Renders collapsed/expanded/single,
   panel + lookup. Dedupe keeps m-chain variant of a display triplet.
4. EXPANDED MODE — every deduped candidate its own .cand-row: lemma +
   diff-badges vs same-lemma siblings, feats, extras, gloss; thin top rule.
5. EMPTY STATES — honest: no analyses ⇒ NO card of any kind (slot kept,
   width 4.5–12rem); gloss miss ⇒ silent; compound without genuine chain ⇒ no
   block (कुरुक्षेत्रे case). 无词条 never renders as text.
6. SPACING/HIERARCHY — separation by whitespace+scale (no rules): row font
   0.82×ui, cards mb 4px, compound mt 4px + dashed hairline, member rows
   dotted hairlines; hierarchy token > lemma(bold) > feats/chip > gloss.

Audit: 60 tokens (BhG pages 1–3 × 20) → qa-report/golden-audit.md.
