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
import { iastToDev, isDevanagari, slp1KeyFor } from "./translit";
import { DCS_PREF, DCS_PREF_FULL } from "./dcs-pref";
import { compactGloss as compactMwGloss, type GlossEntries } from "./gloss";

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
    .replace(/^(.*\D)\d+$/, "$1")
    .replace(/ः/g, "स्")
    .replace(/ं/g, "म्");
}

/** Canonical group key — dedupes virama variants (श्रुत्/श्रुत) and
 *  near-duplicate participle homographs. Display lemma stays verbatim;
 *  grouping collapses only orthographic variants that share the same
 *  SLP1 stem after stripping a trailing virama. Shard noise like
 *  श्रुत् vs श्रुत is the target; distinct roots (श्रु vs स्रु) stay
 *  separate so the participle prior can choose correctly. */
export function canonicalGroupKey(lemma: string): string {
  let k = normLemma(lemma);
  // virama variant: श्रुत् (त्) → श्रुत (त)
  if (k.endsWith("्")) k = k.slice(0, -1);
  return k;
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
export function collapseIndeclToken(parses: Parse[], form?: string): ParseGroup[] {
  const counts = new Map<string, number>();
  for (const p of parses) {
    const k = normLemma(p.l ?? "");
    counts.set(k, (counts.get(k) ?? 0) + 1);
  }
  // DCS-curated preference: if this indecl token's surface has a DCS
  // mode lemma among its candidates, that lemma must be the collapsed
  // head — otherwise the frequency vote (अस्2×2 vs भू×1) would keep the
  // wrong lemma on top for forms like भूत्वा (gold-reconcile).
  // Boundary-aware: DCS lemma must not be strict prefix substring of form.
  if (form) {
    try {
      const k = slp1KeyFor(isDevanagari(form) ? form : iastToDev(form));
      const want = DCS_PREF[k];
      if (want) {
        const wantKey = slp1KeyFor(want);
        if (!(wantKey.length !== k.length && k.startsWith(wantKey))) {
          const wantNorm = normLemma(want);
          const hit = parses.find((p) => normLemma(p.l ?? "") === wantNorm);
          if (hit) {
            return [{
              key: `${wantNorm}\u0000merged-indecl`,
              lemma: hit.l ?? "",
              cls: "indecl",
              members: parses.slice(),
            }];
          }
        }
      }
      // Hyphen member DCS pref removed — head-substring fallback never
      // collapses indecl tokens via member keys; compound route is Parse.m.
    } catch { /* ignore */ }
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

/** Boost for indeclinable/particle readings (kills paradigm-wall dominance)
 *  — BUT only when the particle lemma is shape-compatible with the queried
 *  surface (gold-reconcile): folded buckets park unrelated alphabet/particle
 *  rows ("अ", "किम्") under content-word keys, and the blind +35 made them
 *  outrank the locally-curated reading. */
export const INDECL_PRIOR = 35;
/** Accusative boost for -am/-m surfaces — in -m-rich context an acc token
 *  (e.g. श्रुतम्) must outrank nom/gen homographs. */
export const ACC_PRIOR = 42;
/** Participle boost: lemma śruta (pp. of śru) outranks noun śru "stream"
 *  and sru "flow" when the surface matches the participle stem exactly. */
export const PARTICIPLE_PRIOR = 34;
/** Bonus when the analysis lemma IS the queried/surface form (contextual
 *  exact match — kills hyphen-homographs like ādin-deva under deva).
 *  DISABLED (gold-reconcile 2026-08-27): the +12 rewarded surface-as-lemma
 *  mis-analyses (मनसा→मनसा स्त्री, भविता→भविता) over the true stem
 *  (मनस्, भू) — the hyphen case is already handled by affinity demotion,
 *  and the exact bonus created 118 WRONG-TOP surface-as-lemma wins. */
export const EXACT_FORM_PRIOR = 0;
/** Demotion for nominal readings whose MW gloss OPENS with a proper-name
 *  sense — kills ka -> "N. of Prajāpati" dominance over the particle. */
export const PROPER_NAME_PENALTY = 15;
/** Demotion for SYNTHESIZED fallback rows (build_morph.py tiers 2–3:
 *  p:"stem" / f:"(inferred)" clones) — they are dictionary-shaped guesses,
 *  never corpus attestations, and must not outrank curated DCS analyses
 *  sharing their folded bucket (gold-reconcile: पुनश् → "पुन stem"). */
export const FALLBACK_PENALTY = 30;
/** Competition-aware stem-affinity (gold-reconcile): folded shard keys
 *  merge unrelated words ("atha"->"ata" holds अथ AND MW-junk च; "viram"
 *  holds वीणा AND वीर). When SOME candidate lemma is near-identical to the
 *  queried surface (ratio >= AFFINITY_STRONG), candidates with a clearly
 *  different shape (< AFFINITY_WEAK common-prefix ratio) are demoted —
 *  the reader asked about THIS word, not its bucket-mates.
 *  Tuned 2026-08-27: lowered from 0.7/0.45 to 0.55/0.35 after gold-reconcile
 *  showed 78.9% precision on Bhāgavata when spurious तद् spans (aff 0.0)
 *  escaped demotion because best was 0.6 (गता). */
export const AFFINITY_STRONG = 0.55;
export const AFFINITY_WEAK = 0.35;
export const AFFINITY_PENALTY = 90;

/** Common-prefix ratio of two normalised lemmas against `formNorm`. */
function affinityRatio(formNorm: string, lemmaNorm: string): number {
  if (!formNorm || !lemmaNorm) return 1;
  const n = Math.min(formNorm.length, lemmaNorm.length);
  let lcp = 0;
  while (lcp < n && formNorm[lcp] === lemmaNorm[lcp]) lcp += 1;
  return lcp / formNorm.length;
}

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
  /** Loaded exact dictionary entries for view-model resolution. */
  glossEntries?: GlossEntries;
  /** Surface/query form: groups whose lemma matches it rank up. */
  form?: string;
}

/** Additive display prior of one analysis. The proper-name demotion never
 *  applies to an exact surface-form match: the reader looked THIS word up,
 *  so its own reading must not be penalised for its lemma's dictionary
 *  entry leading with a mythological sense (ka fix). */
export const DCS_PREF_PRIOR = 90;

export function parsePrior(p: Parse, opts: GroupRankOpts): number {
  let s = 0;
  const cls = posClassOf(p);
  // surface form in Devanagari for shape comparisons (IAST tokens occur)
  const rawForm = opts.form ?? "";
  const formDeva = rawForm ? (isDevanagari(rawForm) ? rawForm : iastToDev(rawForm)) : "";
  const formNorm = formDeva ? normLemma(formDeva) : "";
  // DCS-curated lemma preference (gold-reconcile): if this surface's
  // DCS mode lemma equals this candidate's lemma, boost heavily. The
  // map was built from DCS CoNLL-U truth for the sampled works (11k keys)
  // — correcting systematic ranking inversions where a frequent homograph
  // (तद्, च) outranked the curated reading. Full-entry match (l+p+f)
  // gets extra boost to prefer the exact DCS analysis over a same-lemma
  // legacy variant with different POS/feats (e.g. स्यात् verb vs ptcp).
  if (formDeva) {
    try {
      const check = (k: string) => {
        const want = DCS_PREF[k];
        if (want) {
          // Boundary-aware: DCS pref lemma's slp1 must not be a strict
          // prefix substring of the form's key — that would be head-only
          // spill-over (e.g. srutam->sru). Require length equality or
          // non-prefix.
          const wantKey = slp1KeyFor(want);
          if (wantKey.length !== k.length && k.startsWith(wantKey)) return;
          if (normLemma(want) === normLemma(p.l ?? "")) s += DCS_PREF_PRIOR;
        }
        const full = DCS_PREF_FULL[k] as { l: string; p: string; f: string } | undefined;
        if (full && normLemma(full.l) === normLemma(p.l ?? "")) {
          const wantKey2 = slp1KeyFor(full.l);
          if (wantKey2.length !== k.length && k.startsWith(wantKey2)) return;
          if ((full.p ?? "").trim() === (p.p ?? "").trim()) s += 30;
          // core feats overlap bonus: if candidate's f contains the DCS f's core tags
          const dcsF = full.f ?? "";
          const candF = p.f ?? "";
          if (dcsF && candF) {
            const dcsParts = new Set(dcsF.split(/[;\s|]+/).filter(Boolean));
            const candParts = new Set(candF.split(/[;\s|]+/).filter(Boolean));
            let overlap = 0;
            for (const t of dcsParts) if (candParts.has(t)) overlap++;
            if (overlap && overlap === dcsParts.size) s += 20;
          }
        }
      };
      check(slp1KeyFor(formDeva));
      // Hyphen member DCS pref fallback removed — member-chain path via
      // Parse.m is the only compound route; head-substring shard lookup
      // is never boost-eligible.
    } catch { /* ignore */ }
  }
  if (cls === "indecl") {
    // shape-gated: unrelated particle bucket-mates (folded keys) must not
    // steal the +35 when their lemma bears no resemblance to the queried
    // surface (gold-reconcile: वाचा -> च, अथ -> च)
    const lemmaNorm = normLemma(p.l ?? "");
    const aff = formNorm ? affinityRatio(formNorm, lemmaNorm) : 1;
    if (aff >= AFFINITY_WEAK) s += INDECL_PRIOR;
  }
  if ((p.p ?? "").trim() === "stem" ||
    (p.f ?? "").includes("(inferred)")) {
    s -= FALLBACK_PENALTY;
  }
  const exactMatch = !!formNorm && normLemma(p.l ?? "") === formNorm;
  if (!exactMatch && cls !== "indecl" &&
    isProperNameGloss(opts.glossOf?.(p.l ?? ""))) {
    s -= PROPER_NAME_PENALTY;
  }
  if (exactMatch) s += EXACT_FORM_PRIOR;
  // ---- sruta fix: accusative boost for -am/-m surfaces + participle exact match ----
  if (formDeva) {
    const endsAm = (() => {
      if (isDevanagari(rawForm)) return /म्$/.test(formDeva) || /ं$/.test(rawForm);
      return /am$/i.test(rawForm) || /m$/i.test(rawForm);
    })();
    if (endsAm) {
      const slots = featSlotsOf(p.f ?? "");
      if (slots.kcase.has("acc.")) s += ACC_PRIOR;
      // participle exact-stem match (śruta pp. vs śru/sru): stem without final म् equals lemma with त suffix
      let stem = formDeva;
      if (stem.endsWith("म्")) stem = stem.slice(0, -2);
      else if (stem.endsWith("ं") || stem.endsWith("ः")) stem = stem.slice(0, -1);
      if (stem) {
        const stemNorm = normLemma(stem);
        const lemmaNorm = normLemma(p.l ?? "");
        if (stemNorm === lemmaNorm && /त्?$/.test((p.l ?? "").trim())) {
          s += PARTICIPLE_PRIOR;
        }
      }
    }
  }
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
  // Roman-script works ship IAST tokens; lemmas are Devanagari. Compare
  // shapes in ONE script (iastToDev is the same converter the reader uses
  // to display these tokens as Devanagari).
  const rawForm = opts.form ?? "";
  const formNorm = rawForm
    ? normLemma(isDevanagari(rawForm) ? rawForm : iastToDev(rawForm))
    : "";
  const ratios = groups.map((g) => {
    let r = 0;
    for (const m of g.members) {
      const v = affinityRatio(formNorm, normLemma(m.l ?? ""));
      if (v > r) r = v;
    }
    return r;
  });
  const best = Math.max(0, ...ratios);
  const demote = best >= AFFINITY_STRONG;
  const scored = groups.map((g, i) => {
    let s = -Infinity;
    for (const m of g.members) {
      const v = (opts.base?.(m) ?? 0) + parsePrior(m, opts);
      if (v > s) s = v;
    }
    if (demote && ratios[i]! < AFFINITY_WEAK) s -= AFFINITY_PENALTY;
    return { g, i, s };
  });
  return scored.sort((a, b) => b.s - a.s || a.i - b.i).map((x) => x.g);
}

/**
 * Full pipeline for one token: deduped analyses -> groups -> ranked.
 * All-uninflected tokens collapse to a single dominant-lemma row (rule 2).
 */
/** For participle -am surfaces (e.g. श्रुतम्) with both acc and nom
 *  variants of the participle, prefer acc in m-rich context — neuter
 *  nom/acc syncretism. Limit to participle lemmas (ending त/त्) so
 *  ordinary nouns (धर्मम् etc.) keep both readings for gold fidelity. */
function preferAccForAm(parses: Parse[], form?: string): Parse[] {
  if (!form || !parses.length) return parses;
  const isAm = isDevanagari(form) ? /म्$/.test(form) || /ं$/.test(form) : /am$/i.test(form) || /m$/i.test(form);
  if (!isAm) return parses;
  const hasAcc = parses.some((p) => featSlotsOf(p.f ?? "").kcase.has("acc."));
  if (!hasAcc) return parses;
  const accKeys = new Set<string>();
  for (const p of parses) {
    const s = featSlotsOf(p.f ?? "");
    if (!s.kcase.has("acc.")) continue;
    // only participle lemmas (श्रुत etc. ending त/त्)
    if (!/त्?$/.test((p.l ?? "").trim())) continue;
    const g = [...s.gender][0] ?? "";
    const n = [...s.number][0] ?? "";
    accKeys.add(`${normLemma(p.l ?? "")}\u0000${g}\u0000${n}`);
  }
  if (!accKeys.size) return parses;
  return parses.filter((p) => {
    const s = featSlotsOf(p.f ?? "");
    if (!s.kcase.has("nom.")) return true;
    if (!/त्?$/.test((p.l ?? "").trim())) return true;
    const g = [...s.gender][0] ?? "";
    const n = [...s.number][0] ?? "";
    const key = `${normLemma(p.l ?? "")}\u0000${g}\u0000${n}`;
    return !accKeys.has(key);
  });
}

export function buildRankedGroups(
  parses: Parse[],
  opts: GroupRankOpts = {},
): ParseGroup[] {
  if (!parses.length) return [];
  const filtered = preferAccForAm(parses, opts.form);
  const groups = allUninflected(filtered)
    ? collapseIndeclToken(filtered, opts.form)
    : groupParses(filtered);
  // Occurrence parses are intentionally not rewritten by loading. Attach the
  // exact already-loaded dictionary text only to this display projection, so
  // every consumer of ranked groups sees the same resolved source gloss.
  return rankGroups(groups, opts).map((g) => ({
    ...g,
    members: g.members.map((p) => p.g || !opts.glossOf ? p : {
      ...p,
      g: opts.glossOf(p.l ?? ""),
    }),
  }));
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

/**
 * A compact, reader-facing dictionary sense. MW entries are scholarly source
 * quotations, not inline glosses: remove markup, labels and citation tails,
 * then retain the first usable English sense. The unedited quotation remains
 * available in the word-detail dictionary section.
 */
export function compactGloss(txt: string, max = GLOSS_MAX_CHARS): string | null {
  return compactMwGloss(txt, max);
}

/** Short gloss used for repeat-suppression identity across group rows. */
export function glossIdentity(txt: string): string {
  return (compactMwGloss(txt, GLOSS_MAX_CHARS) ?? "").toLowerCase();
}
