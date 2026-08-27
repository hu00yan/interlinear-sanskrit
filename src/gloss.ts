// One display model for a parsed reading. It deliberately accepts only source
// glosses and exact dictionary headword matches; ranking remains elsewhere.
import { stripAccents, type Parse } from "./api";
import { slp1KeyFor } from "./translit";

export const COMPACT_GLOSS_MAX_CHARS = 90;

export interface GlossEntry { u?: string; g?: string }
export type GlossEntries = ReadonlyMap<string, GlossEntry | undefined>;

export interface ParseViewModel {
  lemma: string;
  features: string;
  compactGloss?: string;
  isProperName: boolean;
}

function sourceGloss(p: Parse, entries?: GlossEntries): string | undefined {
  if (compactGloss(p.g ?? "")) return p.g;
  if (!entries) return undefined;
  const exact = entries.get(p.l) ?? entries.get(stripAccents(p.l));
  if (exact?.g) return exact.g;
  // Maps from an API cache are normally keyed by stripped lemma. This final
  // comparison covers callers that retain a headword-keyed cache, still exact.
  const key = slp1KeyFor(p.l);
  if (!key) return undefined;
  for (const entry of entries.values()) {
    if (entry?.g && entry.u && slp1KeyFor(entry.u) === key) return entry.g;
  }
  return undefined;
}

/** Verified signals only: POS/features declare a name, or MW leads with one. */
export function isProperNameParse(p: Parse, gloss?: string): boolean {
  if (/^(?:propn|proper|name)$/i.test((p.p ?? "").trim())) return true;
  if (/(?:^|[;|\s])(?:PROPN|Proper(?:Name)?|Name)(?:$|[;|\s])/i.test(p.f ?? "")) return true;
  return /^\s*(?:as,\s*)?(?:[mfn]\.?\s*)?(?:N|Name)\.\s*of\b/i.test(
    (gloss ?? "").replace(/\s+/g, " ").slice(0, 60),
  );
}

/** Convert scholarly MW text into one short reader-facing English sense. */
export function compactGloss(txt: string, max = COMPACT_GLOSS_MAX_CHARS): string | null {
  let text = (txt ?? "")
    .replace(/<[^>]*>|\[[^\]]*\]/g, " ")
    .replace(/[\u0900-\u097f\u3400-\u9fff]/g, " ")
    .replace(/\b(?:m|f|n|mf|ind|pron|nom|acc|dat|abl|gen|loc|voc|sg|du|pl|cf|see)\.?\b/gi, " ")
    .replace(/\b(?:RV|AV|VS|TS|ŚBr|ŚB|MBh|R|Pāṇ(?:ini)?)\.?\s*[\d.,;:()\-–—]*/gi, " ")
    .replace(/\b(?:q\.v\.|s\.v\.|and\s+so\s+on)\b[^.;]*/gi, " ")
    .replace(/^[\s,;:()\-–—.]+/, " ").replace(/\s+/g, " ").trim();
  text = text.split(/[;.](?=\s|$)/)[0]?.trim() ?? "";
  text = text.replace(/^[^A-Za-z]*|[^A-Za-z)\- ]*$/g, "").trim();
  if (!/[A-Za-z]{2}/.test(text)) return null;
  if (text.length <= max) return text;
  const cut = text.slice(0, max - 1).lastIndexOf(" ");
  return `${text.slice(0, cut > max / 2 ? cut : max - 1)}…`;
}

/** Pure parse presentation model shared by all gloss-owning surfaces. */
export function parseViewModel(p: Parse, entries?: GlossEntries): ParseViewModel {
  const raw = sourceGloss(p, entries);
  const compact = raw ? compactGloss(raw) ?? undefined : undefined;
  return {
    lemma: p.l ?? "",
    features: p.f ?? "",
    compactGloss: compact,
    isProperName: isProperNameParse(p, raw),
  };
}

export function glossIdentity(txt: string): string {
  return (compactGloss(txt) ?? "").toLowerCase();
}
