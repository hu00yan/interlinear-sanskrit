// Shared interlinear rendering: Greek units (verse lines or prose chunks)
// with per-word parse cards, controls bar, and the click-for-details panel.
import { dedupeParses, fetchJSON, loadCatalog, loadGloss, loadMorph, loadOccurrenceMorph, stripAccents, zhNameOf, zhTitleOf, type Catalog, type Gloss, type OccurrenceMorph, type Parse, type Unit } from "./api";
import { applyClasses, attachChip, isKnown, markKnown, toolbarControls, unmarkKnown } from "./vocab";
import { copyLinkButtonFor, openStarPanel, starButtonFor } from "./bookmarks";
import { openLexicon, lexiconButton } from "./lexicon";
import { themeControl } from "./theme";
import { disp, registerUnitScripts, scriptPrefControls,
  scriptPrefs } from "./display";
import { devToIast, iastToDev, slp1KeyFor, slp1KeyVariants } from "./translit";
import { compactFeatsEl, compactTagNode, lemmaDualEl,
  parseDcsFeats } from "./feats";
import { groupHeadEl } from "./group-ui";
import {
  GLOSS_MAX_CHARS, buildRankedGroups,
  clipGloss, glossIdentity, normLemma, rankedParses, type ParseGroup,
} from "./group";
import { attachMwGloss, compoundBlock, firstCompound, membersOf,
  mwGlossFor } from "./compound";
import type { AnalyzeCandidate, AnalyzeResult } from "./parser-wasm";

const glossShards = new Map<string, Record<string, Gloss> | null>();
async function loadGlossShard(letter: string):
  Promise<Record<string, Gloss> | null> {
  if (glossShards.has(letter)) return glossShards.get(letter)!;
  const shard = await fetchJSON<Record<string, Gloss> | null>(
    `data/gloss/${letter}.json`,
  ).catch(() => null);
  glossShards.set(letter, shard);
  return shard;
}

type El = HTMLElement;
const el = (tag: string, cls?: string, text?: string): El => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text; // never innerHTML
  return e;
};

/** Collapsed parse-column density: ONE best group-row per token — the
 *  greek-reader canonical (its fillParseCol renders a single best card +
 *  "+N" chip). Further readings live behind the chip / word panel. */
const COLLAPSED_ROWS = 1;

/** Language tag of the most recently rendered view ("pi" for Pali).
 *  Set per renderUnits call; consulted by primaryText so Pali words in
 *  panels/cards stay Roman even when the Devanagari pref is on. */
let viewLang: string | null = null;

/** el() for user-facing Sanskrit strings: renders via the current PRIMARY
 *  script (Devanagari when on, else IAST). Static after insert — word lines
 *  are handled by the unit-scripts registry instead. */
function primaryText(orig: string): string {
  if (viewLang === "pi") return orig; // Pali: already IAST Latin, pass through
  // direction detected per token (Upaniṣads ship IAST sources)
  const target = scriptPrefs().deva ? "deva" : "iast";
  return disp(orig, target);
}
const elDisp = (tag: string, cls: string | undefined, orig: string): El => {
  return el(tag, cls, primaryText(orig));
};

export interface RenderCtx {
  morph: Map<string, Parse[]>;
  gloss: Map<string, Gloss>;
  /** Accent-stripped forms known to be unanalysable (paste live pass). */
  unknown?: Set<string>;
  /** lemma -> occurrence count among this work's loaded tokens
   *  (ranking signal for parse disambiguation). */
  lemmaFreq?: Map<string, number>;
  /** Author register hint: "prose" enables the dialect penalty in the
   *  parse ranking; anything else is neutral. */
  genre?: string;
  /** Author TLG id when known (reader routes). Gates speaker coloring to
   *  dialogue works — undefined (e.g. paste view) means never color. */
  authorKey?: string;
  /** Work language tag ("pi" for Pali): Roman-script passthrough —
   *  no Devanagari conversion in lemma/panel display either. */
  lang?: string;
  /** Non-null means inline grammar is occurrence-DCS only: no surface fallback. */
  occurrence?: OccurrenceMorph | null;
}

/* ---------------- parse ranking ---------------- */

/** Dialect tags that mark a parse as off-register for classical prose. */
const PROSE_FOREIGN_DIALECTS = new Set([
  "epic", "homeric", "doric", "aeolic", "ionic",
]);

/** Authors whose works are classical/Koine PROSE (TLG id -> register).
 *  Poets and dramatists stay neutral; Herodotus writes Ionic prose, so
 *  he is deliberately not listed. Extend as new authors ship. */
const GENRE_BY_TLG: Record<string, string> = {
  tlg0003: "prose", // Thucydides
  tlg0007: "prose", // Plutarch
  tlg0010: "prose", // Isocrates
  tlg0014: "prose", // Demosthenes
  tlg0018: "prose", // Philo Judaeus
  tlg0026: "prose", // Aeschines
  tlg0027: "prose", // Andocides
  tlg0028: "prose", // Antiphon
  tlg0029: "prose", // Dinarchus
  tlg0030: "prose", // Hyperides
  tlg0031: "prose", // New Testament
  tlg0032: "prose", // Xenophon
  tlg0034: "prose", // Lycurgus
  tlg0059: "prose", // Plato
  tlg0060: "prose", // Diodorus Siculus
  tlg0062: "prose", // Lucian
  tlg0074: "prose", // Arrian
  tlg0081: "prose", // Dionysius of Halicarnassus
  tlg0086: "prose", // Aristotle
  tlg0093: "prose", // Theophrastus
  tlg0099: "prose", // Strabo
  tlg0284: "prose", // Aelius Aristides
  tlg0525: "prose", // Pausanias
  tlg0527: "prose", // Septuaginta
  tlg0532: "prose", // Achilles Tatius
  tlg0537: "prose", // Epicurus
  tlg0540: "prose", // Lysias
  tlg0543: "prose", // Polybius
  tlg0545: "prose", // Aelian
  tlg0548: "prose", // Apollodorus
  tlg0557: "prose", // Epictetus
  tlg0560: "prose", // Longinus
  tlg0561: "prose", // Longus
  tlg0562: "prose", // Marcus Aurelius
  tlg0612: "prose", // Dio Chrysostom
  tlg0627: "prose", // Hippocrates
};

/** Register for a catalog author; "" when neutral. */
export function genreFor(authorKey: string): string {
  return GENRE_BY_TLG[authorKey] ?? "";
}

/** Dialect tokens of a parse (x = dialects space-separated | stemtypes).
 *  Some shipped shard entries omit fields; stay defensive. */
function dialectTags(p: Parse): string[] {
  return ((p.x ?? "").split("|")[0] ?? "").split(/\s+/).filter(Boolean);
}

/** Pure ranking score for one candidate parse.
 *  Corpus frequency dominates (weight 10/log2); dialect flags cost 5. */
export function scoreParse(
  p: Parse,
  lemmaFreq?: Map<string, number>,
  genre?: string,
): number {
  let s = 0;
  const f = lemmaFreq?.get(stripAccents(p.l ?? "")) ?? 0;
  s += Math.log2(1 + f) * 10;
  if (
    genre === "prose" &&
    dialectTags(p).some((d) => PROSE_FOREIGN_DIALECTS.has(d))
  ) {
    s -= 5;
  }
  return s;
}

/** Indices into `parses`, best-ranked first. Stable tiebreak: original order. */
export function rankParses(
  parses: Parse[],
  lemmaFreq?: Map<string, number>,
  genre?: string,
): number[] {
  return parses
    .map((p, i) => ({ i, s: scoreParse(p, lemmaFreq, genre) }))
    .sort((a, b) => b.s - a.s || a.i - b.i)
    .map((x) => x.i);
}

/** Add every candidate lemma of every parsed token to ctx.lemmaFreq.
 *  Call once per freshly loaded batch to grow the work-view signal.
 *
 *  PLAUSIBILITY GATE (gold-reconcile): folded shard keys merge distinct
 *  words ("atha"->"ata" holds अथ + MW-junk च rows). Counting EVERY
 *  candidate lemma per occurrence let junk homographs accumulate fake
 *  frequency and win ranking — a self-reinforcing loop. Count a lemma
 *  only when it is plausibly a reading of THIS surface: exact match,
 *  shared raw prefix, or folded-key common prefix >= 2. */
export function tallyLemmas(ctx: RenderCtx, units: Unit[]): void {
  if (!ctx.lemmaFreq) ctx.lemmaFreq = new Map();
  const freq = ctx.lemmaFreq;
  for (const u of units) {
    for (const w of u.words) {
      for (const p of ctx.morph.get(stripAccents(w)) ?? []) {
        const l = stripAccents(p.l);
        if (!l) continue;
        if (!plausibleLemma(w, l)) continue;
        freq.set(l, (freq.get(l) ?? 0) + 1);
      }
    }
  }
}

/** True when `lemma` may be counted as an in-work reading of `word`.
 *  Only TOTALLY unrelated shapes are excluded (raw and folded common
 *  prefix both empty — e.g. MW-junk च inside the "atha" bucket). Sandhi
 *  pairs (तेन↔तद् share just "t") must stay counted: excluding them would
 *  hand frequency to exactly the junk homographs that share more letters.
 *  2026-08-27: sandhi fusions (चैव→एव, चैनं→एनद्) were excluded because the
 *  lemma is a suffix, not a prefix — check suffix + containment as well
 *  so that trailing constituents get their frequency counted and can win
 *  ranking (gold-reconcile: चैव WRONG-TOP च vs एव). */
function plausibleLemma(word: string, lemma: string): boolean {
  const a = normLemma(stripAccents(word));
  const b = normLemma(lemma);
  if (!a || !b || a === b) return true;
  if (a.startsWith(b) || b.startsWith(a)) return true;
  if (a.endsWith(b) || b.endsWith(a)) return true;
  if (a.includes(b) || b.includes(a)) return true;
  const fa = slp1KeyFor(a);
  const fb = slp1KeyFor(b);
  let n = Math.min(fa.length, fb.length);
  let lcp = 0;
  while (lcp < n && fa[lcp] === fb[lcp]) lcp += 1;
  if (lcp >= 1) return true;
  // suffix on SLP1 as well (eva vs ceva)
  let lcs = 0;
  while (lcs < n && fa[fa.length - 1 - lcs] === fb[fb.length - 1 - lcs]) lcs += 1;
  if (lcs >= 2) return true;
  n = Math.min(a.length, b.length);
  let rl = 0;
  while (rl < n && a[rl] === b[rl]) rl += 1;
  if (rl >= 1) return true;
  // suffix on raw as well
  let rs = 0;
  while (rs < n && a[a.length - 1 - rs] === b[b.length - 1 - rs]) rs += 1;
  return rs >= 2;
}

/**
 * Feature tokens of candidate idx that vary within its same-lemma group,
 * e.g. ["acc"] vs ["dat"] — the disagreement made scannable. DCS feature
 * strings are ";"/space-separated ("पुं;1;एक"), so both separators split.
 */
export function diffTokens(fs: string[], idx: number): string[] {
  if (fs.length < 2) return [];
  const sets = fs.map((f) =>
    new Set((f ?? "").split(/[;\s|]+/).filter(Boolean)));
  return Array.from(sets[idx]).filter((t) =>
    !sets.every((s) => s.has(t)),
  );
}

/* expansion state persists per word-form while one work view is on screen.
 * All columns of the same form expand/collapse together: a live registry
 * keeps every rendered column in sync with the set (common words like
 * "ὅτι" appear many times per view). */
let expandedView: El | null = null;
const expandedForms = new Set<string>();
const colsByForm = new Map<string, Array<{ col: El; word: string }>>();
let currentCtx: RenderCtx | null = null;
const occurrenceByCol = new WeakMap<El, Parse[]>();

function resetExpansion(container: El): void {
  if (expandedView !== container) {
    expandedView = container;
    expandedForms.clear();
    colsByForm.clear();
  }
}

/** Re-render every live parse column against the expansion set. */
function rerenderAll(): void {
  if (!currentCtx) return;
  for (const arr of colsByForm.values()) {
    for (const entry of arr) {
      if (entry.col.isConnected) fillParseCol(entry.col, entry.word, currentCtx,
        occurrenceByCol.get(entry.col));
    }
  }
}

/** Expand every multi-candidate word in the current view. */
export function expandAll(): void {
  if (!currentCtx || !expandedView?.isConnected) return;
  for (const [key, arr] of colsByForm) {
    const entry = arr.find((e) => e.col.isConnected);
    if (!entry) continue;
    if ((currentCtx.morph.get(key)?.length ?? 0) > 1) expandedForms.add(key);
  }
  rerenderAll();
}

/** Collapse everything back to best-parse cards. */
export function collapseAll(): void {
  if (!expandedForms.size) return;
  expandedForms.clear();
  rerenderAll();
}

/** Keyboard shortcut: E toggles all candidates in the current view. */
function onGlobalKey(e: KeyboardEvent): void {
  if (e.key !== "e" && e.key !== "E") return;
  const t = e.target as HTMLElement | null;
  if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" ||
    t.isContentEditable)) return;
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (!currentCtx || !expandedView?.isConnected) return;
  e.preventDefault();
  if (expandedForms.size) collapseAll();
  else expandAll();
}
document.addEventListener("keydown", onGlobalKey);

let pruneQueued = false;

/** Prune disconnected columns from every registry entry — DEFERRED to a
 *  macrotask. A synchronous isConnected filter here was a corpus-wide bug
 *  (Yamaka/Paṭṭhāna): parseCards registers columns while their row is still
 *  DETACHED (parseRow appends to `row` before `container.appendChild(row)`),
 *  so on pages where one form repeats >64× the prune discarded freshly
 *  pushed not-yet-connected columns — their 「另有 N 解」 chips then expanded
 *  every OTHER instance of the form while staying collapsed themselves. */
function queueColPrune(): void {
  if (pruneQueued) return;
  pruneQueued = true;
  setTimeout(() => {
    pruneQueued = false;
    for (const [k, list] of colsByForm) {
      const live = list.filter((e) => e.col.isConnected);
      if (live.length) colsByForm.set(k, live);
      else colsByForm.delete(k);
    }
  }, 0);
}

function registerCol(key: string, col: El, word: string): void {
  let arr = colsByForm.get(key);
  if (!arr) colsByForm.set(key, (arr = []));
  arr.push({ col, word });
  // memory guard: prune lazily, NEVER synchronously against mid-render
  // (detached) columns — see queueColPrune.
  if (arr.length > 64) queueColPrune();
}

/** Flip expansion for one word-form and re-render every live column. */
function toggleExpanded(word: string, ctx: RenderCtx): void {
  const key = stripAccents(word);
  if (!expandedForms.delete(key)) expandedForms.add(key);
  for (const entry of colsByForm.get(key) ?? []) {
    if (!entry.col.isConnected) continue;
    fillParseCol(entry.col, entry.word, ctx);
  }
}

/** Merge freshly loaded shards into an accumulating context. */
export function mergeCtx(
  ctx: RenderCtx,
  morph: Map<string, Parse[]>,
  gloss: Map<string, Gloss>,
): RenderCtx {
  for (const [k, v] of morph) if (!ctx.morph.has(k)) ctx.morph.set(k, v);
  for (const [k, v] of gloss) if (!ctx.gloss.has(k)) ctx.gloss.set(k, v);
  return ctx;
}

/** Load every analysis + gloss needed for these units (shards cached).
 *  `scope` = catalog work id — narrows the surface-index lookup to that
 *  work's per-work slice when available. */
export async function prepare(
  units: Unit[],
  scope?: string,
): Promise<RenderCtx> {
  const forms = units.flatMap((u) => u.words);
  const occurrence = await loadOccurrenceMorph(units, scope);
  // A migrated work must never draw inline grammar from global surface shards.
  const morph = occurrence ? new Map<string, Parse[]>() : await loadMorph(forms, scope);
  const lemmas: string[] = [];
  for (const w of new Set(forms)) {
    for (const p of morph.get(stripAccents(w)) ?? []) lemmas.push(p.l);
  }
  const gloss = await loadGloss(lemmas);
  return { morph, gloss, occurrence };
}

function parseCards(word: string, ctx: RenderCtx, ref?: string, tokenIndex?: number): El {
  const col = el("div", "pcol");
  registerCol(stripAccents(word), col, word);
  const occurrence = ctx.occurrence && ref !== undefined && tokenIndex !== undefined
    ? ctx.occurrence.get(`${ref}\u0000${tokenIndex}`) ?? [] : undefined;
  if (occurrence !== undefined) occurrenceByCol.set(col, occurrence);
  fillParseCol(col, word, ctx, occurrence);
  return col;
}

/* ---------------- ranked (lemma × POS-class) groups ----------------
 * kim/ka disaster fix: shard arrays accumulate EVERY corpus occurrence's
 * feature combo, so high-frequency forms rendered paradigm walls. The
 * display now GROUPS by (lemma, POS-class), ranks indeclinable readings and
 * exact surface-form lemmas first, demotes proper-name homographs, and
 * clips MW essay glosses to their first sentence.
 *
 * Presentation density converged to greek-reader (śatakatraya pile-up fix):
 * the COLLAPSED column shows exactly ONE best-ranked group-row (+ 「另有 N 解」
 * chip when further groups exist); samāsa blocks render only on demand —
 * in the expanded column or the word panel — never stacked under every
 * token. Full detail stays one click away (chip / word click). */

/** Sync gloss text for ranking priors from the loaded ctx.gloss map. */
function groupOpts(ctx: RenderCtx, word?: string): {
  base: (p: Parse) => number;
  glossOf: (l: string) => string | undefined;
  form?: string;
} {
  return {
    base: (p) => scoreParse(p, ctx.lemmaFreq, ctx.genre),
    glossOf: (l) => ctx.gloss.get(stripAccents(l))?.g,
    form: word,
  };
}

/**
 * One group row: `lemma abbr-feat-summary — short-gloss`. Wide variation
 * prints compact SET notation ("m./n., sg./du./pl., various cases") instead
 * of enumerating combos; the full grid lives only in the word panel.
 * The gloss cell is appended empty; the caller paints it (deterministic
 * repeat-suppression across a token's rows).
 */
function groupRow(g: ParseGroup): El {
  const row = el("div", "pcard pcard-compact cand-row");
  row.appendChild(groupHeadEl(g));
  row.appendChild(el("div", "gloss mw-gloss"));
  return row;
}

/**
 * Paint every group row's gloss cell of one token IN ROW ORDER once all
 * lookups settle: clipped at the first sentence boundary ≤120 chars
 * (spec 4), suppressed entirely when an earlier row already showed the
 * identical gloss. 无词条 → cell removed silently (R3).
 */
function paintGroupGlosses(items: Array<{ row: El; lemma: string }>): void {
  void Promise.all(
    items.map((it) => mwGlossFor(it.lemma ?? "")),
  ).then((txts) => {
    const seen = new Set<string>();
    items.forEach((it, i) => {
      const cell = it.row.querySelector(":scope > .mw-gloss") as El | null;
      if (!cell || !cell.isConnected) return; // column re-rendered meanwhile
      const t = txts[i];
      if (!t) {
        cell.remove();
        return;
      }
      const id = glossIdentity(t);
      if (seen.has(id)) {
        cell.remove(); // identical gloss already shown on an earlier row
        return;
      }
      seen.add(id);
      cell.textContent = clipGloss(t, GLOSS_MAX_CHARS);
    });
  });
}

/** 「另有 N 解」 chip for group-rows beyond the collapsed cap. N counts
 *  hidden GROUPS (not raw analyses) so the label matches what expansion adds. */
function expandChip(
  word: string,
  nHidden: number,
  totalGroups: number,
  ctx: RenderCtx,
): HTMLButtonElement {
  const chip = el("button", "more-chip", `另有 ${nHidden} 解`) as
    HTMLButtonElement;
  chip.lang = "zh";
  chip.type = "button";
  chip.title = `${totalGroups} distinct readings — click to compare`;
  chip.setAttribute(
    "aria-label",
    `${totalGroups} readings for ${word}; ${nHidden} more — click to show all`,
  );
  chip.addEventListener("click", () => toggleExpanded(word, ctx));
  return chip;
}

/** Card-display lemma: DCS homonym digits ("दृश्1" -> "दृश्") are
 *  disambiguation noise for readers; the raw lemma still feeds gloss
 *  lookups and the word panel. */
function dispLemma(lemma: string): string {
  return (lemma || "").replace(/^(.*\D)\d+$/, "$1");
}

/** Expanded-detail extras of one analysis: unmapped f-extras + x field
 *  (dialects / stem types / compound TYPE) — muted, detail only (R2/R5). */
function extrasLine(p: Parse): El | null {
  const { extras } = parseDcsFeats(p.f ?? "");
  const xToks = (p.x ?? "").split(/[|\s]+/).filter(Boolean);
  const all = [...extras, ...xToks];
  if (!all.length) return null;
  return el("div", "feats feat-extras", all.join(" · "));
}

/** (Re)render one word's parse column per current expansion state. */
function fillParseCol(col: El, word: string, ctx: RenderCtx, occurrence?: Parse[]): void {
  col.replaceChildren();
  const key = stripAccents(word);
  // dedupe BEFORE rendering the candidate list (idempotent: loadMorph
  // already drops identical triplets at collection time; live/paste-built
  // contexts may not have passed through it)
  const parses = dedupeParses(occurrence ?? ctx.morph.get(key) ?? []);
  if (parses.length === 0) {
    // R4 honesty gate: NO parse card of any kind — the column stays empty
    // (it must still occupy its slot so cards align under their words);
    // the word remains clickable → dictionary panel.
    appendDeepEntry(col, word); // wasm flag only — no-op otherwise
    return;
  }

  // GROUP by (lemma, POS-class) and rank with priors (kim/ka fix). Collapsed
  // density = greek-reader: ONE best group-row + chip; expansion (chip click
  // / word click / key E) reveals every group. Never a raw paradigm wall.
  const groups = buildRankedGroups(parses, groupOpts(ctx, word));
  if (!groups.length) {
    appendDeepEntry(col, word);
    return;
  }
  const expanded = expandedForms.has(key) && groups.length > 1;
  // Strict one-parse-line per token: never stack multiple group rows vertically.
  // Collapsed and expanded both show exactly one best row + chip; full paradigm
  // lives in the word panel, not as a block pile under the token.
  const visible = groups.slice(0, COLLAPSED_ROWS);
  const painted: Array<{ row: El; lemma: string }> = [];
  for (const g of visible) {
    const row = groupRow(g);
    col.appendChild(row);
    painted.push({ row, lemma: g.lemma });
  }
  paintGroupGlosses(painted);
  if (groups.length > COLLAPSED_ROWS) {
    col.appendChild(expandChip(
      word,
      groups.length - COLLAPSED_ROWS,
      groups.length,
      ctx,
    ));
  }
  // samāsa block: on-demand detail only — only when expanded, but still
  // below the single parse line, not as a pile of candidates.
  if (expanded) {
    const comp = compoundFor(word, ctx);
    if (comp) col.appendChild(comp);
  }
  appendDeepEntry(col, word); // wasm flag only — no-op otherwise
}

/** Compound-member mini-rows for this word: first PRIOR-RANKED parse that
 *  carries a member chain wins. Null when the word isn't a compound (or the
 *  shards carry no chain for it). */
function compoundFor(word: string, ctx: RenderCtx): El | null {
  const parses = ctx.morph.get(stripAccents(word)) ?? [];
  if (!parses.length) return null;
  return firstCompound(rankedParses(parses, groupOpts(ctx, word)));
}

/* ---------------- wasm deep parse (opt-in enhancement) ----------------
 * Client-side sandhi split + morphology via public/wasm/webdemo.wasm,
 * gated behind ?wasm=1 / localStorage wasmParser=1. Flag OFF ⇒ not even
 * the module chunk is fetched and fillParseCol output is byte-identical
 * to pre-wasm rendering. Any failure degrades silently back to the shard
 * path — the entry button removes itself rather than dead-ending.
 * KI-10 honesty fields (integration-guide §3.1) are read defensively:
 * artifacts older than W2c omit them, in which case no badge renders. */

/** KI-10 fields on top of the typed facade (optional, may be absent). */
type DeepCand = AnalyzeCandidate & {
  level?: string;
  attestation?: string[];
  undetermined?: boolean;
};

function wasmFlagOn(): boolean {
  try {
    if (new URLSearchParams(location.search).has("wasm")) return true;
    return localStorage.getItem("wasmParser") === "1";
  } catch {
    return false;
  }
}

type WasmMod = typeof import("./parser-wasm");
let wasmModPromise: Promise<WasmMod | null> | null = null;
function wasmMod(): Promise<WasmMod | null> {
  if (!wasmModPromise) {
    wasmModPromise = import("./parser-wasm").catch(() => null);
  }
  return wasmModPromise;
}

/* Facade-first with a direct-load fallback (defense in depth). The kit's
 * static capability probe (parser-wasm.ts PROBE_BYTES) used to mis-encode its
 * type section and fail validate() everywhere; that probe is now FIXED (same
 * corrected sequence as moonbit-samsaadhanii/web/main.js), so the facade path
 * loads normally. This private loader stays as a belt-and-braces fallback in
 * case the facade module fails to import/init for any other reason. All
 * failures resolve false / null — never throw. */

interface DeepExports {
  analyze_word(deva: string): string;
  morph_lookup(deva: string): string;
}
let deepExp: DeepExports | null = null;
let deepInitPromise: Promise<boolean> | null = null;

function deepInit(): Promise<boolean> {
  if (!deepInitPromise) {
    deepInitPromise = (async () => {
      try {
        const url = new URL("wasm/webdemo.wasm", document.baseURI).href;
        const res = await fetch(url);
        if (!res.ok) return false;
        // arrayBuffer(), not instantiateStreaming: immune to wrong
        // Content-Type (integration-guide §2)
        const bytes = await res.arrayBuffer();
        const inst3 = WebAssembly.instantiate as unknown as (
          b: BufferSource,
          i: WebAssembly.Imports,
          o: { builtins: string[]; importedStringConstants: string },
        ) => Promise<WebAssembly.WebAssemblyInstantiatedSource>;
        const { instance } = await inst3(bytes, {}, {
          builtins: ["js-string"],
          importedStringConstants: "_",
        });
        const e = instance.exports as unknown as DeepExports;
        if (typeof e.analyze_word !== "function") return false;
        deepExp = e;
        return true;
      } catch {
        return false;
      }
    })();
  }
  return deepInitPromise;
}

async function deepReady(): Promise<boolean> {
  const m = await wasmMod();
  if (m && (await m.initParser())) return true; // facade healthy (post-fix)
  return deepInit(); // private fallback loader
}

/** analyzeWord via the healthy path (facade or fallback); null ⇒ degrade. */
async function deepAnalyze(deva: string): Promise<AnalyzeResult | null> {
  if (!(await deepReady())) return null;
  const m = await wasmMod();
  const viaFacade = m ? m.analyzeWord(deva) : null;
  if (viaFacade && viaFacade.candidates.length > 0) return viaFacade;
  if (!deepExp) return viaFacade;
  try {
    const v = JSON.parse(deepExp.analyze_word(deva)) as AnalyzeResult | null;
    if (!v || !Array.isArray(v.candidates)) return null;
    return v.candidates.every((c) => c && Array.isArray(c.parts_deva) &&
      Array.isArray(c.parts_iast))
      ? v
      : null;
  } catch {
    return null;
  }
}

interface MorphRow {
  lemma_iast?: string;
  lemma_deva?: string;
  pos?: string;
  feats?: string[];
}

/** morphLookup via the healthy path (facade or fallback). */
async function deepMorph(
  part: string,
): Promise<{ found: boolean; rows: MorphRow[] } | null> {
  if (!(await deepReady())) return null;
  const m = await wasmMod();
  const mr = m ? m.morphLookup(part) : null;
  if (mr) {
    return mr.found
      ? { found: true, rows: mr.analyses }
      : { found: false, rows: [] };
  }
  if (!deepExp) return null;
  try {
    const v = JSON.parse(deepExp.morph_lookup(part)) as
      | { found?: boolean; analyses?: MorphRow[] }
      | null;
    if (!v || typeof v.found !== "boolean" || !Array.isArray(v.analyses)) {
      return null;
    }
    return { found: v.found, rows: v.analyses };
  } catch {
    return null;
  }
}

/** Idle-time warmup so the first click skips the ~80 ms cold start.
 *  Idempotent; a no-op unless the flag is on. */
let wasmWarmed = false;
function warmWasmParser(): void {
  if (wasmWarmed || !wasmFlagOn()) return;
  wasmWarmed = true;
  const g = globalThis as {
    requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number;
  };
  const kick = () => void wasmMod().then(() => deepReady()).catch(() => {});
  if (typeof g.requestIdleCallback === "function") {
    g.requestIdleCallback(kick, { timeout: 3000 });
  } else {
    setTimeout(kick, 200);
  }
}

/** Devanagari form for the parser (tokens may ship as IAST); "" when the
 *  view has no Devanagari reality (Pali renders Roman-only). */
function devaForm(word: string): string {
  if (viewLang === "pi") return "";
  return disp(word, "deva");
}

/** The per-word entry chip. Appends nothing when the flag is off or the
 *  view language can't feed the Devanagari parser. */
function appendDeepEntry(col: El, word: string): void {
  if (!wasmFlagOn() || viewLang === "pi") return;
  warmWasmParser();
  const b = el("button", "more-chip wasm-deep-btn", "深度解析") as HTMLButtonElement;
  b.type = "button";
  b.title = "Deep sandhi analysis (client-side wasm)";
  b.setAttribute("aria-label", `Deep analysis of ${word}`);
  b.addEventListener("click", () => void toggleDeep(col, word));
  col.appendChild(b);
}

async function toggleDeep(col: El, word: string): Promise<void> {
  const prev = col.querySelector(":scope > .wasm-deep");
  if (prev) {
    prev.remove(); // second click collapses
    return;
  }
  const btn = col.querySelector(":scope > .wasm-deep-btn") as HTMLButtonElement | null;
  const box = el("div", "pcard wasm-deep");
  box.setAttribute("aria-live", "polite");
  box.textContent = "…";
  col.appendChild(box);
  const deva = devaForm(word);
  const res = deva ? await deepAnalyze(deva) : null;
  if (!box.isConnected) return; // column re-rendered meanwhile
  if (!res || res.candidates.length === 0) {
    // 静默降级：撤除入口，回到既有 shard 路径，绝不阻塞
    box.remove();
    btn?.remove();
    return;
  }
  box.replaceChildren(...deepChildren(res));
}

function deepChildren(res: AnalyzeResult): El[] {
  const out: El[] = [];
  for (const c of res.candidates as DeepCand[]) {
    const row = el("div", "pcard cand-row wasm-cand");
    const head = el("div", "cand-head");
    // KI-10 undetermined → dashed frame + 「未裁定」ribbon
    if (c.undetermined) {
      row.style.borderTop = "none";
      row.style.border = "1px dashed var(--border-strong)";
      row.style.borderRadius = "var(--radius-s)";
      row.style.padding = "4px 6px";
      head.appendChild(el("span", "diff-badge", "未裁定"));
    }
    // KI-10 level Low → amber dot (spk0 adapts to both themes)
    if (c.level === "Low" || c.level === "NoIdea") {
      const dot = el("span");
      dot.style.cssText =
        "display:inline-block;width:8px;height:8px;border-radius:999px;background:var(--spk0,#b45309);flex:none;";
      dot.title = `confidence ${c.level}`;
      dot.setAttribute("aria-label", `confidence ${c.level}`);
      head.appendChild(dot);
    }
    // candidate parts: clickable chips feeding morph_lookup
    for (let j = 0; j < c.parts_deva.length; j++) {
      if (j > 0) head.appendChild(el("span", undefined, "+"));
      const part = elDisp("span", "lemma w wasm-part", c.parts_deva[j]);
      part.title = `${c.parts_iast[j] ?? ""} — click for morphology`;
      // KI-10 attestation ParadigmOnly → 「仅理论存在」corner tag
      if (c.attestation && c.attestation[j] === "ParadigmOnly") {
        const po = el("span", "diff-badge", "仅理论存在");
        po.style.cssText = "font-size:0.56rem;padding:1px 3px;margin-left:2px;";
        po.title = "ParadigmOnly — 形状合法但词库未见";
        part.appendChild(po);
      }
      part.addEventListener("click", () =>
        void toggleMorph(row, c.parts_deva[j] ?? "", c.parts_iast[j] ?? ""));
      head.appendChild(part);
    }
    row.appendChild(head);
    const hits = typeof c.hits === "number" ? c.hits : 0;
    const members = typeof c.members === "number" ? c.members : c.parts_deva.length;
    row.appendChild(el("div", "feats",
      `hits ${hits}/${members}${res.total > res.candidates.length ? ` · of ${res.total}` : ""}`));
    out.push(row);
  }
  return out;
}

/** Part-chip click: wasm morph_lookup inline (entry/drawer vocabulary),
 *  plus a jump into the existing lexicon drawer. */
async function toggleMorph(row: El, partDeva: string, partIast: string): Promise<void> {
  const prev = row.querySelector(":scope > .wasm-morph");
  if (prev) {
    prev.remove();
    return;
  }
  const block = el("div", "wasm-morph");
  block.style.marginTop = "4px";
  block.textContent = "…";
  row.appendChild(block);
  const mr = await deepMorph(partDeva);
  if (!block.isConnected) return;
  block.replaceChildren();
  const rows = (mr?.rows ?? []).filter((a) =>
    a && typeof a.pos === "string" && Array.isArray(a.feats));
  if (!mr || !mr.found || rows.length === 0) {
    // honest miss — not an error
    block.appendChild(el("div", "noparse", "morph 子集未收录"));
    return;
  }
  for (const a of rows.slice(0, 4)) {
    const entry = el("div", "entry");
    entry.appendChild(elDisp("span", "lemma",
      a.lemma_iast || a.lemma_deva || `(${a.pos})`));
    entry.appendChild(el("div", "feats", [a.pos, ...(a.feats ?? [])].join(" · ")));
    block.appendChild(entry);
  }
  const jump = el("button", undefined, "Lexicon ↗") as HTMLButtonElement;
  jump.type = "button";
  jump.addEventListener("click", () => openLexicon(partIast || devToIast(partDeva)));
  block.appendChild(jump);
}

/** Render interlinear units into container.
 *  kind "verse": one row per unit — ref label, Greek line, cards beneath.
 *  kind "prose": ref badge + flowing paragraph of words, cards beneath.
 *  baseIndex: cumulative unit offset (prose refs show every 5th chunk).
 *  Refs render VERBATIM — Stephanus/Bekker/book.line strings as shipped.
 *  Header fix: every unit gets a deterministic .unit-head with ref + grouped
 *  actions (TTS 🔊 + AI). Buttons are inline flex gap at header end (right-aligned),
 *  never between greek lines and parse rows. No MutationObserver mid-unit. */

let currentProsodyWorkId: string | null = null;

export function setProsodyWorkId(id: string | null): void {
  currentProsodyWorkId = id;
}

/** Shipped data refs repeat when an edition chunks one verse into several
 *  units. DOM refs must be unique for deep links / resume tracking, so the
 *  first occurrence keeps the verbatim ref and repeats get letter suffixes:
 *  1.2a, 1.2b, … Counts are keyed per container (one reader view = one
 *  work), so pagination continues the sequence and route changes reset it.
 *  unit.ref itself is NEVER mutated — translation alignment matches on it. */
const refCountsByRoot = new WeakMap<El, Map<string, number>>();

export function uniqueDomRef(container: El, ref: string): string {
  let counts = refCountsByRoot.get(container);
  if (!counts) {
    counts = new Map();
    refCountsByRoot.set(container, counts);
  }
  const n = counts.get(ref) ?? 0;
  counts.set(ref, n + 1);
  if (n === 0) return ref;
  return n <= 26 ? `${ref}${String.fromCharCode(96 + n)}` : `${ref}${n}`;
}

export function renderUnits(
  container: El,
  units: Unit[],
  ctx: RenderCtx,
  kind: "verse" | "prose" = "verse",
  baseIndex = 0,
): void {
  resetExpansion(container);
  currentCtx = ctx;
  viewLang = ctx.lang ?? null;
  units.forEach((unit, uIdx) => {
    const row = el("div", kind === "prose" ? "unit prose-unit" : "line");
    // unique per-work DOM ref (repeated verse chunks get letter suffixes);
    // unit.ref stays verbatim for translation alignment
    const domRef = unit.ref ? uniqueDomRef(container, unit.ref) : null;
    if (domRef) row.dataset.ref = domRef; // deep-link / resume target    // Deterministic header: ref + right-aligned grouped actions (TTS + AI)
    const head = el("div", "unit-head");
    // prose-head alias for backward compat + styling
    if (kind === "prose") head.classList.add("prose-head");
    const showRef = kind === "verse" ? !!unit.ref : !!(unit.ref && (baseIndex + uIdx) % 5 === 0);
    if (showRef && domRef) {
      const refEl = el("span", kind === "verse" ? "ref-label" : "ref-badge", domRef);
      if (kind === "verse") refEl.title = `ref ${domRef}`;
      head.appendChild(refEl);
    }
    const actions = el("div", "unit-actions");
    const star = starButtonFor(domRef ?? unit.ref);
    if (star) actions.appendChild(star);
    const copy = copyLinkButtonFor(domRef ?? unit.ref);
    if (copy) actions.appendChild(copy);
    head.appendChild(actions);
    row.appendChild(head);

    // dual-script container: Devanagari line first (primary), optional IAST
    // second; grid columns keep word cells aligned across both lines.
    // "greek-line" kept as a legacy-compat hook: vocab dimming, translation
// scroll-sync and postbuild tooling select on it.
const scripts = el("div", "unit-scripts greek-line");
    scripts.setAttribute("lang", "sa");
    const spkCount = speakerSpanCount(unit, ctx);
    const speakers = unit.words.map((_, i) => i < spkCount);
    registerUnitScripts(scripts, {
      deva: unit.words.slice(),
      speakers,
      lang: ctx.lang,
      onWord: (i, sp) => {
        const w = unit.words[i];
        openPanel(sp, w, ctx);
        const parses = ctx.morph.get(stripAccents(w)) ?? [];
        if (parses.length > 1) toggleExpanded(w, ctx);
      },
    });
    row.appendChild(scripts);

    const parseRow = el("div", "parse-row");
    unit.words.forEach((w, i) => {
      if (speakers[i]) return; // speaker labels get no parse column
      parseRow.appendChild(parseCards(w, ctx, unit.ref, i));
    });
    // Regression fix (3026b36 dropped this line): the parse cards were built
    // but never attached — every line rendered with NO grammatical parsing.
    row.appendChild(parseRow);
    container.appendChild(row);
    // NOTE: no registerForReflow here. The vline splitter assumes flat .w
    // spans in one wrapping line; unit-scripts stacks each token's scripts
    // in a per-word cell, so splitting by offsetTop would scramble it.
  });
  applyClasses(); // vocab dimming + stats chip for the freshly rendered page
}

/* ---------------- speaker labels ---------------- */

/** Proper-name speaker lexicon: the ONLY words that may ever render as a
 *  colored speaker label. Extend as dialogue works ship. */
export const SPEAKER_LEMMAS = new Set<string>([
  // Platonic cast
  "σωκρατησ", "πλατων", "φαιδρος", "γλαυκων", "αδειμαντοσ",
  "θρασυμαχοσ", "πολεμαρχοσ", "κεφαλοσ", "λυσις", "μενοξενοσ",
  "χαρμιδησ", "ιππιας", "πρωταγορας", "μενων", "κριτιας", "τιμαιοσ",
  "ερμογονης", "απολλοδωρος", "παμφιλος", "εικρατης", "ιων",
  "κριτων", "κεβεισ", "σιμμιασ", "ευθυφρων", "κριτωνα", "κεβεισοσ",
  // include stripped variants without accents for robustness (stripAccents lower)
  "σωκρατεσ", "κριτωνοσ",
  // MSS speaker abbreviations used by dialogue editions (ΣΩ, ΙΩΝ, ΚΡ)
  "σω", "σοκ", "κρ", "κρι",
  // NT / LXX frequent actors
  "ιησους", "πετρος", "παυλος", "ιωαννησ", "μωυσησ", "πιλατος",
  "ηρως", "δαβιδ", "αβρααμ",
]);

/** Works whose editions carry REAL speaker labels (dramatic dialogues).
 *  Speaker coloring is gated to these: in epistles, histories and scripture
 *  a leading proper name is the narrator's subject or a vocative addressee
 *  ("ΠΑΥΛΟΣ…", ἀδελφοί), never the voice speaking. */
const DIALOGUE_TLGS = new Set([
  "tlg0006", // Euripides
  "tlg0011", // Sophocles
  "tlg0019", // Aristophanes
  "tlg0059", // Plato
  "tlg0062", // Lucian
  "tlg0085", // Aeschylus
]);

/** Morpheus marks person names with a "pers" feature token; used only to
 *  resolve a canonical lemma/label once a word already passed the lexicon
 *  gate — it no longer qualifies a word on its own. */
export function isPersonParse(p: Parse): boolean {
  return (
    /\bpers\b/.test(p.f ?? "") ||
    /\bpers\b/.test(p.x ?? "") ||
    SPEAKER_LEMMAS.has(stripAccents(p.l ?? ""))
  );
}

function isTitleCase(word: string): boolean {
  if (!word) return false;
  const first = word[0];
  const rest = word.slice(1);
  const isUpper = first !== first.toLowerCase() && first === first.toUpperCase();
  if (!isUpper) return false;
  // rest lowercase or empty (allows ΙΩΝ all-caps to be handled separately)
  return rest === rest.toLowerCase();
}
function isAllCapsGreek(word: string): boolean {
  return word.length >= 2 && word === word.toUpperCase() && word !== word.toLowerCase();
}

/**
 * Speaker test, tightened after false positives in 1 Corinthians:
 * the form must LOOK like a speaker label (TitleCase name or all-caps MSS
 * abbreviation such as ΣΩ / ΙΩΝ / ΚΡ) AND its accent-stripped form must be
 * in the SPEAKER_LEMMAS proper-name lexicon. Previously ANY all-caps token
 * (ΚΑΙ, ΔΕ…) or any parse carrying a "pers" tag qualified — which coloured
 * epistle openings like ΠΑΥΛΟΣ κλητὸς ἀπόστολος as a "speaker".
 */
function isSpeakerWord(word: string): boolean {
  const stripped = stripAccents(word);
  return (
    (isTitleCase(word) || isAllCapsGreek(word)) &&
    SPEAKER_LEMMAS.has(stripped)
  );
}

/** How many LEADING words are person names (cap 2). Genre-gated: coloring
 *  only happens for known dialogue works. */
export function speakerSpanCount(unit: Unit, ctx: RenderCtx): number {
  if (!ctx.authorKey || !DIALOGUE_TLGS.has(ctx.authorKey)) return 0;
  const n = Math.min(2, unit.words.length);
  let count = 0;
  for (let i = 0; i < n; i++) {
    if (isSpeakerWord(unit.words[i])) count += 1;
    else break;
  }
  return count;
}

export function hashColor(s: string): number {
  let h = 0;
  for (const ch of s) h = (h * 31 + (ch.codePointAt(0) ?? 0)) >>> 0;
  return h % 10;
}

/** Speaker color for a unit (first leading person name), or null. */
export function getSpeakerColor(unit: Unit, ctx: RenderCtx): number | null {
  const n = speakerSpanCount(unit, ctx);
  if (n === 0) return null;
  const w = unit.words[0];
  const parses = ctx.morph.get(stripAccents(w)) ?? [];
  const hit = parses.find((p) => isPersonParse(p));
  // fallback canonical is the stripped word itself when pers missing
  const canonical = stripAccents(hit?.l || w);
  return hashColor(canonical);
}

/** Canonical speaker lemma / form for label, or null. */
export function getSpeakerLabel(unit: Unit, ctx: RenderCtx): string | null {
  const n = speakerSpanCount(unit, ctx);
  if (n === 0) return null;
  const w = unit.words[0];
  const parses = ctx.morph.get(stripAccents(w)) ?? [];
  const hit = parses.find((p) => isPersonParse(p));
  return hit?.l || w;
}

/** Style one word span as a speaker label with a stable per-name color. */
function markSpeaker(span: El, w: string, parses: Parse[]): void {
  const hit = parses.find((p) => isPersonParse(p));
  const canonical = stripAccents(hit?.l || w);
  span.classList.add("speaker", `spk-${hashColor(canonical)}`);
  span.title = `speaker: ${hit?.l || w}`;
}

/* ---------------- parse-area cap ---------------- */

/* ---------------- viewport-width interlinear reflow ----------------
 * Greek text wraps naturally in the browser; once a row is near the
 * viewport we READ the browser's own wrap points (word-span offsetTop
 * groups) and restructure the DOM so every VISUAL line gets its parse
 * cards directly beneath it — NoDictionaries-style. Repacked on
 * container resize (debounced), font-size change, and web-font load.
 * Only rows within ~1 screen ahead are processed. */

interface ReflowEntry {
  row: El;
  done: boolean;
}
const reflowRows = new Set<ReflowEntry>();
let reflowIO: IntersectionObserver | null = null;
let resizeTimer = 0;

function registerForReflow(row: El): void {
  // drop rows from torn-down views (route changes)
  for (const e of reflowRows) {
    if (!e.row.isConnected) reflowRows.delete(e);
  }
  const entry: ReflowEntry = { row, done: false };
  reflowRows.add(entry);
  ensureReflowObserver().observe(row);
}

function ensureReflowObserver(): IntersectionObserver {
  if (reflowIO) return reflowIO;
  reflowIO = new IntersectionObserver(
    (ents) => {
      for (const e of ents) {
        if (!e.isIntersecting) continue;
        for (const entry of reflowRows) {
          if (entry.row === e.target && !entry.done) {
            entry.done = true;
            requestAnimationFrame(() => reflowRow(entry));
          }
        }
      }
    },
    { rootMargin: "100% 0px" }, // ~one screen ahead
  );
  // web fonts change every width — repack when they settle
  document.fonts?.ready.then(() => {
    repackAll();
  }).catch(() => {});
  window.addEventListener("resize", onReflowResize);
  return reflowIO;
}

function onReflowResize(): void {
  window.clearTimeout(resizeTimer);
  resizeTimer = window.setTimeout(() => {
    repackAll();
  }, 150);
}

/** Undo all splits and re-run the wrap-point pass from scratch. */
export function repackAll(): void {
  for (const entry of reflowRows) {
    unsplitRow(entry.row);
    entry.done = false;
    reflowIO?.unobserve(entry.row);
    reflowIO?.observe(entry.row);
  }
}

/** Restore the flat one-paragraph layout (pre-split). */
function unsplitRow(row: El): void {
  const blocks = Array.from(row.querySelectorAll(".vline"));
  if (!blocks.length) return;
  const head = row.querySelector(".unit-head");
  const aiOut = row.querySelector(":scope > .ai-out") as El | null;
  // gather word-aligned scansion spans back in word order
  const scanUs: HTMLElement[] = [];
  for (const b of blocks) {
    b.querySelectorAll<HTMLElement>(".scansion .scan-u")
      .forEach((s) => scanUs.push(s));
  }
  const greek = el("div", "greek-line");
  greek.setAttribute("lang", "grc");
  const parseRow = el("div", "parse-row");
  for (const b of blocks) {
    const gl = b.querySelector(".greek-line");
    const pr = b.querySelector(".parse-row");
    while (gl?.firstChild) greek.appendChild(gl.firstChild);
    while (pr?.firstChild) parseRow.appendChild(pr.firstChild);
    b.remove();
  }
  row.replaceChildren();
  if (head) row.appendChild(head);
  row.appendChild(greek);
  if (scanUs.length) {
    const scan = el("div", "scansion");
    for (const s of scanUs) scan.appendChild(s);
    row.appendChild(scan);
  }
  row.appendChild(parseRow);
  if (aiOut) row.appendChild(aiOut);
}

/** Split one rendered row into per-visual-line blocks using the
 *  browser's own wrap points (offsetTop of the word spans). */
function reflowRow(entry: ReflowEntry): void {
  const { row } = entry;
  const greek = row.querySelector(".greek-line") as El | null;
  const parseRow = row.querySelector(".parse-row") as El | null;
  if (!greek || !parseRow || row.querySelector(".vline")) return;
  const spans = Array.from(greek.querySelectorAll<HTMLElement>(".w"));
  if (spans.length < 2) return;

  // group word indices by visual line via offsetTop
  const groups: number[][] = [[]];
  let top = spans[0].offsetTop;
  spans.forEach((s, i) => {
    if (s.offsetTop !== top) {
      groups.push([]);
      top = s.offsetTop;
    }
    groups[groups.length - 1].push(i);
  });
  if (groups.length < 2) return; // single visual line

  // bucket every child node under its word: a .w span opens its own
  // bucket; spaces/ref-labels attach to the current (preceding) word
  const buckets: Node[][] = spans.map(() => []);
  let wi = 0;
  for (const n of Array.from(greek.childNodes)) {
    const isW = n.nodeType === 1 &&
      (n as Element).classList.contains("w");
    if (!isW && wi === 0) buckets[0].push(n); // ref label / leading junk
    else if (isW) buckets[Math.min(wi, spans.length - 1)].push(n);
    else buckets[Math.max(0, wi - 1)].push(n); // trailing space
    if (isW) wi += 1;
  }

  const head = row.querySelector(".unit-head");
  // Preserve AI output if present (should stay outside vlines, at row end)
  const aiOut = row.querySelector(":scope > .ai-out") as El | null;
  // word-aligned scansion: distribute spans into their own visual-line block
  const scanRow = row.querySelector(":scope > .scansion") as El | null;
  const scanUs = scanRow
    ? Array.from(scanRow.querySelectorAll<HTMLElement>(".scan-u"))
    : [];
  const frag = document.createDocumentFragment();
  // measure container width explicitly to pack correctly (prose paragraphs)
  void row.clientWidth;
  void greek.clientWidth;
  for (const g of groups) {
    const block = el("div", "vline");
    const gl = el("div", "greek-line");
    gl.setAttribute("lang", "grc");
    const pr = el("div", "parse-row");
    let bScan: El | null = scanUs.length ? el("div", "scansion") : null;
    if (bScan && scanRow) bScan.dataset.pattern = scanRow.dataset.pattern ?? "";
    // pack every word index in this visual line
    for (const idx of g) {
      for (const n of buckets[idx] ?? []) gl.appendChild(n);
      const su = scanUs[idx];
      if (su && bScan) bScan.appendChild(su); // scansion follows its word's line
    }
    // every visual Greek line gets exactly its parse row beneath
    for (let k = 0; k < g.length; k++) {
      const col = parseRow.firstElementChild;
      if (!col) break;
      pr.appendChild(col);
    }
    block.appendChild(gl);
    if (bScan && bScan.childElementCount) block.appendChild(bScan);
    block.appendChild(pr);
    frag.appendChild(block);
  }
  row.replaceChildren();
  if (head) row.appendChild(head);
  row.appendChild(frag);
  if (aiOut) row.appendChild(aiOut);
}

/** Back-compat alias used by the paste page. */
export const renderLines = renderUnits;

/* ---------------- controls ---------------- */

export interface Controls {
  root: El;
}

/** This bar's TTS status subscription (re-bound per renderControls call). */
let ttsUiUnsub: (() => void) | null = null;

/* ---------------- bilingual (Chinese) reader header ---------------- */

/**
 * Reader-header upgrade: swap the flat crumb ("Author, Title") for a
 * compact two-line stack — Chinese title primary (author group's nameZh
 * prepended when the catalog ships one), original "Author, Title" small +
 * muted underneath — when this route's work carries titleZh. No-op when
 * absent, the route changed mid-load, or the bar was torn down.
 * Route shapes here are `#/<workId>?ref=…` and `#/pali/<workId>` (work ids
 * globally unique); legacy tlg pairs redirect before a reader exists.
 */
function upgradeCrumbs(crumbs: El, catalog: Catalog): void {
  const hashAtCall = location.hash;
  const route = hashAtCall.replace(/^#\/?/, "").split("?")[0];
  if (!route || route === "about" || route === "pali") return;
  const wid = route.startsWith("pali/") ? route.slice("pali/".length) : route;
  if (!wid || wid.includes("/")) return; // not a plain work route
  let id = wid;
  try { id = decodeURIComponent(wid); } catch { /* raw slug */ }
  for (const author of catalog.authors) {
    const work = author.works.find((w) => w.id === id);
    if (!work) continue;
    const zh = zhTitleOf(work);
    if (!zh || !crumbs.isConnected || location.hash !== hashAtCall) return;
    crumbs.classList.add("bilingual");
    const nameZh = zhNameOf(author);
    const zhLine = el("span", "crumb-zh", nameZh ? `${nameZh} · ${zh}` : zh);
    zhLine.lang = "zh";
    crumbs.replaceChildren(zhLine, el("span", "crumb-orig",
      `${author.name}, ${work.title}`));
    return;
  }
}

export function renderControls(
  crumbsText: string,
  onBack: () => void,
  opts?: { noTranslation?: boolean },
): Controls {
  const bar = el("nav", "controls");
  const back = el("button", undefined, "← Home");
  back.addEventListener("click", onBack);
  bar.appendChild(back);
  const crumbs = el("span", "crumbs", crumbsText);
  bar.appendChild(crumbs);
  // Truly untranslated works (no EN and no zh): subtle 「无译文」 badge
  // beside the crumbs so readers know up front that no translation ships.
  // Zh-only works don't get this — their 汉译 layer is the translation.
  // Lives OUTSIDE .crumbs so the bilingual upgrade can't drop it.
  if (opts?.noTranslation) {
    const badge = el("span", "no-trans-badge", "无译文");
    badge.lang = "zh";
    badge.title = "No translation available for this work yet";
    bar.appendChild(badge);
  }

  const spacer = el("span", "spacer");
  bar.appendChild(spacer);

  let showGloss = true;
  const tog = el("button", undefined, "Hide glosses");
  tog.setAttribute("aria-pressed", "true");
  tog.addEventListener("click", () => {
    showGloss = !showGloss;
    document.body.classList.toggle("hide-gloss", !showGloss);
    tog.textContent = showGloss ? "Hide glosses" : "Show glosses";
    tog.setAttribute("aria-pressed", String(showGloss));
  });
  bar.appendChild(tog);

  // expand/collapse all candidate lists (also key: E)
  const expAll = el("button", undefined, "Expand all");
  expAll.title = "Show every candidate parse (key: E)";
  expAll.addEventListener("click", expandAll);
  const colAll = el("button", undefined, "Collapse all");
  colAll.title = "Back to best-parse cards (key: E)";
  colAll.addEventListener("click", collapseAll);
  bar.appendChild(expAll);
  bar.appendChild(colAll);

  // vocabulary book: mode toggle group, stats chip, bulk page marking
  bar.appendChild(toolbarControls());
  attachChip(bar);

  // starred lines panel (list lives in bookmarks.ts)
  const starTitles = new Map<string, string>();
  loadCatalog().then((catalog) => {
    for (const author of catalog.authors) {
      for (const w of author.works) starTitles.set(w.id, w.title);
    }
    // bilingual header upgrade (no-op when the work has no titleZh)
    upgradeCrumbs(bar.querySelector<HTMLElement>(".crumbs")!, catalog);
  }).catch(() => {});
  const starsBtn = el("button", undefined, "★ Saved") as HTMLButtonElement;
  starsBtn.type = "button";
  starsBtn.title = "Bookmarked lines";
  starsBtn.addEventListener("click", () => openStarPanel(starTitles));
  bar.appendChild(starsBtn);


  bar.appendChild(lexiconButton());

  const greekSize = () =>
    parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue("--greek-size"),
    ) || 1.35;
  const setGreekSize = (rem: number) =>
    document.documentElement.style.setProperty(
      "--greek-size",
      `${Math.min(2.4, Math.max(0.9, rem)).toFixed(2)}rem`,
    );
  const minus = el("button", undefined, "A−");
  minus.addEventListener("click", () => {
    setGreekSize(greekSize() - 0.15);
    onReflowResize(); // glyph widths changed → re-pack visual lines
  });
  const plus = el("button", undefined, "A+");
  plus.addEventListener("click", () => {
    setGreekSize(greekSize() + 0.15);
    onReflowResize();
  });
  bar.appendChild(minus);
  bar.appendChild(plus);

  // display script: IAST <-> Devanagari (label names the other script)
  bar.appendChild(scriptPrefControls());

  bar.appendChild(themeControl());

  return { root: bar };
}

/** Best prior-ranked analysis of a token (panel actions, vocab marking). */
function topParse(
  parses: Parse[],
  ctx: RenderCtx,
  word?: string,
): Parse | undefined {
  return rankedParses(parses, groupOpts(ctx, word))[0];
}

/* ---------------- side panel ---------------- */

let panel: El | null = null;

function ensurePanel(): El {
  if (panel) return panel;
  panel = el("aside", "side-panel hidden");
  panel.setAttribute("aria-label", "Word details");
  const close = el("button", "close-btn", "×");
  close.setAttribute("aria-label", "Close details");
  close.addEventListener("click", hidePanel);
  panel.appendChild(close);
  const body = el("div", "panel-body");
  panel.appendChild(body);
  document.body.appendChild(panel);
  return panel;
}

export function hidePanel(): void {
  if (panel) panel.classList.add("hidden");
  document.body.classList.remove("panel-open");
  document.querySelectorAll(".w.active").forEach((n) => n.classList.remove("active"));
}

function openPanel(span: El, word: string, ctx: RenderCtx): void {
  const p = ensurePanel();
  const body = p.querySelector(".panel-body") as El;
  body.replaceChildren();

  document.querySelectorAll(".w.active").forEach((n) => n.classList.remove("active"));
  span.classList.add("active");

  // dual-script heading (IAST primary + Devanagari beneath); the raw form
  // rides on data-word so async fills can detect staleness
  const h2 = el("h2");
  h2.dataset.word = word;
  h2.appendChild(lemmaDualEl(word));
  body.appendChild(h2);
  const parses = ctx.morph.get(stripAccents(word)) ?? [];

  // vocabulary book: mark/unmark this form (stores stripped key + best lemma)
  const stripped = stripAccents(word);
  const vrow = el("p", "panel-vocab");
  const vbtn = el("button", "panel-vocab-btn") as HTMLButtonElement;
  vbtn.type = "button";
  const paintV = (): void => {
    const knownNow = isKnown(stripped);
    vbtn.textContent = knownNow ? "Unmark" : "Mark known ✓";
    vbtn.classList.toggle("marked", knownNow);
    if (knownNow) span.classList.add("vk");
    else span.classList.remove("vk");
    vbtn.title = knownNow
      ? `Remove ${stripped} from your vocabulary`
      : `Remember ${stripped} (dim it while reading)`;
  };
  vbtn.addEventListener("click", () => {
    if (isKnown(stripped)) unmarkKnown(stripped);
    else {
      const bestLemma = parses.length
        ? topParse(parses, ctx, word)?.l
        : undefined;
      markKnown(stripped, bestLemma);
    }
    paintV();
    applyClasses();
  });
  paintV();
  vrow.appendChild(vbtn);
  body.appendChild(vrow);

  if (parses.length === 0) {
    body.appendChild(el("p", "word-form", "No analyses available for this form."));
  } else {
    // GROUPED readings (kim/ka fix): one entry per (lemma, POS-class) group,
    // ranked with priors — never a raw per-occurrence paradigm wall. The
    // full Monier-Williams text for each distinct lemma stays below.
    const groups = buildRankedGroups(parses, groupOpts(ctx, word));
    body.appendChild(
      el("p", "word-form",
        `${groups.length} reading${groups.length > 1 ? "s" : ""}`),
    );
    for (const g of groups) {
      const entry = el("div", "entry");
      entry.appendChild(groupHeadEl(g));
      if (g.members.length === 1) {
        // unmapped f-extras + x-field stay visible in panel detail (R2/R5)
        const ex = extrasLine(g.members[0]!);
        if (ex) entry.appendChild(ex);
      } else {
        entry.appendChild(el("div", "feats feat-extras",
          `${g.members.length} attested combos`));
      }
      attachMwGloss(entry, g.lemma ?? "");
      body.appendChild(entry);
    }
  }

  // samāsa members: one mini-row per compound member (form, tags, MW gloss)
  const comp = compoundFor(word, ctx);
  if (comp) body.appendChild(comp);

  // full dictionary entries for each distinct lemma of this form
  const dictEntries: Gloss[] = [];
  for (const parse of parses) {
    const gl = ctx.gloss.get(stripAccents(parse.l));
    if (gl && !dictEntries.some((d) => d.u === gl.u)) dictEntries.push(gl);
  }
  if (dictEntries.length) {
    body.appendChild(el("h3", undefined, "Monier-Williams"));
    for (const d of dictEntries) {
      const entry = el("div", "entry");
      entry.appendChild(lemmaDualEl(d.u));
      entry.appendChild(el("div", "dict-gloss", d.g));
      body.appendChild(entry);
    }
  }

  // deep-link into the lexicon drawer, prefilled with the best-ranked
  // reading's lemma (prior-aware: interrogative kim, not the noun homograph)
  if (parses.length) {
    const best = topParse(parses, ctx, word);
    if (best?.l) {
      const jump = el("button", undefined, "Open in Lexicon ↗") as HTMLButtonElement;
      jump.type = "button";
      jump.addEventListener("click", () => openLexicon(best.l));
      body.appendChild(jump);
    }
  }

  // Monier-Williams (SLP1-keyed gloss shards): keys from the Devanagari
  // surface via slp1KeyFor (lowercase-normalized AFTER conversion — shards
  // are lowercase-keyed), with sibilant-mirrored variants (re-lowercased at
  // this single shard-lookup point), plus a longest-prefix (>=4) fallback.
  // Section hidden when nothing hits.
  if (word) {
    const wantWord = word;
    void (async () => {
      const baseKeys = [slp1KeyFor(word)]
        .filter((k) => k && k.length >= 2);
      const tried = new Set<string>();
      let hit: { u: string; g: string } | null = null;
      for (const base of baseKeys) {
        for (const key of [base, ...slp1KeyVariants(base)].map((k) =>
          k.toLowerCase(),
        )) {
          if (tried.has(key)) continue;
          tried.add(key);
          for (const cut = 0; ;) {
            const probe = key.slice(0, Math.max(4, key.length - cut));
            const letter = probe[0];
            if (!letter) break;
            const shard = await loadGlossShard(letter);
            const bucket = shard ?? {};
            const exact = bucket[probe];
            if (exact) {
              hit = { u: exact.u ?? probe, g: exact.g ?? "" };
              break;
            }
            // longest prefix >= 4 within this shard
            const pref = Object.keys(bucket)
              .filter((kk) => kk.startsWith(probe.slice(0, -0) ) || probe.startsWith(kk))
              .sort((a, b) => b.length - a.length)
              .find((kk) => probe.startsWith(kk) && kk.length >= 4);
            if (pref) {
              hit = { u: bucket[pref].u ?? pref, g: bucket[pref].g ?? "" };
              break;
            }
            break; // only one probe length per variant; prefixes handled above
          }
          if (hit) break;
        }
        if (hit) break;
      }
      if (!hit || !panel || panel.classList.contains("hidden")) return;
      if ((body.querySelector("h2")?.dataset.word ?? "") !== wantWord) return;
      body.appendChild(el("h3", "mw-head", "Monier-Williams"));
      const entryDiv = el("div", "entry mw-entry");
      entryDiv.appendChild(lemmaDualEl(hit.u));
      // skip OCR/parsing artifacts that reduced the sense to punctuation
      if (/[^\u0900-\u097fA-Za-z]/.test(hit.g.replace(/\s/g, "")) &&
          hit.g.replace(/[^A-Za-z\u0900-\u097f]/g, "").length >= 3) {
        entryDiv.appendChild(el("div", "dict-gloss", hit.g));
      }
      body.appendChild(entryDiv);
    })();
  }

  p.classList.remove("hidden");
  document.body.classList.add("panel-open"); // squeeze #app so controls stay clickable
}
