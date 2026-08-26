// Compound-member annotation (समास): DCS CoNLL-U range rows carry each
// member of a compound (form, lemma, POS, feats); build_morph_dcs.py emits
// them as Parse.m. This module renders one mini-row per member:
//   member form (IAST primary + Devanagari secondary) · inflection tags ·
//   Monier-Williams gloss of the member lemma (async; 「无词条」 when the
//   shards have no entry).
// Shared by the reader parse cards + side panel, and the lookup surfaces.
import { fetchJSON, stripAccents, type Parse } from "./api";
import { slp1KeyFor, slp1KeyVariants } from "./translit";
import { compactTagNode, isDevaStr, lemmaDualEl,
  parseDcsFeats } from "./feats";

type El = HTMLElement;
const el = (tag: string, cls?: string, text?: string): El => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text; // never innerHTML
  return e;
};

export interface CompoundMember {
  d: string; // member surface form (Devanagari)
  l: string; // member lemma (Devanagari)
  p: string; // part of speech
  f: string; // inflection tags ("पुं;2;एक", "Cpd", …)
}

/**
 * Genuineness gate (wrong-Chinese glitch fix): shard entries come in two
 * shapes that both carry member chains —
 *   • REAL DCS samāsa rows: the CoNLL-U range marks every non-head member
 *     with the `Cpd` tag, and the HEAD (last member) carries case inflection
 *     (digits 1–7 / सम्बोधन) with a nominal/participle POS.
 *   • Sandhi-fusion span rows (pipeline lotus-keys feature): adjacent-row
 *     concatenations like पश्य+एताम् or आहुः+त्वाम्+ऋषयः reuse the same `m`
 *     shape, but their first member never carries `Cpd` and their last
 *     member is often an uninflected particle (च/वत्/एव) or a finite verb.
 * Rendering a span as 「复合词成分」 presents ordinary sandhi as a compound —
 * exactly the wrong-content glitch users reported. Only chains passing this
 * test may render as samāsa blocks, everywhere (cards, panel, lookup).
 */
const CASE_TAGS = new Set([
  "1", "2", "3", "4", "5", "6", "7",
  "\u0938\u092e\u094d\u092c\u094b\u0927\u0928", // सम्बोधन (voc.)
]);

export function isGenuineSamasa(members: CompoundMember[]): boolean {
  if (members.length < 2) return false;
  const f0 = (members[0].f ?? "").split(/[;\s|]+/);
  if (!f0.includes("Cpd")) return false;
  const head = members[members.length - 1];
  // samāsa head is an inflected nominal — never particle or finite verb
  if (head.p === "indecl" || head.p === "verb") return false;
  const hf = (head.f ?? "").split(/[;\s|]+/);
  return hf.some((t) => CASE_TAGS.has(t));
}

/** Parse entries may carry the member chain (optional shard field). */
export function membersOf(p: Parse): CompoundMember[] | null {
  const m = (p as Parse & { m?: unknown }).m;
  if (!Array.isArray(m)) return null;
  const out = m.filter((x): x is CompoundMember =>
    !!x && typeof x === "object" &&
    typeof (x as CompoundMember).d === "string").slice(0, 8);
  return out.length >= 2 && isGenuineSamasa(out) ? out : null;
}

/* ---------------- member-lemma MW glosses (memoized) ---------------- */

type MwHit = { u?: string; g?: string };
const glossMemo = new Map<string, Promise<string | null>>();
const glossShardCache = new Map<string, Record<string, MwHit> | null>();

async function glossShard(letter: string):
  Promise<Record<string, MwHit> | null> {
  const cached = glossShardCache.get(letter);
  if (cached !== undefined) return cached;
  const p = await fetchJSON<Record<string, MwHit> | null>(
    `data/gloss/${letter}.json`,
  ).catch(() => null);
  glossShardCache.set(letter, p);
  return p;
}

/**
 * Monier-Williams gloss for a member lemma (either script accepted).
 * Exact SLP1 key (+ sibilant variants) only — members are headwords, so a
 * miss is honest 「无词条」 rather than a fuzzy prefix guess.
 */
export function mwGlossFor(lemma: string): Promise<string | null> {
  const key = slp1KeyFor(lemma);
  if (!key || key.length < 2) return Promise.resolve(null);
  let p = glossMemo.get(key);
  if (!p) {
    p = (async () => {
      const letter = key[0]!;
      if (!/^[a-z]$/.test(letter)) return null;
      const shard = await glossShard(letter);
      if (!shard) return null;
      for (const k of [key, ...slp1KeyVariants(key)].map((x) =>
        x.toLowerCase(),
      )) {
        const hit = shard[k];
        if (hit?.g) return hit.g;
      }
      return null;
    })();
    glossMemo.set(key, p);
  }
  return p;
}

/** One member mini-row: dual-script form + COMPACT abbr tags + async MW
 *  gloss cell (silent when the shards have no entry — R3/R5). */
function memberRow(m: CompoundMember, idx: number, total: number): El {
  const row = el("div", "comp-member");
  // joiner glyph between members (samāsa reading order top→bottom)
  const form = el("span", "comp-form");
  form.appendChild(lemmaDualEl(isDevaStr(m.d) ? m.d : m.l || m.d));
  row.appendChild(form);
  // compact inflection: mapped tags only; Cpd/unmapped extras suppressed
  const { main } = parseDcsFeats(m.f ?? "");
  if (main.length) {
    const fl = el("span", "feats comp-feats");
    main.forEach((t, i) => {
      if (i) fl.appendChild(document.createTextNode(" "));
      fl.appendChild(compactTagNode(t));
    });
    row.appendChild(fl);
  }
  const gl = el("div", "gloss comp-gloss");
  row.appendChild(gl);
  const lemmaKey = stripAccents(m.l || m.d);
  void mwGlossFor(lemmaKey).then((g) => {
    if (!gl.isConnected) return;
    if (!g) {
      gl.remove(); // 无词条 → omit silently, never a loud placeholder
      return;
    }
    gl.textContent = g.length > 160 ? `${g.slice(0, 157)}…` : g;
  });
  if (idx < total - 1) row.appendChild(el("span", "comp-plus", "+"));
  return row;
}

/** Full compound block: header + one mini-row per member. Null when this
 *  parse carries no usable member chain. */
export function compoundBlock(p: Parse): El | null {
  const members = membersOf(p);
  if (!members) return null;
  const box = el("div", "compound");
  box.appendChild(el("div", "wl-head comp-head",
    `复合词成分 Samāsa · ${members.length}`));
  members.forEach((m, i) =>
    box.appendChild(memberRow(m, i, members.length)));
  return box;
}

/**
 * First parse carrying a member chain among `parses` (best-parse first —
 * callers pass ranked parses), or null. Convenience for collapsed cards.
 */
export function firstCompound(parses: Parse[]): El | null {
  for (const p of parses) {
    const b = compoundBlock(p);
    if (b) return b;
  }
  return null;
}

/**
 * R3: every rendered analysis line ends with its English MW gloss, keyed
 * by the analysis LEMMA (slp1-keyed exact shard hit). The cell is appended
 * empty and filled async; when the shards have no entry the cell removes
 * itself — no loud placeholder, ever.
 * Shared by reader cards (render.ts), word-lookup (lookup.ts), lexicon.
 */
export function attachMwGloss(
  parent: HTMLElement,
  lemma: string,
  maxChars = 180,
): void {
  const g = document.createElement("div");
  g.className = "gloss mw-gloss";
  parent.appendChild(g);
  void mwGlossFor(lemma || "").then((txt) => {
    if (!g.isConnected) return;
    if (!txt) {
      g.remove();
      return;
    }
    g.textContent = txt.length > maxChars ? `${txt.slice(0, maxChars - 3)}…` : txt;
  });
}
