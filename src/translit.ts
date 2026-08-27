// Devanagari ⇄ IAST transliteration (standard Sanskrit mapping).
//
// devToIast:   धर्मक्षेत्रे -> dharmakṣetre   (inherent 'a' realised unless
//                                              killed by virama / replaced
//                                              by a matra)
// iastToDev:   dharmakṣetre -> धर्मक्षेत्रे   (consonant not followed by a
//                                              vowel gets explicit virama)
//
// Covered: all vowels (short/long, ṛ ṝ ḷ ḹ), guttural→labial stops incl.
// aspirates, ṅ ñ ṇ ś ṣ, anusvāra ṃ, visarga ḥ, candrabindu m̐, avagraha ’,
// Devanagari digits, OM (ॐ → oṃ), ZWJ/ZWNJ passthrough. Danda punctuation
// is shared and passes through untouched. iastToDev accepts precomposed OR
// decomposed diacritics (NFC-normalises first) and any letter case.
//
// Self-test table (round-trips both ways; verified against standard IAST):
//   धर्म        <-> dharma
//   योग         <-> yoga
//   कृष्ण        <-> kṛṣṇa
//   अर्जुन       <-> arjuna
//   संन्यास      <-> saṃnyāsa
//   भगवद्गीता    <-> bhagavadgītā
//   मोक्ष        <-> mokṣa
//   धर्मक्षेत्रे   <-> dharmakṣetre
//   शान्ति       <-> śānti
//   आत्मन्       <-> ātman
//   अहिंसा       <-> ahiṃsā
//   हरे कृष्ण     <-> hare kṛṣṇa   (spaces/punctuation preserved)

/* ---------------- shared character tables ---------------- */

const ZWJ = "\u200d";
const ZWNJ = "\u200c";
const VIRAMA = "\u094d";

/** Independent vowels: Devanagari -> IAST. */
const DEV_VOWELS = new Map<string, string>([
  ["\u0905", "a"], ["\u0906", "\u0101"], ["\u0907", "i"], ["\u0908", "\u012b"],
  ["\u0909", "u"], ["\u090a", "\u016b"], ["\u090b", "\u1e5b"],
  ["\u0960", "\u1e5d"], ["\u090c", "\u1e37"], ["\u0961", "\u1e39"],
  ["\u090f", "e"], ["\u0910", "ai"], ["\u0913", "o"], ["\u0914", "au"],
]);

/** Consonants: Devanagari -> IAST (incl. Vedic retroflex ळ). */
const DEV_CONS = new Map<string, string>([
  ["\u0915", "k"], ["\u0916", "kh"], ["\u0917", "g"], ["\u0918", "gh"],
  ["\u0919", "\u1e45"],
  ["\u091a", "c"], ["\u091b", "ch"], ["\u091c", "j"], ["\u091d", "jh"],
  ["\u091e", "\u00f1"],
  ["\u091f", "\u1e6d"], ["\u0920", "\u1e6dh"], ["\u0921", "\u1e0d"],
  ["\u0922", "\u1e0dh"], ["\u0923", "\u1e47"],
  ["\u0924", "t"], ["\u0925", "th"], ["\u0926", "d"], ["\u0927", "dh"],
  ["\u0928", "n"],
  ["\u092a", "p"], ["\u092b", "ph"], ["\u092c", "b"], ["\u092d", "bh"],
  ["\u092e", "m"],
  ["\u092f", "y"], ["\u0930", "r"], ["\u0932", "l"], ["\u0935", "v"],
  ["\u0933", "\u1e37"],
  ["\u0936", "\u015b"], ["\u0937", "\u1e63"], ["\u0938", "s"],
  ["\u0939", "h"],
]);

/** Dependent vowel signs (matras): Devanagari -> IAST. */
const DEV_MATRAS = new Map<string, string>([
  ["\u093e", "\u0101"], ["\u093f", "i"], ["\u0940", "\u012b"],
  ["\u0941", "u"], ["\u0942", "\u016b"], ["\u0943", "\u1e5b"],
  ["\u0944", "\u1e5d"], ["\u0962", "\u1e37"], ["\u0963", "\u1e39"],
  ["\u0947", "e"], ["\u0948", "ai"], ["\u094b", "o"], ["\u094c", "au"],
]);

/** Digits: Devanagari -> ASCII. */
const DEV_DIGITS = new Map<string, string>(
  "\u0966\u0967\u0968\u0969\u096a\u096b\u096c\u096d\u096e\u096f"
    .split("")
    .map((d, i) => [d, String(i)]),
);

/* ---------------- Devanagari -> IAST ---------------- */

/**
 * Transliterate Devanagari to IAST. Non-Devanagari characters (spaces,
 * Latin, danda, ZWJ/ZWNJ) pass through unchanged.
 */
export function devToIast(s: string): string {
  const chars = Array.from(s);
  let out = "";
  let pendingA = false; // bare consonant awaits its inherent vowel
  for (const ch of chars) {
    if (ch === ZWJ || ch === ZWNJ) {
      out += ch;
      continue;
    }
    if (ch === VIRAMA) {
      pendingA = false; // halant kills the inherent vowel
      continue;
    }
    const matra = DEV_MATRAS.get(ch);
    if (matra !== undefined) {
      out += matra; // matra replaces the inherent vowel
      pendingA = false;
      continue;
    }
    const cons = DEV_CONS.get(ch);
    if (cons !== undefined) {
      if (pendingA) out += "a";
      out += cons;
      pendingA = true;
      continue;
    }
    // any other character closes the inherent-vowel window
    if (pendingA) {
      out += "a";
      pendingA = false;
    }
    const vow = DEV_VOWELS.get(ch);
    if (vow !== undefined) {
      out += vow;
      continue;
    }
    switch (ch) {
      case "\u0902": // anusvāra
        out += "\u1e43";
        continue;
      case "\u0903": // visarga
        out += "\u1e25";
        continue;
      case "\u0901": // candrabindu
        out += "m\u0310";
        continue;
      case "\u093d": // avagraha
        out += "\u2019";
        continue;
      case "\u0950": // OM
        out += "o\u1e43";
        continue;
    }
    const dig = DEV_DIGITS.get(ch);
    if (dig !== undefined) {
      out += dig;
      continue;
    }
    out += ch;
  }
  if (pendingA) out += "a";
  return out;
}

/* ---------------- IAST -> Devanagari ---------------- */

// vowel -> [matra, independent]
const IA_VOWELS = new Map<string, [string, string]>([
  ["a", ["", "\u0905"]], ["\u0101", ["\u093e", "\u0906"]],
  ["i", ["\u093f", "\u0907"]], ["\u012b", ["\u0940", "\u0908"]],
  ["u", ["\u0941", "\u0909"]], ["\u016b", ["\u0942", "\u090a"]],
  ["\u1e5b", ["\u0943", "\u090b"]], ["\u1e5d", ["\u0944", "\u0960"]],
  ["\u1e37", ["\u0962", "\u090c"]], ["\u1e39", ["\u0963", "\u0961"]],
  ["e", ["\u0947", "\u090f"]], ["ai", ["\u0948", "\u0910"]],
  ["o", ["\u094b", "\u0913"]], ["au", ["\u094c", "\u0914"]],
]);

// aspirate digraphs (checked before single letters)
const IA_CONS2 = new Map<string, string>([
  ["kh", "\u0916"], ["gh", "\u0918"], ["ch", "\u091b"], ["jh", "\u091d"],
  ["\u1e6dh", "\u0920"], ["\u1e0dh", "\u0922"], ["th", "\u0925"],
  ["dh", "\u0927"], ["ph", "\u092b"], ["bh", "\u092d"],
]);
const IA_CONS1 = new Map<string, string>([
  ["k", "\u0915"], ["g", "\u0917"], ["\u1e45", "\u0919"],
  ["c", "\u091a"], ["j", "\u091c"], ["\u00f1", "\u091e"],
  ["\u1e6d", "\u091f"], ["\u1e0d", "\u0921"], ["\u1e47", "\u0923"],
  ["t", "\u0924"], ["d", "\u0926"], ["n", "\u0928"],
  ["p", "\u092a"], ["b", "\u092c"], ["m", "\u092e"],
  ["y", "\u092f"], ["r", "\u0930"], ["l", "\u0932"], ["v", "\u0935"],
  ["\u1e33", "\u0933"],
  ["\u015b", "\u0936"], ["\u1e63", "\u0937"], ["s", "\u0938"],
  ["h", "\u0939"],
]);
// signs incl. candrabindu (2 code points) and the ISO-style ṁ alias
const IA_SIGNS = new Map<string, string>([
  ["\u1e43", "\u0902"], ["m\u0323", "\u0902"], ["\u1e41", "\u0902"],
  ["\u1e25", "\u0903"], ["m\u0310", "\u0901"],
  ["\u2019", "\u093d"],
]);
// ASCII digits -> Devanagari (mirror of DEV_DIGITS)
const IA_DIGITS = new Map<string, string>(
  "0123456789".split("").map((d, i) => [d, String.fromCharCode(0x966 + i)]),
);

type TokKind = "vowel" | "cons" | "sign";

/** Longest-match token starting at cps[i]: [normalised token, length]. */
function nextTok(cps: string[], i: number): [string, number] | null {
  if (i + 1 < cps.length) {
    const two = (cps[i]! + cps[i + 1]).toLowerCase();
    if (IA_CONS2.has(two)) return [two, 2];
    if (IA_VOWELS.has(two)) return [two, 2]; // ai, au
    if (IA_SIGNS.has(two)) return [two, 2]; // m<combining> candrabindu
  }
  const one = cps[i]!.toLowerCase();
  if (IA_VOWELS.has(one) || IA_CONS1.has(one) || IA_SIGNS.has(one)) {
    return [one, 1];
  }
  return null;
}

function tokKind(t: string): TokKind {
  if (IA_CONS1.has(t) || IA_CONS2.has(t)) return "cons";
  if (IA_VOWELS.has(t)) return "vowel";
  return "sign";
}

/**
 * Transliterate IAST to Devanagari. A consonant followed by anything other
 * than a vowel receives an explicit virama (corpus convention: word-final
 * clusters/consonants carry ्). Unmapped characters pass through; letter
 * case is ignored (Devanagari has none).
 */
export function iastToDev(input: string): string {
  const cps = Array.from(input.normalize("NFC"));
  let out = "";
  let expectVowel = false; // last emission was a consonant lacking its vowel
  for (let i = 0; i < cps.length;) {
    const ch = cps[i]!;
    if (ch === ZWJ || ch === ZWNJ) {
      out += ch;
      i += 1;
      continue;
    }
    const tok = nextTok(cps, i);
    if (!tok) {
      // unmapped char — map ASCII digits, pass everything else through
      out += IA_DIGITS.get(ch) ?? ch;
      expectVowel = false;
      i += 1;
      continue;
    }
    const [t, len] = tok;
    const kind = tokKind(t);
    if (kind === "cons") {
      out += (IA_CONS2.get(t) ?? IA_CONS1.get(t))!;
      // vowel next? then it will attach as a matra — otherwise close
      // the syllable with an explicit virama (word-final clusters too)
      const j = i + len;
      const nxt = j < cps.length ? nextTok(cps, j) : null;
      if (nxt && tokKind(nxt[0]) === "vowel") {
        expectVowel = true;
      } else {
        out += VIRAMA;
        expectVowel = false;
      }
    } else if (kind === "vowel") {
      const [matra, indep] = IA_VOWELS.get(t)!;
      out += expectVowel ? matra : indep;
      expectVowel = false;
    } else {
      out += IA_SIGNS.get(t) ?? t;
      expectVowel = false;
    }
    i += len;
  }
  return out;
}

/* ---------------- SLP1 (dictionary shard keys) ----------------
 * Cologne-style SLP1 as used by the Monier-Williams gloss shards AND the
 * DCS morph shards (verified against both: sabanga/sangat -> ṅ=N,
 * kftayjalir -> ñ=Y, mokza/zakara sibilants as tabled):
 *   long vowels capitalized (A I U f F x X), aspirates single capitals
 *   (kh=K gh=G ch=C jh=J Th=W Dh=Q th=T dh=D ph=P bh=B),
 *   retroflex t/d/n = w q R, retroflex s = z, palatal s = S,
 *   anusvaara = M, visarga = H, candrabindu = ~.
 * iastToSlp1 maps standard IAST to that key space; devToSlp1 composes via
 * devToIast. lookupVariants() yields alternate keys for snapshots that use
 * the mirrored sibilant convention. */

const IA_TO_SLP: Array<[string, string]> = [
  // multi-char first (longest-match)
  ["ai", "E"], ["au", "O"],
  ["kh", "K"], ["gh", "G"], ["ch", "C"], ["jh", "J"],
  ["\u1e6dh", "W"], ["\u1e0dh", "Q"], ["th", "T"], ["dh", "D"], ["ph", "P"], ["bh", "B"],
  // candrabindu before plain m (devToIast emits m\u0310; SLP1 yogavaaha ~)
  ["m\u0310", "~"],
  ["\u1e63", "z"],                 // sa -> z        (retroflex)
  ["\u015b", "S"],                 // za -> S        (palatal)
  ["\u1e45", "N"], ["\u00f1", "Y"],
  ["\u1e6d", "w"], ["\u1e0d", "q"], ["\u1e47", "R"],
  ["\u0101", "A"], ["\u012b", "I"], ["\u016b", "U"],
  ["\u1e5b", "f"], ["\u1e5d", "F"], ["\u1e37", "x"], ["\u1e39", "X"],
  ["\u1e43", "M"], ["\u1e25", "H"],
];

export function iastToSlp1(sRaw: string): string {
  const s = sRaw.normalize("NFC").toLowerCase();
  let out = "";
  let i = 0;
  outer: while (i < s.length) {
    for (const [ia, slp] of IA_TO_SLP) {
      if (s.startsWith(ia, i)) {
        out += slp;
        i += ia.length;
        continue outer;
      }
    }
    const ch = s[i];
    out += /[a-z]/.test(ch) ? ch : "";   // drop anything non-key (punct etc.)
    i += 1;
  }
  return out;
}

/** Devanagari surface token -> canonical SLP1 shard key. */
export function devToSlp1(s: string): string {
  return iastToSlp1(devToIast(s));
}

/**
 * Devanagari/Latin surface token -> SLP1 shard LOOKUP key (QA-LOCAL-1).
 * The gloss shards are lowercase-SLP1-keyed ("darmakzetre", not
 * "Darmakzetre"), while iastToSlp1 emits capitals for long vowels and
 * aspirates — so proper-noun-ish display forms produced capital-initial
 * probes that could never match. Normalize AFTER conversion, BEFORE any
 * letter-shard selection. Display strings keep their original casing;
 * only this lookup key lowercases.
 */
export function slp1KeyFor(s: string): string {
  return iastToSlp1(devToIast(s)).toLowerCase();
}

/** Alternate shard keys for snapshots with the mirrored sibilant mapping. */
export function slp1KeyVariants(key: string): string[] {
  const variants = new Set<string>([key]);
  for (const [a, b] of [["z", "S"], ["S", "z"]] as Array<[string, string]>) {
    if (key.includes(a)) variants.add(key.split(a).join(b));
  }
  return [...variants];
}

/**
 * ALL valid shard-key spellings of one surface form — client mirror of
 * pipeline/build_morph_dcs.py _canonical_keys(). Devanagari and roman
 * input normalize ai/au differently (वै -> "ve" via SLP1 E/O folding vs
 * ascii "vai" keeping the digraph), so BOTH flavors are derived; a shard
 * key is an EXACT surface hit only when it is one of these. Anything else
 * resolved from the surface index (its stem-prefix fallback) is a fuzzy
 * match and must not feed parse cards.
 */
export function canonicalKeysFor(form: string): Set<string> {
  const out = new Set<string>();
  const add = (k: string | undefined): void => {
    if (k && /^[a-z~]+$/.test(k)) out.add(k);
  };
  if (isDevanagari(form)) {
    add(slp1KeyFor(form)); // deva -> IAST -> SLP1 flavor
    const rom = devToIast(form).toLowerCase();
    if (/^[a-z]+$/.test(rom)) add(rom); // pure-ascii romanization: HK flavor
  } else {
    add(slp1KeyFor(form));
  }
  return out;
}

/**
 * Trust gate for shard keys resolved through the surface slices
 * (qa "morph-parse discipline" R4): TRUE only when `key` is one of the
 * form's own canonical spellings — i.e. the shards carry analyses for this
 * EXACT surface shape. Keys produced by the build's longest-resolving-
 * prefix stem fallback fail the membership test here, so their (possibly
 * unrelated) analyses are never rendered. Boundary-aware: shard key length
 * must equal the canonical spelling length (exact equality, not prefix
 * substring). Hyphenated display tokens no longer fall back to member
 * substring — compound analyses surface via Parse.m member chains only
 * (compoundBlock), never via head-substring shard lookup.
 */
export function surfaceKeyTrusted(form: string, key: string): boolean {
  if (!form || !key) return false;
  const cands = canonicalKeysFor(form);
  if (!cands.has(key)) return false;
  // exact length equality already implied by Set membership, but guard
  // explicitly against any future prefix-substring looseness
  for (const cand of cands) {
    if (cand === key) return true;
  }
  return false;
}

// Test/dev hook: lets Playwright resolve shard keys without importing TS.
if (typeof window !== "undefined") {
  (window as unknown as Record<string, unknown>).__iastToSlp1 = iastToSlp1;
}

/** True when the string contains Devanagari-block characters (U+0900–U+097F). */
export function isDevanagari(s: string): boolean {
  return /[\u0900-\u097f]/.test(s);
}
