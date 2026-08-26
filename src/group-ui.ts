// Group-row DOM builders shared by every parse surface (reader columns,
// word-click panel, home lookup box): one (lemma × POS-class) group renders
// as `lemma abbr-feat-summary`, with compact SET notation when the group
// holds many attested combos ("m./n., sg./du./pl., various cases").
// textContent-only element construction — never innerHTML.
import { compactFeatsEl, compactTagNode, lemmaDualEl } from "./feats";
import { groupSummaryAbbrs, type ParseGroup } from "./group";

type El = HTMLElement;

/** POS label of a group (compact abbr of its class). */
export function posLabelOf(g: ParseGroup): string {
  switch (g.cls) {
    case "noun": return "n.";
    case "verb": return "v.";
    case "part": return "ptcp.";
    case "indecl": return "indecl.";
    default: return "";
  }
}

/**
 * The `.cand-head` of one group row: dual-script lemma + feature summary.
 * Single-analysis groups keep the classic per-parse dual-script tags
 * (IAST over Devanagari); multi-member groups use the synthesized
 * compact-set summary (no Devanagari original exists for joins).
 */
export function groupHeadEl(g: ParseGroup): El {
  const head = document.createElement("div");
  head.className = "cand-head";
  const lemma = (g.lemma || "").replace(/^(.*\D)\d+$/, "$1");
  head.appendChild(lemmaDualEl(lemma || "?"));
  if (g.members.length === 1) {
    // single analysis: full dual-script fidelity of the classic card
    head.appendChild(compactFeatsEl(g.members[0]!.p, g.members[0]!.f));
  } else {
    const d = document.createElement("div");
    d.className = "feats";
    const pos = posLabelOf(g);
    if (pos) d.appendChild(compactTagNode({ ab: pos }));
    for (const ab of groupSummaryAbbrs(g)) {
      if (d.childNodes.length) d.appendChild(document.createTextNode(" "));
      d.appendChild(compactTagNode({ ab }));
    }
    head.appendChild(d);
  }
  return head;
}
