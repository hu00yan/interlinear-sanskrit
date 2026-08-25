// Typed facade over the Samsaadhanii-mbt wasm parser (public/wasm/webdemo.wasm).
//
// The module targets wasm-gc + JS String Builtins, so MoonBit strings cross
// the boundary natively — no UTF-8 glue (integration-guide §2). Every entry
// point here is total: null / "" instead of throw, so callers can treat the
// parser as a pure enhancement layer and render the plain text when it is
// absent. JSON schemas mirror integration-guide §3; authoritative definition:
// moonbit-samsaadhanii/src/webdemo/api.mbt.
//
// This file is intentionally self-contained and NOT imported anywhere yet —
// wiring into render.ts etc. is a later task.

export interface AnalyzeCandidate {
  /** Sandhi parts in Devanagari (NFC). */
  parts_deva: string[];
  /** Same parts in IAST (lowercase). */
  parts_iast: string[];
  /** ITRANS parts (entries are "" before the T2 table landed). */
  parts_itrans: string[];
  /** Lexicon hits among the parts. */
  hits: number;
  /** Total number of parts for this candidate. */
  members: number;
}

export interface AnalyzeResult {
  input: string;
  /** Internal WX-domain form of the fused input. */
  wx: string;
  /** Full candidate count; `candidates` is capped at 8. */
  total: number;
  /** Sorted by lexicon coverage, fewest parts first. */
  candidates: AnalyzeCandidate[];
}

export type MorphPos = "noun" | "pron" | "verb" | "indecl" | "part";

export interface MorphAnalysis {
  /** WX stem ("" for pos-only rows). */
  lemma: string;
  lemma_deva: string;
  lemma_iast: string;
  /**
   * Declared as MorphPos per the current schema; an unknown future value from
   * a newer artifact passes through as-is at runtime.
   */
  pos: MorphPos;
  feats: string[];
}

export interface MorphResult {
  input: string;
  wx: string;
  found: boolean;
  analyses: MorphAnalysis[];
}

export type TranslitScheme = "deva" | "iast" | "itrans";

interface WasmExports {
  analyze_word(deva: string): string;
  morph_lookup(deva: string): string;
  translit3(deva: string, scheme: string): string;
  version(): string;
}

let exp: WasmExports | null = null;
let initPromise: Promise<boolean> | null = null;

// Magic-header module with GC-free func types, straight from integration-guide
// §4: a cheap capability probe so we never download 1.4 MB on a runtime that
// cannot instantiate the real thing anyway.
const PROBE_BYTES = new Uint8Array([
  0, 97, 115, 109, 1, 0, 0, 0, 1, 13, 2, 96, 2, 127, 127, 96, 1, 127, 96, 0, 0,
]);

function wasmUrl(): string {
  // document.baseURI instead of import.meta.env.BASE_URL: keeps this module
  // free of vite/client typings and correct under any <base href>.
  return new URL("wasm/webdemo.wasm", document.baseURI).href;
}

async function load(): Promise<boolean> {
  try {
    if (!WebAssembly.validate(PROBE_BYTES)) return false;
    const res = await fetch(wasmUrl());
    if (!res.ok) return false;
    // arrayBuffer(), not instantiateStreaming: immune to a server serving
    // .wasm with a wrong Content-Type (integration-guide §2).
    const bytes = await res.arrayBuffer();
    // The js-string-builtins three-line pattern. lib.dom.d.ts has no typing
    // for the third argument yet, so widen locally once, right here.
    const instantiate3 = WebAssembly.instantiate as unknown as (
      bytes: BufferSource,
      imports: WebAssembly.Imports,
      options: { builtins: string[]; importedStringConstants: string },
    ) => Promise<WebAssembly.WebAssemblyInstantiatedSource>;
    const { instance } = await instantiate3(bytes, {}, {
      builtins: ["js-string"],
      importedStringConstants: "_", // MoonBit compiler's constant-string namespace default
    });
    const e = instance.exports as unknown as WasmExports;
    // Touch one export during init so a corrupt/mismatched artifact fails
    // here rather than on the user's first click.
    if (typeof e.version() !== "string") return false;
    exp = e;
    return true;
  } catch {
    return false;
  }
}

/**
 * Lazily fetch + instantiate the wasm parser. Idempotent and memoized:
 * concurrent/repeat calls share one attempt. Resolves false (never throws)
 * on unsupported runtimes (needs WasmGC + JS String Builtins), missing or
 * broken artifacts.
 */
export function initParser(): Promise<boolean> {
  if (!initPromise) initPromise = load();
  return initPromise;
}

/** True once analyzeWord/morphLookup/translit3 can produce results. */
export function parserReady(): boolean {
  return exp !== null;
}

/** Artifact provenance string (version / rule count / data-slice SHAs), or null before init. */
export function parserVersion(): string | null {
  try {
    return exp ? exp.version() : null;
  } catch {
    return null;
  }
}

function parseJson(s: string): unknown {
  try {
    return JSON.parse(s) as unknown;
  } catch {
    return null;
  }
}

function strArr(v: unknown): string[] | null {
  if (!Array.isArray(v)) return null;
  return v.every((x) => typeof x === "string") ? (v as string[]) : null;
}

const POS_VALUES: readonly MorphPos[] = ["noun", "pron", "verb", "indecl", "part"];

function toAnalyze(v: unknown): AnalyzeResult | null {
  if (!v || typeof v !== "object") return null;
  const r = v as Record<string, unknown>;
  if (!Array.isArray(r.candidates)) return null;
  const candidates: AnalyzeCandidate[] = [];
  for (const c of r.candidates) {
    if (!c || typeof c !== "object") continue;
    const o = c as Record<string, unknown>;
    const deva = strArr(o.parts_deva);
    const iast = strArr(o.parts_iast);
    const itrans = strArr(o.parts_itrans);
    if (!deva || !iast || !itrans) continue;
    candidates.push({
      parts_deva: deva,
      parts_iast: iast,
      parts_itrans: itrans,
      hits: typeof o.hits === "number" ? o.hits : 0,
      members: typeof o.members === "number" ? o.members : deva.length,
    });
  }
  return {
    input: typeof r.input === "string" ? r.input : "",
    wx: typeof r.wx === "string" ? r.wx : "",
    total: typeof r.total === "number" ? r.total : candidates.length,
    candidates,
  };
}

function toMorph(v: unknown): MorphResult | null {
  if (!v || typeof v !== "object") return null;
  const r = v as Record<string, unknown>;
  if (typeof r.found !== "boolean" || !Array.isArray(r.analyses)) return null;
  const analyses: MorphAnalysis[] = [];
  for (const a of r.analyses) {
    if (!a || typeof a !== "object") continue;
    const o = a as Record<string, unknown>;
    if (typeof o.pos !== "string") continue;
    const feats = strArr(o.feats);
    if (!feats) continue;
    analyses.push({
      lemma: typeof o.lemma === "string" ? o.lemma : "",
      lemma_deva: typeof o.lemma_deva === "string" ? o.lemma_deva : "",
      lemma_iast: typeof o.lemma_iast === "string" ? o.lemma_iast : "",
      pos: (POS_VALUES as readonly string[]).includes(o.pos)
        ? (o.pos as MorphPos)
        : "part",
      feats,
    });
  }
  return {
    input: typeof r.input === "string" ? r.input : "",
    wx: typeof r.wx === "string" ? r.wx : "",
    found: r.found,
    analyses,
  };
}

/**
 * Split a fused Devanagari surface form into candidate part sequences.
 * Returns null when the parser is not initialized or output was malformed;
 * an unparseable word is a valid result with one identity candidate, hits=0.
 */
export function analyzeWord(deva: string): AnalyzeResult | null {
  if (!exp) return null;
  try {
    return toAnalyze(parseJson(exp.analyze_word(deva)));
  } catch {
    return null;
  }
}

/**
 * Look up stem / POS / features for a single surface form (feed it
 * `analyzeWord(...).candidates[i].parts_deva[j]` to close the loop).
 * `found: false` means "not in the embedded 35k subset", not an error.
 * Returns null only when uninitialized/failed.
 */
export function morphLookup(deva: string): MorphResult | null {
  if (!exp) return null;
  try {
    return toMorph(parseJson(exp.morph_lookup(deva)));
  } catch {
    return null;
  }
}

/**
 * Whole-string transliteration. "" signals failure/uninitialized, and also
 * what the artifact returns for an unknown scheme — note "itrans" stays ""
 * until probed non-empty (guide §3.2).
 */
export function translit3(deva: string, scheme: TranslitScheme): string {
  if (!exp) return "";
  try {
    return exp.translit3(deva, scheme);
  } catch {
    return "";
  }
}

/**
 * Kick off initParser() when the main thread goes idle, so the first click on
 * a word does not pay the ~80 ms cold start (guide §6). Safe to call
 * unconditionally and repeatedly.
 */
export function warmup(): void {
  if (exp || initPromise) return;
  const g = globalThis as {
    requestIdleCallback?: (
      cb: () => void,
      opts?: { timeout: number },
    ) => number;
  };
  if (typeof g.requestIdleCallback === "function") {
    g.requestIdleCallback(() => void initParser(), { timeout: 3000 });
  } else {
    setTimeout(() => void initParser(), 200);
  }
}
