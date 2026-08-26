#!/usr/bin/env python3
"""pali_dpd.py — stage 50-analyze Pali lane: build public/data/morph-pali/**
from the Digital Pāḷi Dictionary (dpd-db release v0.4.20260728).

Source (verified in qa-report/pali-morph-sources.md Lead 2):
  .cache-dpd/dpd.db                    SQLite export (~169MB tar.xz)
    - dpd_headwords: lemma_1, pos, grammar, stem, pattern, meaning_1 …
    - lookup:        reverse index, any inflected form -> headword ids
  .cache-dpd/deconstructor_output.json surface sandhi form -> ranked splits

Pass A scope (this round): FLAT inflections only. Every lookup hit emits
{lemma, POS-map, coarse feats, English gloss}; NO template expansion, so
nominal case/number and verbal tense/person stay UNRESOLVED (feats carry
the headword's gender only). Compound fallback uses deconstructor_output
EXACT-FULL-FORM matches whose every member independently hits lookup;
candidates failing that are dropped (explicit misses stay absent/null —
no guessing, per FST-PORT-CONTRACT.md honesty rule).

Key normalization (mirrors pipeline/sanscript.slp1_key + house convention,
cf. build_morph_dcs._canonical_keys):
  * niggahīta fold: our bilara texts write ṁ (U+1E41), DPD writes ṃ
    (U+1E43) -> BOTH fold to ṃ before keying, then lowercase-SLP1, so
    "cakkaṁva"(ours) and "cakkaṃva"(DPD) meet at one shard key "cakkamva".
  * punctuation attached to corpus tokens ("bhāsati,", "padaṁ.") is
    dropped from KEYS but kept verbatim in _surface slice keys.
  * long/short vowels collide exactly as on the Sanskrit shards
    (slp1_key lowercases capitals: dhammā ≡ damma ≡ dhamma).

Outputs (schema mirrors public/data/morph/**; additive "_provenance"
top-level block on every file — never collides: shard keys are [a-z~]+):
  morph-pali/<letter>.json            {"_provenance":…, "<key>":[analyses]}
    analysis = {l lemma, p POS∈noun/verb/part/indecl, f feats, x stem,
                g gloss}          (+ m:[{d,l,p,f}] member chains for
                                   deconstructor compounds, as on /morph/)
  morph-pali/_surface/<letter>.json   {displayToken(incl punct): shardKey}
  morph-pali/_surface/by-work/<id>.json  per catalog work id (primary slice)

Usage:
  python3 pipeline/stages/50-analyze/pali_dpd.py \
      [--cache .cache-dpd] [--out-root public/data] [--data-root public/data]
      [--report qa-report/logs/pali-dpd-build.json]

License: DPB data AND derived shards are CC BY-NC-SA 4.0 (BY attribute +
NC non-commercial + SA share-alike). Every emitted artifact carries the
provenance block; site display must attribute DPD (see
qa-report/pali-dpd-ingest.md).
"""
import argparse
import glob
import json
import os
import re
import sqlite3
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, "pipeline"))
import sanscript  # noqa: E402  (indic_transliteration build-time dep)

PROVENANCE = {
    "source": "dpd",
    "upstream": "digitalpalidictionary/dpd-db v0.4.20260728",
    "license": "CC BY-NC-SA 4.0",
    "attribution": "Digital P\u0101li Dictionary (https://dpd.hh.sutanu.dev)",
}

MAX_ANALYSES_PER_KEY = 16
MAX_COMPOUND_CANDIDATES = 3
GLOSS_MAX = 200

# --- key normalization -----------------------------------------------------

# corpus-side niggahīta ṁ (U+1E41) -> DPD-side ṃ (U+1E43); documented choice
_NIGGAHITA = {"\u1e41": "\u1e43"}
_LETTERISH = re.compile(r"[A-Za-zĀ-ž\u1e00-\u1eff]")


def fold_niggahita(text: str) -> str:
    return "".join(_NIGGAHITA.get(c, c) for c in text)


def word_core(token: str) -> str:
    """Letter-only core of a corpus token (drops , ; : . “ ” etc.)."""
    return "".join(c for c in fold_niggahita(token.lower())
                   if _LETTERISH.match(c))


def canon_key(token: str) -> str:
    """Shard key: niggahīta-folded, punctuation-free, lowercase-SLP1."""
    core = word_core(token)
    if not core:
        return ""
    k = sanscript.slp1_key(core)
    return k if re.fullmatch(r"[a-z~]+", k) else ""


def lookup_key_of(dpd_form: str) -> str:
    """Normalize a DPD-side form onto the same key space."""
    return canon_key(dpd_form)


# --- POS mapping (house vocab: noun | verb | part | indecl, cf.
#     build_morph_dcs.map_pos) ------------------------------------------------

POS_NOUNISH = {"adj", "masc", "fem", "neut", "ntp", "num", "ord"}
POS_VERBISH = {"verb", "dut", "caus", "fact", "irr"}
POS_PARTISH = {"pp", "prp", "pron"}       # participles/pronouns -> "part"
POS_INDECLISH = {"ind", "idi", "neg", "cs", "epu", "sandhi", "suffix",
                 "pt", "avy", "conj", "interj", "abbrev"}
POS_MAP_EXTRA = {"inf": "verb", "root": "part"}


def map_pos(dpd_pos: str) -> str:
    p = (dpd_pos or "").strip().lower()
    if p in POS_NOUNISH:
        return "noun"
    if p in POS_VERBISH or p == "inf":
        return "verb"
    if p in POS_PARTISH or p == "root":
        return "part"
    if p in POS_INDECLISH:
        return "indecl"
    # verbs hide behind unknown tags less often than nouns; default keeps
    # every analysis renderable without inventing a POS
    return "part"


_GENDER_TAGS = [("masc", "m."), ("fem", "f."), ("neut", "n."),
                ("mf", "m.f."), ("nt", "n.")]


def feats_from_grammar(grammar: str, pos: str) -> str:
    """Pass A coarse feats: gender tags only (case/number/tense need the
    inflection_templates expansion = Pass B, deliberately skipped)."""
    g = (grammar or "").lower()
    tags = []
    for needle, abbr in (("masc", "m."), ("fem", "f."), ("neut", "n.")):
        if needle in g:
            tags.append(abbr)
    if not tags and "nt" in g.split():
        tags.append("n.")
    return ";".join(tags)


_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_MD_BOLD = re.compile(r"\*\*?")
_HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")


def clean_gloss(meaning: str) -> str:
    if not meaning:
        return ""
    s = _MD_LINK.sub(r"\1", meaning)
    s = _MD_BOLD.sub("", s)
    s = _HTML_TAG.sub("", s)
    s = s.replace("\u2714", "").replace("`", "")
    s = re.sub(r"\s+", " ", s).strip(" ;,")
    return s[:GLOSS_MAX].rstrip() + ("\u2026" if len(s) > GLOSS_MAX else "")


# --- inputs ----------------------------------------------------------------


def pali_works(data_root: str):
    """[(work_id, [text paths])] for author key 'pali-canon'."""
    cat = json.load(open(os.path.join(data_root, "catalog.json"),
                         encoding="utf-8"))
    out = []
    for author in cat["authors"]:
        if author.get("key") != "pali-canon":
            continue
        for w in author["works"]:
            out.append((w["id"], [os.path.join(data_root, f)
                                  for f in w["files"]]))
    return out


def collect_tokens(works):
    """({work_id: [raw tokens]}, {distinct raw token}) order-preserving."""
    by_work, distinct = {}, {}
    for wid, paths in works:
        toks = []
        for path in paths:
            doc = json.load(open(path, encoding="utf-8"))
            units = doc.get("units", []) if isinstance(doc, dict) else doc
            for u in units:
                toks.extend(u.get("words", []) or [])
        by_work[wid] = toks
        for t in toks:
            distinct.setdefault(t, None)
    return by_work, list(distinct.keys())


class DpdDb:
    def __init__(self, cache_dir: str):
        self.db_path = os.path.join(cache_dir, "dpd.db")
        if not os.path.exists(self.db_path):
            sys.exit(f"FATAL [pali_dpd] missing {self.db_path} — download "
                     f"dpd.db.tar.xz (release v0.4.20260728) into "
                     f"{cache_dir}/ and extract (see module docstring)")
        con = sqlite3.connect(f"file:{self.db_path}?mode=ro&immutable=1",
                              uri=True)
        self.con = con
        self._schema_check()

    def _schema_check(self):
        tables = {r[0] for r in self.con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        for need in ("dpd_headwords", "lookup"):
            if need not in tables:
                sys.exit(f"FATAL [pali_dpd] dpd.db lacks table {need!r}; "
                         f"tables={sorted(tables)}")
        cols = {r[1] for r in self.con.execute(
            "PRAGMA table_info(dpd_headwords)")}
        self.col_lemma = ("lemma_1" if "lemma_1" in cols
                          else "lemma" if "lemma" in cols else None)
        self.col_meaning = ("meaning_1" if "meaning_1" in cols
                            else "meaning" if "meaning" in cols
                            else "meaning_lit" if "meaning_lit" in cols
                            else None)
        for need in (self.col_lemma, "pos"):
            if need and need not in cols:
                sys.exit(f"FATAL [pali_dpd] dpd_headwords lacks column "
                         f"{need!r}: {sorted(cols)}")
        n_hw = self.con.execute(
            "SELECT count(*) FROM dpd_headwords").fetchone()[0]
        n_lk = self.con.execute("SELECT count(*) FROM lookup").fetchone()[0]
        print(f"[pali_dpd] dpd.db ok: dpd_headwords={n_hw} rows, "
              f"lookup={n_lk} rows")

    def scan_lookup(self, needed_norm: set) -> dict:
        """One pass over `lookup`: normalized form-key -> ordered headword
        ids. Scanning (instead of per-form IN queries) catches every DPD
        spelling that folds onto a corpus key, incl. ṃ/ṁ variants."""
        wanted = {}
        out = {}
        q = "SELECT lookup_key, headwords FROM lookup"
        for lk, hw_json in self.con.execute(q):
            nk = lookup_key_of(lk or "")
            if nk not in needed_norm:
                continue
            try:
                ids = json.loads(hw_json) if hw_json else []
            except (ValueError, TypeError):
                ids = []
            ids = [i for i in ids if isinstance(i, int)]
            if not ids:
                continue
            cur = out.setdefault(nk, [])
            seen = set(cur)
            for i in ids:
                if i not in seen:
                    cur.append(i)
                    seen.add(i)
            wanted[nk] = True
        del wanted
        return out

    def headwords(self, ids) -> dict:
        """id -> row tuple (lemma, pos, grammar, stem, meaning)."""
        sel = ", ".join([self.col_lemma, "pos", "grammar", "stem",
                         self.col_meaning])
        out = {}
        ids = list(ids)
        for i in range(0, len(ids), 400):
            chunk = ids[i:i + 400]
            marks = ",".join("?" * len(chunk))
            q = (f"SELECT id, {sel} FROM dpd_headwords "
                 f"WHERE id IN ({marks})")
            for row in self.con.execute(q, chunk):
                out[row[0]] = row[1:]
        return out


def load_deconstructor(cache_dir: str, needed_norm: set) -> dict:
    """Exact-full-form sandhi candidates for unresolved tokens only.
    Returns normkey -> ranked ["a + b", …] (first MAX_COMPOUND_CANDIDATES)."""
    path = os.path.join(cache_dir, "deconstructor_output.json")
    if not os.path.exists(path):
        alt = sorted(glob.glob(os.path.join(cache_dir, "*deconstructor*")))
        if not alt:
            return {}
        path = alt[0]
    print(f"[pali_dpd] loading deconstructor {os.path.basename(path)} "
          f"(one-shot, memory-heavy)")
    with open(path, encoding="utf-8") as fh:
        whole = json.load(fh)
    out = {}
    for form, splits in whole.items():
        nk = lookup_key_of(form)
        if nk in needed_norm and isinstance(splits, list):
            keep = [s for s in splits[:MAX_COMPOUND_CANDIDATES]
                    if isinstance(s, str)]
            if keep:
                out[nk] = keep
    del whole
    return out


def analyses_for(ids, hw) -> list:
    """Build deduped {l,p,f,x,g} analyses for one form's headword ids."""
    out, seen = [], set()
    for i in ids:
        row = hw.get(i)
        if row is None:
            continue
        lemma, pos, grammar, stem, meaning = row
        lemma = (lemma or "").strip()
        if not lemma:
            continue
        p = map_pos(pos)
        a = {"l": lemma, "p": p,
             "f": feats_from_grammar(grammar or "", p),
             "x": (stem or "").strip()}
        g = clean_gloss(meaning or "")
        if g:
            a["g"] = g
        tup = json.dumps(a, ensure_ascii=False, sort_keys=True)
        if tup not in seen:
            seen.add(tup)
            out.append(a)
        if len(out) >= MAX_ANALYSES_PER_KEY:
            break
    return out


def split_parts(candidate: str) -> list:
    """"akāsi + amhā" -> ["akāsi", "amhā"]; None when shape unexpected."""
    cand = candidate.replace("−", "+")  # some outputs mark joins oddly
    parts = [p.strip() for p in cand.split("+")]
    parts = [p for p in parts if p]
    if len(parts) < 2 or not all(_LETTERISH.match(c) for p in parts
                                 for c in p):
        return None
    return parts


# --- emission ---------------------------------------------------------------


def _write_json(path: str, obj) -> int:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    blob = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(blob)
    return len(blob.encode("utf-8"))


def _with_prov(obj: dict) -> dict:
    out = {"_provenance": PROVENANCE}
    out.update(obj)
    return out


def emit(shards: dict, surface: dict, surface_by_work: dict,
         out_root: str) -> dict:
    """Write morph-pali/** deterministically; returns byte counts."""
    base = os.path.join(out_root, "morph-pali")
    surf = os.path.join(base, "_surface")
    sizes = {"shards": 0, "surface": 0, "by_work": 0}
    letters = {}
    for key, analyses in shards.items():
        letters.setdefault(key[0], {})[key] = analyses
    for letter in sorted(letters):
        fp = os.path.join(base, f"{letter}.json")
        sizes["shards"] += _write_json(fp, _with_prov(letters[letter]))
    buckets = {}
    for tok, key in surface.items():
        initial = next((c for c in tok.lower() if "a" <= c <= "z"), None)
        if initial:
            buckets.setdefault(initial, {})[tok] = key
    for name in sorted(buckets):
        fp = os.path.join(surf, f"{name}.json")
        sizes["surface"] += _write_json(fp, _with_prov(buckets[name]))
    for wid in sorted(surface_by_work):
        fp = os.path.join(surf, "by-work", f"{wid}.json")
        sizes["by_work"] += _write_json(fp,
                                        _with_prov(surface_by_work[wid]))
    return sizes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cache", default=os.path.join(REPO, ".cache-dpd"))
    ap.add_argument("--out-root", default=os.path.join(REPO, "public",
                                                       "data"))
    ap.add_argument("--data-root", default=None,
                    help="catalog/texts root (default: --out-root)")
    ap.add_argument("--report",
                    default=os.path.join(REPO, "qa-report", "logs",
                                         "pali-dpd-build.json"))
    args = ap.parse_args()
    data_root = args.data_root or args.out_root

    works = pali_works(data_root)
    by_work, distinct = collect_tokens(works)
    print(f"[pali_dpd] {len(works)} works, {sum(len(v) for v in by_work.values())} "
          f"tokens, {len(distinct)} distinct")

    db = DpdDb(args.cache)

    # pass 1: resolve flat inflections via the lookup reverse index
    tok_keys = {}           # raw token -> canonical key ("" when unusable)
    keys_needed = set()
    for t in distinct:
        k = canon_key(t)
        tok_keys[t] = k
        if k:
            keys_needed.add(k)
    lookup_hits = db.scan_lookup(keys_needed)
    print(f"[pali_dpd] lookup: {len(lookup_hits)}/{len(keys_needed)} "
          f"distinct keys resolved")

    used_ids = set()
    for ids in lookup_hits.values():
        used_ids.update(ids)
    hw = db.headwords(used_ids) if used_ids else {}
    print(f"[pali_dpd] headwords fetched: {len(hw)}/{len(used_ids)}")

    shards = {}             # key -> analyses[]
    resolved = {}           # raw token -> bool
    for t, k in tok_keys.items():
        ids = lookup_hits.get(k)
        if ids:
            a = analyses_for(ids, hw)
            if a:
                shards.setdefault(k, a)
                resolved[t] = True
                continue
        resolved[t] = False

    # pass 2: compound fallback — EXACT full-form deconstructor matches only
    unresolved = {tok_keys[t] for t, ok in resolved.items()
                  if not ok and tok_keys[t]}
    print(f"[pali_dpd] unresolved distinct forms: {len(unresolved)}"
          f" -> deconstructor fallback")
    decon = load_deconstructor(args.cache, unresolved) if unresolved else {}
    compound_hits = 0
    for t, ok in sorted(resolved.items()):
        if ok:
            continue
        k = tok_keys[t]
        for cand in decon.get(k, []):
            parts = split_parts(cand)
            if not parts:
                continue
            chains = []
            members_ok = True
            for part in parts:
                pk = lookup_key_of(part)
                ids = lookup_hits.get(pk)
                a = analyses_for(ids, hw)[:1] if ids else []
                if not a:
                    members_ok = False
                    break
                chains.append((part, a[0]))
            if not members_ok:
                continue     # honesty: partial splits are NOT emitted
            head_l, head_a = chains[-1]
            entry = dict(head_a)
            entry["m"] = [{"d": part, "l": a["l"], "p": a["p"],
                           "f": a["f"]} for part, a in chains]
            shards.setdefault(k, []).append(entry)
            compound_hits += 1
            break            # first fully-resolved candidate wins
    print(f"[pali_dpd] compound fallback resolved {compound_hits} more "
          f"forms")

    # pass 3: emit shards + surface slices
    surface = {t: tok_keys[t] for t in distinct
               if resolved.get(t) and tok_keys[t]}
    surface_by_work = {}
    for wid, toks in by_work.items():
        sub = {t: surface[t] for t in toks if t in surface}
        if sub:
            surface_by_work[wid] = sub
    sizes = emit(shards, surface, surface_by_work, args.out_root)
    total_mb = sum(sizes.values()) / 2**20
    print(f"[pali_dpd] wrote morph-pali: {total_mb:.1f} MB "
          f"(shards={sizes['shards']/2**20:.1f}"
          f" surface={sizes['surface']/2**20:.1f}"
          f" by-work={sizes['by_work']/2**20:.1f})")

    # coverage report (token-weighted, per work)
    report = {"provenance": PROVENANCE, "works": {}, "totals": {}}
    tot_tok = hit_tok = 0
    for wid, toks in by_work.items():
        hits = sum(1 for t in toks if resolved.get(t))
        tot_tok += len(toks)
        hit_tok += hits
        report["works"][wid] = {
            "tokens": len(toks), "hit_tokens": hits,
            "coverage_pct": round(100.0 * hits / len(toks), 1)
            if toks else 0.0,
        }
    report["totals"] = {
        "works": len(by_work), "tokens": tot_tok, "hit_tokens": hit_tok,
        "coverage_pct": round(100.0 * hit_tok / max(tot_tok, 1), 1),
        "distinct_forms": len(distinct),
        "resolved_distinct": sum(1 for t in distinct if resolved.get(t)),
        "shard_bytes": sum(sizes.values()),
    }
    if args.report:
        os.makedirs(os.path.dirname(args.report), exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1)
        print(f"[pali_dpd] report -> {args.report}")
    t = report["totals"]
    print(f"[pali_dpd] TOKEN COVERAGE {t['coverage_pct']}% "
          f"({t['hit_tokens']}/{t['tokens']})")


if __name__ == "__main__":
    main()
