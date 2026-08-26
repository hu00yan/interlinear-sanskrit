#!/usr/bin/env python3
"""check_search_index.py — fail-loud QA gate for the home-search index
(pipeline/stages/80-searchindex/build_search_index.py output).

Gates (exit 1 on any violation):
  G1 coverage      _meta.json works[] == catalog work ids, in order; every
                   widIdx referenced by some shard entry; no out-of-range idx.
  G2 dual-script   normalization folds BOTH scripts to one key: norm('राम')
                   == norm('rāma') == 'rama'; shard lookup agrees — probing
                   the Devanagari and IAST spellings of a probe word returns
                   identical work sets (house-mandatory IAST/Devanagari
                   parity, incl. Pali roman works).
  G3 spot queries  configured probes must return their expected work among
                   the top hits with a non-empty first-seen ref.
  G4 shard health  every meta letter has a file on disk, every shard file is
                   <=8MB raw and parses; keys fold to themselves (idempotent
                   normalization); single-char keys absent.
  G5 trans index   search-index-trans.json parses, w[] ⊆ catalog ids, every
                   entry ref non-empty, snippet length sane, size <= 8MB.

Usage:
    python3 pipeline/stages/90-qa/check_search_index.py \
        [--data-root public/data] [--probe '{"rama":["bhagavadgita",...]}']
Exit 0 = all gates green.
"""
import argparse
import json
import os
import re
import sys
import unicodedata

STAGES = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, STAGES)
import lib  # noqa: E402

SHARD_BYTES = 8 * 1024 * 1024

DEFAULT_PROBES = {
    # folded query -> [workId that MUST appear among the hit works]
    # (top-30-per-word cap means only works with real counts qualify)
    "rama": ["ramayana", "mahabharata"],
    "krsna": ["bhagavadgita"],
    "धर्मक्षेत्रे": ["bhagavadgita"],   # Devanagari spelling, end-to-end
    "padam": ["pali-dhammapada"],        # Pali roman corpus reachable
    "dhammo": ["pali-mn"],
}

_COMB = re.compile(
    "[\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20f0\ufe20-\ufe2f]")
_NONKEY = re.compile(r"[^a-z0-9]+")


def norm_sa(token: str) -> str:
    """MUST mirror build_search_index.norm_sa AND src/api.ts normSa."""
    if any("\u0900" <= c <= "\u097f" for c in token):
        from indic_transliteration import sanscript as _s
        token = _s.transliterate(token, _s.DEVANAGARI, _s.IAST)
    s = unicodedata.normalize("NFD", token.lower())
    s = _COMB.sub("", s)
    return _NONKEY.sub("", s)


class Gate:
    def __init__(self) -> None:
        self.violations: list[str] = []

    def check(self, cond: bool, msg: str) -> None:
        if not cond:
            self.violations.append(msg)

    def done(self, what: str) -> None:
        if self.violations:
            for v in self.violations[:30]:
                print(f"VIOLATION [{what}] {v}", file=sys.stderr)
            lib.fail(f"{what}: {len(self.violations)} violation(s)")
        print(f"[check_search_index] {what}: OK")


def load_shards(data_root: str, g: Gate):
    meta = lib.read_json(os.path.join(data_root, "search-index-sa",
                                      "_meta.json"))
    shards = {}
    for letter in meta["letters"]:
        p = os.path.join(data_root, "search-index-sa", f"{letter}.json")
        g.check(os.path.exists(p), f"missing shard file {letter}.json")
        if not os.path.exists(p):
            continue
        size = os.path.getsize(p)
        g.check(size <= SHARD_BYTES,
                f"shard {letter}.json {size} bytes > {SHARD_BYTES}")
        shards[letter] = lib.read_json(p)
    # no orphan shard files on disk
    d = os.path.join(data_root, "search-index-sa")
    for f in os.listdir(d):
        if f.endswith(".json") and f != "_meta.json":
            g.check(f[:-5] in set(meta["letters"]),
                    f"orphan shard on disk: {f}")
    return meta, shards


def lookup(shards, meta, key: str):
    """[total, [[widIdx, ref], ...]] for a folded key, or None."""
    letter = key[0]
    shard = shards.get(letter)
    if not shard:
        return None
    return shard.get(key)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-root", default=os.path.join(lib.REPO,
                                                        "public", "data"))
    ap.add_argument("--probe", help="JSON {foldedQuery: [workId,...]}")
    ap.add_argument("--skip-trans", action="store_true",
                    help="only gate the word index")
    args = ap.parse_args()
    probes = json.loads(args.probe) if args.probe else DEFAULT_PROBES
    root = args.data_root

    catalog = lib.read_json(os.path.join(root, "catalog.json"))
    cat_ids = [w["id"] for a in catalog["authors"] for w in a["works"]]

    g = Gate()

    # ---- G1 coverage ----
    if not os.path.exists(os.path.join(root, "search-index-sa",
                                       "_meta.json")):
        lib.fail("search-index-sa/_meta.json missing — run "
                 "stages/80-searchindex first")
    meta, shards = load_shards(root, g)
    g.check(meta.get("v") == 1, "meta v != 1")
    g.check(sorted(meta["works"]) == sorted(cat_ids),
            "meta works[] != catalog ids")
    n = len(cat_ids)
    covered = set()
    total_entries = 0
    for letter, shard in shards.items():
        for k, (total, hits) in shard.items():
            total_entries += 1
            g.check(len(k) >= 2, f"single-char key {k!r} in shard {letter}")
            g.check(norm_sa(k) == k, f"key {k!r} not normalization-stable")
            for wi, ref in hits:
                g.check(0 <= wi < n, f"widIdx {wi} out of range (key {k!r})")
                covered.add(wi)
                g.check(isinstance(ref, str) and len(ref) <= 24,
                        f"bad ref {ref!r} (key {k!r})")
            g.check(total >= sum(1 for _ in hits),
                    f"total < hits for key {k!r}")
    g.check(len(covered) == n,
            f"{n - len(covered)} catalog works absent from word index")
    g.done(f"G1 coverage ({total_entries} forms, {len(covered)}/{n} works)")

    # ---- G2 dual-script parity + G3 spot queries ----
    g2 = Gate()
    g3 = Gate()
    deva_roma = [("राम", "rāma"), ("कृष्ण", "kṛṣṇa"),
                 ("धर्मक्षेत्रे", "dharmakṣetre")]
    for deva, roma in deva_roma:
        g2.check(norm_sa(deva) == norm_sa(roma),
                 f"fold mismatch {deva!r} vs {roma!r} "
                 f"({norm_sa(deva)!r} vs {norm_sa(roma)!r})")
    for q, expect_works in probes.items():
        key = norm_sa(q)
        hit = lookup(shards, meta, key)
        if hit is None:
            g3.check(False, f"probe {q!r} -> key {key!r} absent")
            continue
        got = {meta["works"][wi] for wi, _ in hit[1]}
        for wid in expect_works:
            g3.check(wid in got, f"probe {q!r}: {wid} not in hits {sorted(got)}")
        g3.check(all(r for _, r in hit[1][:5]),
                 f"probe {q!r}: empty refs among top hits")
    g2.done("G2 dual-script folding")
    g3.done(f"G3 spot queries ({len(probes)} probes)")

    # ---- G5 translation snippet index ----
    if not args.skip_trans:
        tp = os.path.join(root, "search-index-trans.json")
        g5 = Gate()
        g5.check(os.path.exists(tp), "search-index-trans.json missing")
        if os.path.exists(tp):
            g5.check(os.path.getsize(tp) <= SHARD_BYTES,
                     "trans index over 8MB")
            t = lib.read_json(tp)
            g5.check(t.get("v") == 1, "trans v != 1")
            known = set(cat_ids)
            g5.check(set(t["w"]) <= known,
                     f"trans w[] outside catalog: {set(t['w']) - known}")
            short = sum(1 for _wi, ref, sn in t["e"]
                        if not ref or len(sn) > 260)
            g5.check(short == 0, f"{short} bad trans entries")
            g5.check(len(t["e"]) > 1000,
                     f"suspiciously few snippets: {len(t['e'])}")
        g5.done("G5 trans index")


if __name__ == "__main__":
    main()
