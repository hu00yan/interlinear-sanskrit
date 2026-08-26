// Data access: static JSON under public/data, fetched lazily and
// cached per file. No backend involved — except /api/morph (optional
// Cloudflare Pages Function proxying the Tufts morphology service), which
// degrades gracefully on static hosts.
//
// Corpus contract (see pipeline/build_corpus.py):
//   data/catalog.json                     authors -> works -> part files
//   data/texts/<tlg>/<work>-partNN.json   {"id","author","title","kind",
//                                          "units":[{"ref","words"}]}
import { fromBeta, toBeta } from "./betacode";
import { parseDcsFeats, posAbbr } from "./feats";
import { surfaceKeyTrusted } from "./translit";

export interface CatalogWork {
  id: string;
  title: string;
  urn: string;
  license: string;
  files: string[];
  unitCount: number;
  /** Chinese title when the catalog ships one (added concurrently);
   *  absent → the original title renders alone. Read via zhTitleOf. */
  titleZh?: string;
  /** ISO 639 set tag; "pi" (Pali) routes under #/pali/ and skips the
   *  Devanagari display pipeline. Absent = Sanskrit ("sa"). */
  lang?: string;
}
export interface CatalogAuthor {
  name: string;
  key: string;
  /** Chinese group name when the catalog ships one (some corpus groups
   *  only); absent → the original name renders alone in headers. */
  nameZh?: string;
  /** Author-level language default when individual works omit lang. */
  lang?: string;
  works: CatalogWork[];
}

/** Defensive titleZh reader: catalog.json gains the field concurrently;
 *  absent / non-string / whitespace-only all yield "" → original only. */
export function zhTitleOf(w: unknown): string {
  const zh = (w as { titleZh?: unknown } | null)?.titleZh;
  return typeof zh === "string" ? zh.trim() : "";
}
/** Defensive nameZh reader, same contract as zhTitleOf. */
export function zhNameOf(a: unknown): string {
  const zh = (a as { nameZh?: unknown } | null)?.nameZh;
  return typeof zh === "string" ? zh.trim() : "";
}

/** Effective catalog language of a work: work.lang, else author.lang,
 *  else "sa". Drives home-section filtering and route prefixes. */
export function catalogLang(
  w: CatalogWork,
  a?: CatalogAuthor,
): string {
  return w.lang ?? a?.lang ?? "sa";
}

/** True when the catalog ships usable English translation files for this
 *  work (translation present with at least one string file path). */
export function hasTranslation(w: unknown): boolean {
  const t = (w as { translation?: { files?: unknown } } | null)?.translation;
  return !!t && Array.isArray(t.files) &&
    t.files.some((f) => typeof f === "string");
}

/** True when the catalog ships usable Chinese translation files for this
 *  work (translationZh present with at least one string file path). */
export function hasTranslationZh(w: unknown): boolean {
  const t = (w as { translationZh?: { files?: unknown } } | null)
    ?.translationZh;
  return !!t && Array.isArray(t.files) &&
    t.files.some((f) => typeof f === "string");
}

/** Three-tier taxonomy: true ONLY for truly untranslated works — no
 *  English AND no Chinese translation files. Only these get the 「无译文」
 *  badge and the reader's 「此卷暂无可用译文」 notice; zh-only works
 *  (tier 2) instead default the translation layer to 汉译, and dual
 *  works (EN+zh, tier 1) ship no badge at all. */
export function isUntranslated(w: unknown): boolean {
  return !hasTranslation(w) && !hasTranslationZh(w);
}

/** Canonical hash route for a work: Pali works live under #/pali/. */
export function workRoute(w: CatalogWork, a?: CatalogAuthor): string {
  return catalogLang(w, a) === "pi" ? `#/pali/${w.id}` : `#/${w.id}`;
}
export interface Catalog {
  authors: CatalogAuthor[];
}

/** One display unit: a verse line or a ≤~60-word prose chunk. */
export interface Unit {
  ref: string;
  words: string[];
}
export interface WorkPart {
  id: string;
  author: string;
  title: string;
  kind: "verse" | "prose";
  units: Unit[];
}
export interface Parse {
  l: string; // lemma (Unicode)
  p: string; // part of speech
  f: string; // features
  x: string; // dialects / stem types
  /** Inline English gloss when the DCS shard ships one (optional). */
  g?: string;
}
export interface Gloss {
  u: string; // headword (Unicode)
  g: string; // Monier-Williams gloss
}

const jsonCache = new Map<string, Promise<unknown>>();

/** Fetch + decode one static JSON path (relative to site root), cached. */
export function fetchJSON<T>(path: string): Promise<T> {
  let p = jsonCache.get(path);
  if (!p) {
    p = fetch(path).then((r) => {
      if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
      return r.json() as Promise<T>;
    });
    jsonCache.set(path, p);
    p.catch(() => jsonCache.delete(path));
  }
  return p as Promise<T>;
}

export function loadCatalog(): Promise<Catalog> {
  return fetchJSON<Catalog>("data/catalog.json");
}

/**
 * Load a work part. Accepts BOTH unit shapes (dist-slimming):
 *   {ref, words: string[]}   (source/pipeline shape)
 *   {ref, w: "a b c"}        (postbuild compacted shape)
 */
export function loadPart(relPath: string): Promise<WorkPart> {
  return fetchJSON<WorkPart>(`data/${relPath}`).then((part) => {
    for (const u of part.units as unknown as Array<Record<string, unknown>>) {
      if (typeof u.w === "string" && !Array.isArray(u.words)) {
        u.words = (u.w as string).split(" ").filter(Boolean);
      }
    }
    return part;
  });
}

/**
 * Mirror of pipeline/betacode.strip_accents: lowercase, NFD, drop
 * combining marks, fold final sigma.
 */
export function stripAccents(word: string): string {
  // Sanskrit build: tokens are Devanagari; shard keys are exact surface forms
  // (resolved via data/morph/_surface/*.json slices in loadMorph), so do NOT
  // NFD-strip Devanagari — it would destroy matras.
  if (/[\u0900-\u097f]/.test(word)) return word;
  const d = word.toLowerCase().normalize("NFD");
  const s = Array.from(d)
    .filter((c) => !isCombining(c))
    .join("");
  return s.replace(/ς/g, "σ");
}

// surface Devanagari token -> slp1 shard key, via LAZY SLICES (built by
// pipeline/build_morph_dcs.py):
//   data/morph/_surface/<name>.json         corpus-wide, by Devanagari initial
//   data/morph/_surface/by-work/<id>.json   one catalog work's tokens (small;
//                                           the reader's primary slice)
// The monolith _surface_index.json is no longer fetched (kept on disk one
// release as a rollback artifact — TODO remove next release).
type SurfaceSlice = Record<string, string>;

// Devanagari initial char -> slice file name. MUST mirror SLICE_NAME in
// pipeline/build_morph_dcs.py exactly; bucketing rule both sides: first
// mapped char scanning the token left-to-right.
const DEV_SLICE: Record<string, string> = {
  "\u0905": "a", "\u0906": "aa", "\u0907": "i", "\u0908": "ii",
  "\u0909": "u", "\u090a": "uu", "\u090b": "r", "\u0960": "r",
  "\u090c": "l", "\u0961": "l",
  "\u090f": "e", "\u0910": "ai", "\u0913": "o", "\u0914": "au",
  "\u0950": "om",
  "\u093d": "z",
  "\u0915": "k", "\u0958": "k",
  "\u0916": "kh", "\u0959": "kh",
  "\u0917": "g", "\u095a": "g",
  "\u0918": "gh",
  "\u0919": "ng",
  "\u091a": "ch",
  "\u091b": "chh",
  "\u091c": "j", "\u095b": "j",
  "\u091d": "jh",
  "\u091e": "ny",
  "\u091f": "t", "\u0924": "t",
  "\u0920": "th", "\u0925": "th",
  "\u0921": "d", "\u0926": "d", "\u095c": "d",
  "\u0922": "dh", "\u0927": "dh", "\u095d": "dh",
  "\u0923": "n", "\u0928": "n",
  "\u092a": "p",
  "\u092b": "ph", "\u095e": "ph",
  "\u092c": "b",
  "\u092d": "bh",
  "\u092e": "m",
  "\u092f": "y", "\u095f": "y",
  "\u0930": "r",
  "\u0932": "l", "\u0933": "l",
  "\u0935": "v",
  "\u0936": "sh",
  "\u0937": "shh",
  "\u0938": "s",
  "\u0939": "h",
};

/** Slice holding this form's entry, or null when no bucket applies. */
function devSliceName(form: string): string | null {
  for (const ch of form) {
    const name = DEV_SLICE[ch];
    if (name) return name;
  }
  return null;
}

/**
 * Resolve one form against a scope slice when it loaded (authoritative:
 * it holds every resolvable token of that work's text), else fall back to
 * the corpus-wide letter slices. A missing/failed slice file just means
 * lookups miss — never an error.
 */
async function surfaceKeyIn(
  form: string,
  scoped: Promise<SurfaceSlice | null>,
): Promise<string | null> {
  const slice = await scoped;
  if (slice) return slice[form] ?? null;
  const name = devSliceName(form);
  if (!name) return null;
  const letters = await fetchJSON<SurfaceSlice | null>(
    `data/morph/_surface/${name}.json`,
  ).catch(() => null);
  return letters?.[form] ?? null;
}

async function surfaceKey(form: string, scope?: string): Promise<string | null> {
  if (!/[\u0900-\u097f]/.test(form)) return stripAccents(form);
  // fetchJSON dedupes concurrent calls for the same path and caches the
  // promise in memory, so per-form calls here cost one network fetch total.
  const scoped = scope !== undefined
    ? fetchJSON<SurfaceSlice | null>(
        `data/morph/_surface/by-work/${scope}.json`,
      ).catch(() => null)
    : Promise.resolve(null);
  return surfaceKeyIn(form, scoped);
}

function isCombining(c: string): boolean {
  // combining diacritical marks blocks (incl. Greek Extended handled by NFD)
  const re = /[\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20f0\ufe20-\ufe2f]/;
  return re.test(c);
}

function shardLetter(stripped: string): string | null {
  const betaFirst = firstBetaLetter(stripped);
  return /[a-z]/.test(betaFirst) ? betaFirst : null;
}

/** First char of the beta-code transliteration of a stripped greek word. */
const BETA: Record<string, string> = {
  α: "a", β: "b", γ: "g", δ: "d", ε: "e", ζ: "z", η: "h", θ: "q",
  ι: "i", κ: "k", λ: "l", μ: "m", ν: "n", ξ: "c", ο: "o", π: "p",
  ρ: "r", σ: "s", τ: "t", υ: "u", φ: "f", χ: "x", ψ: "y", ω: "w",
};
function firstBetaLetter(stripped: string): string {
  for (const ch of stripped) {
    const b = BETA[ch];
    if (b) return b;
  }
  return "";
}

async function loadShardMap<K, V>(
  keys: string[],
  dir: string,
  keyOf: (k: string) => string,
): Promise<Map<string, V>> {
  const letters = new Set<string>();
  for (const k of keys) {
    const l = shardLetter(keyOf(k));
    if (l) letters.add(l);
  }
  await Promise.all(
    Array.from(letters, (l) =>
      fetchJSON<Record<string, V>>(`${dir}/${l}.json`).catch(() => null),
    ),
  );
  const out = new Map<string, V>();
  for (const k of keys) {
    const l = shardLetter(keyOf(k));
    if (!l) continue;
    const shard = (await fetchJSON<Record<string, V> | null>(
      `${dir}/${l}.json`,
    ).catch(() => null)) as Record<string, V> | null;
    const v = shard?.[keyOf(k)];
    if (v !== undefined) out.set(keyOf(k), v);
  }
  return out;
}

/** Analyses for surface forms, keyed by accent-stripped form.
 *
 * `scope` = catalog work id: resolves against that work's small per-work
 * slice (`_surface/by-work/<id>.json`) instead of the corpus-wide letter
 * slices. Absent/failed slice files degrade to letter slices (scope-less
 * callers, e.g. the lexicon box) and a miss is just "no parse".
 *
 * HONESTY GATE (R4): a resolved key counts ONLY when it is one of the
 * form's own canonical spellings (surfaceKeyTrusted). The build's surface
 * index also stores longest-resolving-PREFIX stem fallbacks; those keys
 * carry analyses of a DIFFERENT (shorter) word and are dropped here, so
 * tokens without exact shard coverage render no parse card at all. */
export async function loadMorph(
  forms: string[],
  scope?: string,
): Promise<Map<string, Parse[]>> {
  const uniq = Array.from(new Set(forms));
  if (scope === undefined) {
    // warm every needed letter slice concurrently (fetchJSON dedupes) so
    // the per-form loop below resolves from the in-memory cache
    await Promise.all(
      uniq.map((f) => {
        const name = devSliceName(f);
        return name === null ? null
          : fetchJSON(`data/morph/_surface/${name}.json`).catch(() => null);
      }),
    );
  }
  const out = new Map<string, Parse[]>();
  for (const form of uniq) {
    const key = await surfaceKey(form, scope);
    if (!key || !surfaceKeyTrusted(form, key)) continue;
    const l = key[0];
    if (!l) continue;
    const shard = await fetchJSON<Record<string, Parse[]> | null>(
      `data/morph/${l}.json`,
    ).catch(() => null);
    // dedupe at COLLECTION time: identical (lemma, abbr-feats, gloss)
    // triplets inside one shard array never enter the morph map
    if (shard?.[key]) out.set(form, dedupeParses(shard[key]));
  }
  return out;
}

/* ---------------- analysis de-duplication ----------------
 * The DCS pipeline ships one analysis ROW PER CORPUS OCCURRENCE, so a
 * single shard entry often contains byte-identical analyses — and the
 * reader rendered each as its own stacked line ("rāma m. sg. nom." twice),
 * which reads as broken repetition. Identity here is the DISPLAYED triplet:
 * lemma + ABBREVIATED feature string + gloss. Keying on the compact-abbr
 * projection (feats.ts) also collapses raw tag orderings that display
 * identically ("पुं;2;एक" ≡ "पुं;एक;2").
 *
 * Collection point (merge-spec step 3): surface resolution picks exactly
 * ONE shard key per form — the by-work slice when present, else the
 * corpus-wide letter slices — so the two paths never concatenate and
 * duplicates can only arrive INSIDE one shard array. Dropping them here,
 * while candidates are collected into the morph map, keeps every consumer
 * (reader columns, word panel, lookup box, lexicon drawer) clean without
 * per-render work. First occurrence wins, so ranking order is unchanged. */

/** Displayed identity of one analysis: the dedupe triplet key. */
export function parseDedupeKey(p: Parse): string {
  const abbr = parseDcsFeats(p.f ?? "").main.map((t) => t.ab).join(" ");
  return `${p.l ?? ""}\u0000${posAbbr(p.p)}\u0000${abbr}\u0000${p.g ?? ""}`;
}

/** Drop analyses whose (lemma, abbreviated features, gloss) triplet was
 *  already seen; order-preserving (first occurrence kept). */
export function dedupeParses(parses: Parse[]): Parse[] {
  const seen = new Set<string>();
  const out: Parse[] = [];
  for (const p of parses) {
    const k = parseDedupeKey(p);
    if (!seen.has(k)) {
      seen.add(k);
      out.push(p);
    }
  }
  return out;
}

/** Dictionary entries for lemma headwords, keyed by accent-stripped lemma. */
export async function loadGloss(lemmas: string[]): Promise<Map<string, Gloss>> {
  const stripped = Array.from(new Set(lemmas.map(stripAccents)));
  return loadShardMap<never, Gloss>(stripped, "data/gloss", (s) => s);
}

/* ---------------- live analysis (optional Pages Function) ---------------- */

// Morpheus POS names -> the single-letter codes used by the static shards.
const POS_CODE: Record<string, string> = {
  noun: "N", verb: "V", participle: "P", adjective: "A", adverb: "D",
  conjunction: "C", preposition: "R", pronoun: "X", article: "L",
  particle: "G", numeral: "M", interjection: "E", exclamation: "E",
  punctuation: "U",
};

function posCode(name: string): string {
  return POS_CODE[name.trim().toLowerCase()] ??
    name.trim().slice(0, 1).toUpperCase();
}

// Spelled-out Morpheus feature values -> shard-style abbreviations
// ("pres ind act 3rd sg", "masc acc sg").
const FEATURE_ABBR: Record<string, string> = {
  // case
  nominative: "nom", genitive: "gen", dative: "dat", accusative: "acc",
  vocative: "voc", ablative: "abl",
  // gender
  masculine: "masc", feminine: "fem", neuter: "neut", common: "masc/fem",
  // number
  singular: "sg", plural: "pl", dual: "dual",
  // tense
  present: "pres", imperfect: "impf", future: "fut", aorist: "aor",
  perfect: "perf", pluperfect: "plup",
  // mood (participle fills the mood slot in shard feature strings)
  indicative: "ind", subjunctive: "subj", optative: "opt",
  imperative: "imperat", infinitive: "inf", participle: "part", gerund: "ger",
  // voice
  active: "act", middle: "mid", passive: "pass",
  "middle/passive": "mid/pass",
  // degree
  comparative: "comp", superlative: "sup",
};

function abbr(value: string): string {
  // Compound values arrive as one element ("nominative/vocative"):
  // abbreviate each slash-separated component.
  return value
    .trim()
    .split("/")
    .map((part) => {
      const v = part.trim().toLowerCase();
      return FEATURE_ABBR[v] ?? part.trim();
    })
    .join("/");
}

function childrenByLocal(el: Element, local: string): Element[] {
  const out: Element[] = [];
  for (const child of el.children) {
    if (child.localName === local) out.push(child);
  }
  return out;
}

function firstChildText(el: Element, local: string): string {
  const child = childrenByLocal(el, local)[0];
  return child?.textContent?.trim() ?? "";
}

/** Headword element -> Unicode lemma; beta-code and comma variants handled. */
function hdwdToLemma(hdwd: Element): string {
  const text = (hdwd.textContent ?? "").trim();
  if (!text) return "";
  const lang = hdwd.getAttribute("xml:lang") ?? hdwd.getAttribute("lang") ?? "";
  const betaish = /^[*()\\\/+=|,\sa-z0-9]+$/.test(text);
  const unicode = lang.includes("beta") || betaish ? fromBeta(text) : text;
  const parts = unicode.split(","); // lu_/ein,lu/w -> lu/w (pipeline rule)
  return parts[parts.length - 1].trim();
}

function inflCard(lemma: string, infl: Element): Parse {
  const posName = firstChildText(infl, "pofs");
  const isPart = posName.trim().toLowerCase() === "participle";
  const slots: string[] = [];
  const push = (local: string) => {
    const v = firstChildText(infl, local);
    if (v) slots.push(abbr(v));
  };
  push("tense");
  if (isPart) slots.push("part"); else push("mood");
  push("voice");
  push("person");
  push("gend");
  push("case");
  push("num");

  // x: dialects space-separated, then stem types comma-joined (pipeline rule)
  const dialects = childrenByLocal(infl, "dialect")
    .concat(childrenByLocal(infl, "dial"))
    .map((d) => d.textContent?.trim() ?? "")
    .filter(Boolean);
  const stemtypes = childrenByLocal(infl, "stemtype")
    .concat(childrenByLocal(infl, "derivtype"))
    .map((s) => s.textContent?.trim() ?? "")
    .filter(Boolean);
  let x = dialects.join(" ");
  if (stemtypes.length) x += (x ? "|" : "") + stemtypes.join(",");

  return { l: lemma, p: posCode(posName), f: slots.join(" "), x };
}

/**
 * Parse a Harpocrates RDF/XML response into shard-shaped cards.
 * Namespace-agnostic: matches on local names (entry/dict/hdwd/infl/...),
 * so either RDF wrapper shape parses.
 */
export function parseLiveRdf(xml: string): Parse[] {
  const doc = new DOMParser().parseFromString(xml, "application/xml");
  if (doc.getElementsByTagName("parsererror").length) {
    throw new Error("live service returned invalid XML");
  }
  const cards: Parse[] = [];
  for (const entry of Array.from(doc.getElementsByTagName("*"))) {
    if (entry.localName !== "entry") continue;
    const dicts = childrenByLocal(entry, "dict");
    let lemma = "";
    if (dicts.length) {
      const hdwds = childrenByLocal(dicts[0], "hdwd");
      if (hdwds.length) lemma = hdwdToLemma(hdwds[0]);
    }
    const infls = childrenByLocal(entry, "infl");
    for (const infl of infls) {
      const card = inflCard(lemma, infl);
      if (card.p || card.f || card.x) cards.push(card);
    }
    if (!infls.length && dicts.length && lemma) {
      // indeclinable: synthesize one card from dict-level info
      const card: Parse = {
        l: lemma,
        p: posCode(firstChildText(dicts[0], "pofs")),
        f: [firstChildText(dicts[0], "decl"), firstChildText(dicts[0], "gend")]
          .filter(Boolean)
          .join(" "),
        x: "",
      };
      if (card.p || card.f) cards.push(card);
    }
  }
  return cards;
}

/**
 * Analyse one Unicode Greek form via /api/morph (Cloudflare Pages Function
 * proxying the Tufts Harpocrates service). Throws on transport errors —
 * callers must degrade gracefully when the endpoint doesn't exist.
 * A resolve with an empty array means: analysed fine, form simply unknown.
 */
export async function fetchLiveParse(word: string): Promise<Parse[]> {
  const beta = toBeta(word);
  const res = await fetch(
    `/api/morph?lang=grc&word=${encodeURIComponent(beta)}`,
  );
  if (!res.ok) throw new Error(`live service HTTP ${res.status}`);
  // Static hosts fall back to index.html with HTTP 200 — treat as absent.
  const type = res.headers.get("content-type") ?? "";
  if (!/xml|json/i.test(type)) {
    throw new Error("live endpoint absent (static host)");
  }
  return parseLiveRdf(await res.text());
}
