#!/usr/bin/env python3
"""build_search_index.py — corpus-wide home-search index, greek-reader parity.

Builds TWO artifacts from the COMMITTED corpus (public/data), answering the
home page's two full-text sections (mirrors greek-reader's
scripts/build_grc_index.py + scripts/build-search-index.py depth):

1. WORD INDEX  public/data/search-index-sa/
   "_meta.json"  {"v":1,"letters":["a",..],"works":[workId,...]}
   "<letter>.json"  {"<norm>": [totalOccurrences,
                                [[widIdx, firstRef], ...]], ...}
   "Which WORKS contain this word?" over EVERY catalog work's unit texts
   (Sanskrit Devanagari AND Pali roman). Keys are FULLY FOLDED ascii:
   Devanagari -> IAST -> lowercase -> NFD -> drop combining marks ->
   keep [a-z0-9] only. So query "rāma", "राम" and sloppy "rama" all fold
   to "rama" — one key space serves both scripts (house-mandatory dual-form).
   Per word: works sorted by occurrence desc, capped MAX_WORKS_PER_WORD=30,
   first-seen ref truncated to 24 chars. Sharded by folded initial so no
   single fetch exceeds SHARD_BYTES=8MB (lazy per-letter loads, same
   pattern as the morph letter shards).

2. TRANSLATION SNIPPET INDEX public/data/search-index-trans.json
   {"v":1,"w":[workId,...],"e":[[widIdx, ref, normalizedSnippet], ...]}
   Sentence-ish snippets (<=240 chars) of every catalog work's English
   translation files (catalog translation.files is authoritative). Same
   folding normalization, so romanized Sanskrit inside old translations
   ("Râma", "Pândavas") matches diacritic-free queries too. If raw JSON
   exceeds TRANS_BYTES=8MB, a keep-gap ladder (chars since last kept
   snippet per work) tightens until it fits.

Normalization MUST stay byte-identical with src/api.ts normSa() — the QA
gate check_search_index.py probes both directions ('rāma' vs 'राम').

Usage:
    python3 pipeline/stages/80-searchindex/build_search_index.py
    python3 pipeline/stages/80-searchindex/build_search_index.py --out-root DIR
"""
import argparse
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
STAGES = os.path.dirname(HERE)
sys.path.insert(0, STAGES)
import lib  # noqa: E402

REPO = lib.REPO
DEFAULT_OUT = os.path.join(REPO, "public", "data")

MAX_WORKS_PER_WORD = 30
REF_CHARS = 24
SHARD_BYTES = 8 * 1024 * 1024
TRANS_BYTES = 8 * 1024 * 1024
# keep-gap ladder for the snippet index (greek capped-mode generalised)
TRANS_GAP_LADDER = [0, 500, 1000, 2000, 4000]

_COMB = re.compile(
    "[\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20f0\ufe20-\ufe2f]")
_NONKEY = re.compile(r"[^a-z0-9]+")
_SNIP_SPLIT = re.compile(r"(?<=[.!?;:])\s+")


def norm_sa(token: str) -> str:
    """Folded ascii search key. Mirrors src/api.ts normSa() exactly:
    Devanagari -> IAST, lowercase, NFD, drop combining marks, keep a-z0-9."""
    if any("\u0900" <= c <= "\u097f" for c in token):
        token = _dev_to_iast(token)
    s = unicodedata.normalize("NFD", token.lower())
    s = _COMB.sub("", s)
    return _NONKEY.sub("", s)


_DEV_CACHE = {}


def _dev_to_iast(text: str) -> str:
    """Devanagari -> IAST via indic-transliteration (memoised per raw form;
    corpora repeat surface forms heavily so this cuts build time ~10x)."""
    hit = _DEV_CACHE.get(text)
    if hit is None:
        from indic_transliteration import sanscript as _s
        hit = _s.transliterate(text, _s.DEVANAGARI, _s.IAST)
        _DEV_CACHE[text] = hit
    return hit


def catalog_map(data_dir: str):
    """(file->workId map for texts/, workId->[trans file relpaths])."""
    catalog = lib.read_json(os.path.join(data_dir, "catalog.json"))
    text_owner: dict[str, str] = {}
    trans_of: dict[str, list[str]] = {}
    for a in catalog["authors"]:
        for w in a["works"]:
            for f in w.get("files", []):
                text_owner[f[len("data/"):] if f.startswith("data/") else f] \
                    = w["id"]
            fs = (w.get("translation") or {}).get("files") or []
            clean = [x[len("data/"):] if x.startswith("data/") else x
                     for x in fs]
            if clean:
                trans_of.setdefault(w["id"], []).extend(clean)
    return catalog, text_owner, trans_of


def unit_tokens(unit: dict):
    words = unit.get("words")
    if isinstance(words, list):
        yield from words
    elif isinstance(unit.get("w"), str):
        yield from unit["w"].split(" ")


def build_word_index(data_dir: str):
    """vocab[norm][wid] = [count, firstRef]; works list in catalog order."""
    _, text_owner, _ = catalog_map(data_dir)
    tdir = os.path.join(data_dir, "texts")
    vocab: dict[str, dict[str, list]] = {}
    works: list[str] = []
    seen: set[str] = set()
    cache: dict[str, str] = {}
    files = 0
    units = 0
    tokens = 0
    for root, _dirs, names in sorted(os.walk(tdir)):
        for name in sorted(names):
            if not name.endswith(".json"):
                continue
            rel = os.path.relpath(os.path.join(root, name), data_dir)
            wid = text_owner.get(rel)
            if wid is None:
                continue
            if wid not in seen:
                seen.add(wid)
                works.append(wid)
            files += 1
            try:
                doc = lib.read_json(os.path.join(root, name))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"  ! skipping unreadable {rel}: {e}", file=sys.stderr)
                continue
            for u in doc.get("units", []):
                units += 1
                ref = u.get("ref") or ""
                for raw in unit_tokens(u):
                    k = cache.get(raw)
                    if k is None:
                        k = norm_sa(raw)
                        cache[raw] = k
                    if len(k) < 2:
                        continue
                    tokens += 1
                    slot = vocab.setdefault(k, {})
                    ent = slot.get(wid)
                    if ent is None:
                        slot[wid] = [1, ref]
                    else:
                        ent[0] += 1
    return vocab, works, {"files": files, "units": units, "tokens": tokens}


def dump_shard(letter: str, entries: dict, wids: dict,
               works_cap: int) -> str:
    out = {}
    for k, slot in entries.items():
        ranked = sorted(slot.items(),
                        key=lambda kv: (-kv[1][0], kv[0]))[:works_cap]
        total = sum(c for c, _ in slot.values())
        out[k] = [total,
                  [[wids[w], (r or "")[:REF_CHARS]] for w, (_c, r) in ranked]]
    return json.dumps(out, ensure_ascii=False, separators=(",", ":"))


WORKS_CAP_LADDER = [MAX_WORKS_PER_WORD, 15, 8]


def write_word_index(vocab, works, out_root: str) -> dict:
    outdir = os.path.join(out_root, "search-index-sa")
    os.makedirs(outdir, exist_ok=True)
    wids = {w: i for i, w in enumerate(works)}
    buckets: dict[str, dict] = {}
    for k, slot in vocab.items():
        buckets.setdefault(k[0], {})[k] = slot
    letters = []
    max_bytes = 0
    for letter, entries in sorted(buckets.items()):
        raw = ""
        for works_cap in WORKS_CAP_LADDER:
            raw = dump_shard(letter, entries, wids, works_cap)
            if len(raw.encode()) <= SHARD_BYTES:
                break
        size = len(raw.encode())
        max_bytes = max(max_bytes, size)
        path = os.path.join(outdir, f"{letter}.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(raw)
        letters.append(letter)
    meta = {"v": 1, "letters": sorted(letters), "works": works}
    with open(os.path.join(outdir, "_meta.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(meta, ensure_ascii=False, separators=(",", ":")))
    return {"entries": len(vocab), "works": len(works),
            "shards": len(letters), "max_shard_bytes": max_bytes}


def snippets(text: str):
    """Sentence-ish snippets <=240 chars (greek build-search-index.py)."""
    parts = _SNIP_SPLIT.split(text.strip())
    out = []
    buf = ""
    for p in parts:
        buf = f"{buf} {p}".strip() if buf and len(buf) < 40 else p
        if len(buf) >= 40:
            out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    for s in out:
        while len(s) > 240:
            cut = s.rfind(" ", 160, 240)
            cut = cut if cut > 0 else 240
            yield s[:cut]
            s = s[cut:].lstrip()
        if s:
            yield s


def build_trans_index(data_dir: str, gap: int):
    """[[widIdx, ref, normalizedSnippet], ...]; widIdx -> works list."""
    catalog, _text_owner, trans_of = catalog_map(data_dir)
    works: list[str] = []
    wid_idx: dict[str, int] = {}
    for a in catalog["authors"]:
        for w in a["works"]:
            wid_idx[w["id"]] = len(works)
            works.append(w["id"])
    entries = []
    kept_chars: dict[str, int] = {}
    used = set()
    for wid, files in sorted(trans_of.items()):
        for rel in files:
            path = os.path.join(data_dir, rel)
            if not os.path.exists(path):
                continue
            used.add(rel)
            try:
                doc = lib.read_json(path)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"  ! skipping unreadable {rel}: {e}", file=sys.stderr)
                continue
            wi = wid_idx[wid]
            for u in doc.get("units", []):
                txt = u.get("text") or ""
                ref = u.get("ref") or ""
                if not txt or not ref:
                    continue
                for sn in snippets(txt):
                    ns = norm_sa(sn)
                    # gap=0 keeps everything; else keep only when >=gap
                    # normalized chars passed since the last kept snippet
                    # (default = keep the work's first snippet, greek rule)
                    since = kept_chars.get(rel, gap)
                    if len(ns) < 15 or (gap and since < gap):
                        kept_chars[rel] = since + len(ns)
                        continue
                    entries.append([wi, ref[:24], ns])
                    kept_chars[rel] = 0
    present = sorted({wid for wid, idx in wid_idx.items()
                      if any(e[0] == idx for e in entries)})
    remap = {wid: i for i, wid in enumerate(present)}
    e = [[remap[works[x[0]]], x[1], x[2]] for x in entries]
    return {"v": 1, "w": present, "e": e}, \
        {"files": len(used), "snippets": len(e)}


def write_trans_index(data_dir: str, out_root: str) -> dict:
    raw = ""
    stats = {}
    for gap in TRANS_GAP_LADDER:
        doc, stats = build_trans_index(data_dir, gap)
        raw = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
        size = len(raw.encode())
        print(f"[search-index] trans gap={gap}: {len(doc['w'])} works, "
              f"{stats['snippets']} snippets, {size / 1e6:.1f}MB")
        if size <= TRANS_BYTES:
            break
    size = len(raw.encode())
    if size > TRANS_BYTES:
        lib.fail(f"translation index {size / 1e6:.1f}MB still over "
                 f"{TRANS_BYTES // (1024 * 1024)}MB at max gap")
    with open(os.path.join(out_root, "search-index-trans.json"), "w",
              encoding="utf-8") as fh:
        fh.write(raw)
    stats["bytes"] = size
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-root", default=DEFAULT_OUT)
    ap.add_argument("--data-dir",
                    help="corpus root (default <out-root>; set to read one "
                         "tree and write another)")
    args = ap.parse_args()
    data_dir = args.data_dir or args.out_root
    vocab, works, ws = build_word_index(data_dir)
    wi = write_word_index(vocab, works, args.out_root)
    print(f"[search-index] word index: {wi['entries']} forms, "
          f"{wi['works']} works, {wi['shards']} shards "
          f"(max {wi['max_shard_bytes'] / 1e6:.1f}MB/shard) "
          f"from {ws['files']} files / {ws['units']} units")
    ts = write_trans_index(data_dir, args.out_root)
    print(f"[search-index] wrote search-index-sa/ + search-index-trans.json "
          f"({ts['bytes'] / 1e6:.1f}MB)")


if __name__ == "__main__":
    main()
