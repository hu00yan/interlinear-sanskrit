// Dictionary drawer: one search box resolving ANY Sanskrit/Pali input.
// Two lookup paths, results merged (same data as the home word-lookup box):
//   1. morph shards (surface form -> parse cards with dual-script tags)
//   2. Monier-Williams gloss shards via SLP1 keys — exact headword first,
//      then headwords starting with the query key.
// Input accepts Devanagari AND IAST in any mix; direction is detected per
// keystroke and both spellings are probed. NO Greek/Beta-Code/LSJ paths —
// this drawer was ported from the Greek reader and fully de-Greeked.
// Keyboard: Enter focuses first result; ArrowUp/Down navigate; Esc closes.
import { fetchJSON, loadMorph, stripAccents, type Parse } from "./api";
import { devToIast, iastToDev, isDevanagari, slp1KeyFor,
  slp1KeyVariants } from "./translit";
import { compactFeatsEl, featTagEl, lemmaDualEl,
  parseDcsFeats } from "./feats";
import { attachMwGloss } from "./compound";

type El = HTMLElement;
const el = (tag: string, cls?: string, text?: string): El => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text; // never innerHTML
  return e;
};

interface MwEntry {
  u: string; // headword as shipped (usually Devanagari)
  g: string; // English gloss
}

let drawer: El | null = null;
let input: HTMLInputElement | null = null;
let hint: El | null = null;
let results: El | null = null;
let searchSeq = 0;

function ensureDrawer(): El {
  if (drawer) return drawer;
  drawer = el("aside", "drawer left hidden");
  drawer.setAttribute("aria-label", "Dictionary");

  const close = el("button", "close-btn", "×");
  close.setAttribute("aria-label", "Close dictionary");
  close.addEventListener("click", closeLexicon);
  drawer.appendChild(close);

  drawer.appendChild(el("h2", undefined, "Lexicon"));

  input = el("input", "lex-search") as HTMLInputElement;
  input.type = "search";
  input.placeholder = "Sanskrit / Pāli — राम or rāma …";
  input.setAttribute("aria-label",
    "Dictionary search: grammar analysis and Monier-Williams entries");
  input.autocomplete = "off";
  input.spellcheck = false;
  drawer.appendChild(input);

  hint = el("p", "lex-beta-hint");
  hint.setAttribute("aria-live", "polite");
  drawer.appendChild(hint);

  results = el("div", "lex-results");
  drawer.appendChild(results);

  input.addEventListener("input", () => void runSearch());
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      focusResult(0);
    } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      moveFocus(e.key === "ArrowDown" ? 1 : -1);
    }
  });
  document.body.appendChild(drawer);
  return drawer;
}

export function openLexicon(prefill?: string): void {
  const d = ensureDrawer();
  d.classList.remove("hidden");
  document.body.classList.add("lexicon-open");
  if (prefill && input) {
    // prefills arrive as lemma headwords (Devanagari or IAST) — show them
    // as-is; runSearch detects the script either way.
    input.value = prefill;
  }
  if (input) {
    void runSearch();
    input.focus();
    input.select();
  }
}

export function closeLexicon(): void {
  drawer?.classList.add("hidden");
  document.body.classList.remove("lexicon-open");
}

export function toggleLexicon(): void {
  if (!drawer || drawer.classList.contains("hidden")) openLexicon();
  else closeLexicon();
}

// Close on Escape
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && drawer && !drawer.classList.contains("hidden")) {
    closeLexicon();
  }
});

export function lexiconButton(label = "Lexicon"): El {
  const b = el("button", undefined, label) as HTMLButtonElement;
  b.type = "button";
  b.addEventListener("click", () => toggleLexicon());
  return b;
}

/* ---------------- lookups ---------------- */

const MAX_PARSES = 12;
const MAX_MW = 20;

/** MW entries for a query in either script: exact shard key + sibilant
 *  variants first, then headwords beginning with the key (prefix scan,
 *  capped). Misses return []. */
async function mwEntries(q: string): Promise<MwEntry[]> {
  const key = slp1KeyFor(q);
  if (!key || key.length < 2) return [];
  const letter = key[0]!;
  if (!/^[a-z]$/.test(letter)) return [];
  const shard = await fetchJSON<Record<string, { u?: string; g?: string }>>(
    `data/gloss/${letter}.json`,
  ).catch(() => null);
  if (!shard) return [];
  const out: MwEntry[] = [];
  const seen = new Set<string>();
  for (const base of [key, ...slp1KeyVariants(key)]) {
    const k = base.toLowerCase();
    if (seen.has(k)) continue;
    seen.add(k);
    const hit = shard[k];
    if (hit && (hit.u || hit.g)) out.push({ u: hit.u ?? k, g: hit.g ?? "" });
  }
  for (const k of Object.keys(shard)
    .filter((k) => k.startsWith(key) && !seen.has(k))
    .sort()
    .slice(0, MAX_MW)) {
    const hit = shard[k]!;
    out.push({ u: hit.u ?? k, g: hit.g ?? "" });
  }
  return out.slice(0, MAX_MW);
}

/** Drop byte-identical duplicate analyses (DCS ships several). */
function dedupe(parses: Parse[]): Parse[] {
  const seen = new Set<string>();
  return parses.filter((p) => {
    const k = `${p.l}|${p.p}|${p.f}|${p.x}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

/** One parse card (mirrors the reader's best-parse card). */
function parseCard(p: Parse): El {
  const card = el("div", "pcard lex-card");
  const head = el("div", "cand-head");
  head.appendChild(lemmaDualEl(p.l || "?"));
  card.appendChild(head);
  // compact abbr inflection (R2); x-extras muted beneath
  card.appendChild(compactFeatsEl(p.p, p.f));
  const extras = parseDcsFeats(p.f ?? "").extras
    .concat((p.x ?? "").split(/[|\s]+/).filter(Boolean));
  if (extras.length) {
    card.appendChild(el("div", "feats feat-extras", extras.join(" · ")));
  }
  attachMwGloss(card, p.l ?? "");
  return card;
}

/** One MW entry card: dual-script headword + English gloss. */
function mwCard(e: MwEntry): El {
  const card = el("div", "entry lex-card lex-mw");
  card.appendChild(el("span", "lex-src", "MW"));
  const head = el("div", "cand-head");
  head.appendChild(lemmaDualEl(e.u));
  card.appendChild(head);
  if (e.g) card.appendChild(el("div", "dict-gloss", e.g));
  return card;
}

async function runSearch(): Promise<void> {
  ensureDrawer();
  const raw = input?.value ?? "";
  const q = raw.trim();
  const seq = ++searchSeq;
  results!.replaceChildren();
  hint!.replaceChildren();

  if (!q) {
    results!.appendChild(
      el("p", "lex-hint-empty",
        "Type a Sanskrit or Pali word — Devanagari (राम) or IAST (rāma)."),
    );
    return;
  }

  // Both scripts accepted: normalize to Devanagari for the morphology
  // surface index; keep an IAST echo under the input.
  const deva = isDevanagari(q) ? q : iastToDev(q);
  const iast = isDevanagari(q) ? devToIast(q) : stripAccents(q);
  hint!.appendChild(featTagEl(deva));

  const mySeq = seq;
  const [morphMap, mw] = await Promise.all([
    loadMorph([deva]).catch(() => new Map<string, Parse[]>()),
    mwEntries(q),
  ]);
  if (mySeq !== searchSeq || !results!.isConnected) return; // stale keystroke

  let shown = 0;
  const parses = dedupe(morphMap.get(deva) ?? []);
  if (parses.length) {
    results!.appendChild(el("h3", "wl-head",
      `解析 Grammar · ${parses.length}`));
    for (const p of parses.slice(0, MAX_PARSES)) {
      results!.appendChild(parseCard(p));
      shown += 1;
    }
  }
  if (mw.length) {
    results!.appendChild(el("h3", "wl-head", "Monier-Williams"));
    for (const e of mw) {
      results!.appendChild(mwCard(e));
      shown += 1;
      if (shown >= 40) break;
    }
  }
  if (!shown) {
    results!.appendChild(
      el("p", "lex-hint-empty",
        `No matches for “${q}” — try another spelling (${iast}).`),
    );
  }
}

/* ---------------- keyboard navigation ---------------- */

function resultCards(): HTMLElement[] {
  return Array.from(
    results?.querySelectorAll<HTMLElement>(".lex-card") ?? [],
  );
}

function focusResult(i: number): void {
  const cards = resultCards();
  cards[i]?.focus();
}

function moveFocus(delta: number): void {
  const cards = resultCards();
  const cur = cards.indexOf(document.activeElement as HTMLElement);
  const next = cur < 0 ? 0 : Math.min(cards.length - 1,
    Math.max(0, cur + delta));
  cards[next]?.focus();
}
