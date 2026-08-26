// Parse-analysis GROUPING + display-layer ranking priors + gloss clipping.
//
// WHY (kim/ka disaster): shard arrays accumulate one analysis ROW PER CORPUS
// OCCURRENCE, so a high-frequency form like किम् ships every attested
// gender×number×case combo as its own entry — each parroting the FULL
// Monier-Williams essay gloss — and homograph junk drawers (श "N. of
// Prajāpati" under ka) outrank the actual particle. Data is owned by the
// pipeline agent; this module fixes the DISPLAY layer:
//   1. group analyses by (lemma, POS-class) — one row per group, collapsed
//      view capped at MAX_VISIBLE_GROUPS rows;
//   2. indeclinable/particle groups carry no inflectional slots, so they can
//      only ever render ONE row (`kim indecl. — interrogative particle…`) —
//      never a case grid; a token whose EVERY analysis is uninflected
//      collapses to a single dominant-lemma row;
//   3. ranking priors: indeclinable readings first, exact surface-form lemma
//      matches next; nominal readings whose MW gloss OPENS with a proper-name
//      sense ("N. of Prajāpati") are demoted below function words;
//   4. MW glosses clip at the first sentence boundary ≤ GLOSS_MAX_CHARS;
//      full text stays available in expander surfaces (panel MW section,
//      lexicon drawer).
// Pure data module (no DOM): callers build elements via feats.ts helpers.
import { stripAccents, type Parse } from "./api";
import { featSlotsOf } from "./feats";

/** Visible collapsed group-rows per token (spec hard cap). */
export const MAX_VISIBLE_GROUPS = 3;

/** Visible gloss budget before any expander (spec M5). */
export const GLOSS_MAX_CHARS = 120;

/* ---------------- lemma / POS normalisation ---------------- */

/**
 * Display/identity lemma: drop DCS homonym digits ("दृश्1" -> "दृश्") and
 * punctuation edges from broken shard lemmas ("(च" -> "च").
 */
export function normLemma(lemma: string): string {
  return stripAccents(lemma ?? "")
    .replace(/^[(\[]+/, "")
    .replace(/[)\]]+$/, "")
    .replace(/^(.*\D)\d+$/, "$1");
}

/** Coarse POS class of one analysis ("indecl" | noun | verb | part | other).
 *  DCS "part" is ambiguous in the shards: true participles carry tense/
 *  voice slots, while inflected particles/pronouns (क "पुं;1;एक") carry
 *  nominal slots only — the latter classify as nominal so they GROUP with
 *  their noun homographs instead of masquerading as "ptcp.". */
export type PosClass = "indecl" | "noun" | "verb" | "part" | "other";

export function posClassOf(p: Parse): PosClass {
  switch ((p.p ?? "").trim()) {
    case "noun": return "noun";
    case "verb": return "verb";
    case "part": {
      const s = featSlotsOf(p.f ?? "");
      return s.tense.size > 0 || s.voice.size > 0 ? "part" : "noun";
    }
    case "indecl": return "indecl";
    default: return "other";
  }
}

function hasInflectionSlots(p: Parse): boolean {
  const s = featSlotsOf(p.f ?? "");
  return s.person.size > 0 || s.gender.size > 0 || s.number.size > 0 ||
    s.kcase.size > 0 || s.tense.size > 0 || s.voice.size > 0;
}

/** True when NO analysis of this token carries an inflectional slot —
 *  the whole token renders as ONE indeclinable row (M4). */
export function allUninflected(parses: Parse[]): boolean {
  if (!parses.length) return false;
  return parses.every((p) => !hasInflectionSlots(p));
}

/* ---------------- grouping ---------------- */

export interface ParseGroup {
  /** Identity key: normalised lemma + POS class. */
  key: string;
  /** Representative lemma as shipped (first member's). */
  lemma: string;
  cls: PosClass;
  members: Parse[];
}

/**
 * Group analyses by (lemma, POS-class). Order-preserving on first sight so
 * downstream stable sorts stay deterministic.
 */
export function groupParses(parses: Parse[]): ParseGroup[] {
  const map = new Map<string, ParseGroup>();
  const out: ParseGroup[] = [];
  for (const p of parses) {
    const lemmaKey = normLemma(p.l ?? "");
    const cls = posClassOf(p);
    const k = `${lemmaKey}\u0000${cls}`;
    let g = map.get(k);
    if (!g) {
      g = { key: k, lemma: p.l ?? "", cls, members: [] };
      map.set(k, g);
      out.push(g);
    }
    g.members.push(p);
  }
  return out;
}

/**
 * Collapse an ALL-UNINFLECTED token (च/तु/किम्-style particle drawers whose
 * shard array accumulated several near-duplicate lemmas) into ONE synthetic
 * group keyed by the dominant lemma — spec rule 2: exactly one row, never a
 * grid of letter-of-the-alphabet entries.
 */
export function collapseIndeclToken(parses: Parse[]): ParseGroup[] {
  const counts = new Map<string, number>();
  for (const p of parses) {
    const k = normLemma(p.l ?? "");
    counts.set(k, (counts.get(k) ?? 0) + 1);
  }
  let best = parses[0]!;
  let bestN = -1;
  for (const p of parses) {
    const n = counts.get(normLemma(p.l ?? "")) ?? 0;
    if (n > bestN) {
      best = p;
      bestN = n;
    }
  }
  return [{
    key: `${normLemma(best.l ?? "")}\u0000merged-indecl`,
    lemma: best.l ?? "",
    cls: "indecl",
    members: parses.slice(),
  }];
}

/* ---------------- compact-set feature summary ---------------- */

/**
 * Compact SET notation for a group's attested combos: singleton slots print
 * their value, small variation joins with "/" ("m./n.", "sg./du./pl."),
 * wide case variation prints 「various cases」 instead of enumerating.
 * Ordered like parseDcsFeats: tense · voice/person · gender · number · case.
 * Empty for indeclinable groups (they have nothing to enumerate — by design).
 */
export function groupSummaryAbbrs(g: ParseGroup): string[] {
  const agg = {
    tense: new Set<string>(), person: new Set<string>(),
    voice: new Set<string>(), gender: new Set<string>(),
    number: new Set<string>(), kcase: new Set<string>(),
  };
  for (const m of g.members) {
    const s = featSlotsOf(m.f ?? "");
    for (const dim of Object.keys(agg) as Array<keyof typeof agg>) {
      for (const v of s[dim]) agg[dim].add(v);
    }
  }
  const joinOrVarious = (
    set: Set<string>, various: string, maxJoin = 3,
  ): string => {
    if (set.size === 0) return "";
    if (set.size === 1) return [...set][0]!;
    if (set.size <= maxJoin) return [...set].join("/");
    return various;
  };
  const out: string[] = [];
  const tense = joinOrVarious(agg.tense, "various tenses");
  const voice = joinOrVarious(agg.voice, "various voices");
  const person = joinOrVarious(agg.person, "various persons");
  const gender = joinOrVarious(agg.gender, "m./f./n.");
  const number = joinOrVarious(agg.number, "sg./du./pl.");
  const kcase = joinOrVarious(agg.kcase, "various cases");
  if (tense) out.push(tense);
  if (agg.gender.size > 0) {
    if (voice) out.push(voice);
    if (gender) out.push(gender);
    if (number) out.push(number);
  } else {
    if (person) out.push(person);
    if (number) out.push(number);
    if (voice) out.push(voice);
  }
  if (kcase) out.push(kcase);
  // de-dupe consecutive repeats (e.g. summary collapsing to one value twice)
  return out.filter((v, i) => i === 0 || v !== out[i - 1]);
}

/* ---------------- ranking priors (display layer) ---------------- */

/** Boost for indeclinable/particle readings (kills paradigm-wall dominance). */
export const INDECL_PRIOR = 35;
/** Bonus when the analysis lemma IS the queried/surface form (contextual
 *  exact match — kills hyphen-homographs like ādin-deva under deva). */
export const EXACT_FORM_PRIOR = 12;
/** Demotion for nominal readings whose MW gloss OPENS with a proper-name
 *  sense — kills ka -> "N. of Prajāpati" dominance over the particle. */
export const PROPER_NAME_PENALTY = 15;

/** True when the MW gloss text leads with a proper-name/mythological sense. */
export function isProperNameGloss(gloss: string | undefined): boolean {
  if (!gloss) return false;
  return /^\s*(?:as,\s*)?(?:[mfn]\.\s*)?(?:N|Name)\.\s*of\b/i.test(
    gloss.replace(/\s+/g, " ").slice(0, 48),
  );
}

export interface GroupRankOpts {
  /** Base corpus-frequency score (render.ts scoreParse); may be absent. */
  base?: (p: Parse) => number;
  /** MW gloss lookup by lemma (sync — callers preload into ctx.gloss). */
  glossOf?: (lemma: string) => string | undefined;
  /** Surface/query form: groups whose lemma matches it rank up. */
  form?: string;
}

/** Additive display prior of one analysis. The proper-name demotion never
 *  applies to an exact surface-form match: the reader looked THIS word up,
 *  so its own reading must not be penalised for its lemma's dictionary
 *  entry leading with a mythological sense (ka fix). */
export function parsePrior(p: Parse, opts: GroupRankOpts): number {
  let s = 0;
  const cls = posClassOf(p);
  if (cls === "indecl") s += INDECL_PRIOR;
  const normForm = opts.form ? normLemma(opts.form) : "";
  const exactMatch = !!normForm && normLemma(p.l ?? "") === normForm;
  if (!exactMatch && cls !== "indecl" &&
    isProperNameGloss(opts.glossOf?.(p.l ?? ""))) {
    s -= PROPER_NAME_PENALTY;
  }
  if (exactMatch) s += EXACT_FORM_PRIOR;
  return s;
}

/**
 * Ranked groups, best first. Score = base corpus score (max over members)
 * + prior (max over members), stable tie-break keeps shard order.
 */
export function rankGroups(
  groups: ParseGroup[],
  opts: GroupRankOpts = {},
): ParseGroup[] {
  const scored = groups.map((g, i) => {
    let s = -Infinity;
    for (const m of g.members) {
      const v = (opts.base?.(m) ?? 0) + parsePrior(m, opts);
      if (v > s) s = v;
    }
    return { g, i, s };
  });
  return scored.sort((a, b) => b.s - a.s || a.i - b.i).map((x) => x.g);
}

/**
 * Full pipeline for one token: deduped analyses -> groups -> ranked.
 * All-uninflected tokens collapse to a single dominant-lemma row (rule 2).
 */
export function buildRankedGroups(
  parses: Parse[],
  opts: GroupRankOpts = {},
): ParseGroup[] {
  if (!parses.length) return [];
  const groups = allUninflected(parses)
    ? collapseIndeclToken(parses)
    : groupParses(parses);
  return rankGroups(groups, opts);
}

/** Flat analyses in ranked-group order (compound scan order etc.). */
export function rankedParses(parses: Parse[], opts: GroupRankOpts): Parse[] {
  return buildRankedGroups(parses, opts).flatMap((g) => g.members);
}

/* ---------------- MW gloss clipping (spec 4) ---------------- */

/**
 * Clip a raw Monier-Williams gloss at its FIRST sentence boundary within
 * `max` chars (periods/semicolons/question marks followed by space or end),
 * skipping degenerate boundaries inside the first few chars ("m. N. of…").
 * Falls back to a word-boundary ellipsis slice. Result length ≤ max.
 */
export function clipGloss(txt: string, max = GLOSS_MAX_CHARS): string {
  const t = (txt ?? "").replace(/\s+/g, " ").trim();
  if (t.length <= max) return t;
  const minCut = Math.min(12, max - 1);
  for (let i = minCut; i < max; i++) {
    const ch = t[i];
    if (ch === "." || ch === ";" || ch === "?" || ch === ":") {
      const nxt = t[i + 1];
      if (nxt === undefined || nxt === " ") return t.slice(0, i + 1);
    }
  }
  const slice = t.slice(0, max - 1);
  const sp = slice.lastIndexOf(" ");
  return (sp > max / 2 ? slice.slice(0, sp) : slice) + "…";
}

/** Short gloss used for repeat-suppression identity across group rows. */
export function glossIdentity(txt: string): string {
  return clipGloss(txt).toLowerCase();
}
