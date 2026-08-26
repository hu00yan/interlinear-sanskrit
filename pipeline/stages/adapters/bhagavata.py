#!/usr/bin/env python3
"""Adapter lane for pilot work bhagavata (Bhāgavatapurāṇa, 12 skandhas).

WRAPS .bhg-work/build_bhagavata.py (untouched): parse(), tokenize(),
collapse_doubled_halves(), split_long(), suffix_refs(), the GRETIL quirks
(519 doubled-half verses, keep-last dup refs) all come from the legacy
module. This file sequences them into stages and reproduces main()'s
serialization EXACTLY (json.dump ensure_ascii=False, separators=(",", ":")).

Stage mapping:
  10-fetch      .cache-corpus/purana/sa_bhAgavatapurANa.txt checksum
  20-normalize  parse(): ref-marker split, dedup, a-b-a-b collapse
                -> verses.json (IAST words + daṇḍa bounds)
  30-tokenize   split_long at daṇḍas (>60-word ceiling) + IAST->Devanagari
                via sanscript.transliterate -> tokens.json
  70-emit       suffix_refs + texts/purana/bhagavata-<NN>.json + counts
                artifact (8MB shard cap asserted, as in legacy main)
  90-qa         per-skandha unit counts vs manifest.expected, Devanagari-only
                words, monotone unique refs
"""
import json
import os
import sys

from lib import REPO, read_json, write_json, load_builder_module

BUILDER = os.path.join(REPO, ".bhg-work", "build_bhagavata.py")
if REPO not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "pipeline"))


def _legacy():
    mod = load_builder_module(BUILDER)
    if not hasattr(mod, "transliterate"):     # sanscript import inside legacy
        from sanscript import transliterate, IAST, DEVA
        mod.transliterate, mod.IAST, mod.DEVA = transliterate, IAST, DEVA
    return mod


# ---------------------------------------------------------------- 20-normalize
def normalize(work_id: str, cfg, inp: str, out: str) -> None:
    mod = _legacy()
    verses = mod.parse()      # [{ref, words(IAST), bounds}] — prints stats
    write_json(out, {
        "workId": work_id,
        "verses": [{"ref": v["ref"], "words": v["words"],
                    "bounds": [int(b) for b in v["bounds"]]}
                   for v in verses],
        "warnings": [],
    })


# ----------------------------------------------------------------- 30-tokenize
def tokenize(work_id: str, cfg, inp: str, out: str) -> None:
    """Legacy main() middle: group by skandha, split_long, transliterate."""
    mod = _legacy()
    verses = read_json(inp)["verses"]
    by_sk = {}
    for u in verses:
        sk = int(u["ref"].split(".")[0])
        for chunk in mod.split_long(u["words"], u["bounds"]):
            by_sk.setdefault(sk, []).append(
                {"ref": u["ref"],
                 "words": [mod.transliterate(w, mod.IAST, mod.DEVA)
                           for w in chunk]})
    write_json(out, {"workId": work_id,
                     "skandhas": {str(k): v for k, v in sorted(by_sk.items())},
                     "warnings": []})


# --------------------------------------------------------------------- 70-emit
def emit(work_id: str, cfg, inp: str, out_dir: str) -> list:
    """Legacy main() tail: suffix_refs, compact JSON docs, 8MB cap.
    Writes under out_dir preserving repo-relative layout; per-skandha counts
    land as a run artifact (legacy wrote them to .bhg-work/counts.json)."""
    mod = _legacy()
    by_sk = {int(k): v for k, v in read_json(inp)["skandhas"].items()}
    counts = {}
    written = []
    os.makedirs(os.path.join(out_dir, "texts", "purana"), exist_ok=True)
    for sk in sorted(by_sk):
        cus = by_sk[sk]
        mod.suffix_refs(cus)
        doc = {"id": f"bhagavata-{sk:02d}", "author": "Vyāsa (trad.)",
               "title": mod.SK_TITLES[sk], "kind": "prose",
               "alignment": "surface-form", "units": cus}
        relp = f"texts/purana/bhagavata-{sk:02d}.json"
        path = os.path.join(out_dir, relp)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"))
        size = os.path.getsize(path)
        assert size <= 8 * 1024 * 1024, f"{relp} {size}B exceeds 8MB"
        counts[str(sk)] = len(cus)
        written.append(relp)
    write_json(os.path.join(out_dir, "_artifacts", "bhagavata-counts.json"),
               counts)
    return written


# ----------------------------------------------------------------------- 90-qa
def qa(work_id: str, cfg, artifacts: dict, out: str) -> None:
    emit_dir = artifacts["emit"]
    exp = (cfg.get("expected") or {}).get("units_per_skandha") or {}
    checks, fails = [], []

    def check(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            fails.append(f"{name}: {detail}")

    # gate the EMITTED files (post suffix_refs — duplicates only exist before)
    for sk_s in sorted(exp):
        sk = int(sk_s)
        path = os.path.join(emit_dir, f"texts/purana/bhagavata-{sk:02d}.json")
        if not os.path.exists(path):
            check(f"emitted[{sk_s}]", False, path)
            continue
        doc = read_json(path)
        cus = doc["units"]
        check(f"id[{sk_s}]", doc["id"] == f"bhagavata-{sk:02d}", doc["id"])
        check(f"title[{sk_s}]", doc["title"] == _legacy().SK_TITLES[sk])
        check(f"units_frozen[{sk_s}]", len(cus) == int(exp[sk_s]),
              f"{len(cus)} != {exp[sk_s]}")
        refs = [u["ref"] for u in cus]
        check(f"refs_unique[{sk_s}]", len(set(refs)) == len(refs),
              f"{len(refs) - len(set(refs))} dups")
        keys = [tuple(int(x) for x in r.rstrip(
            "abcdefghijklmnopqrstuvwxyz").split(".")) for r in refs]
        check(f"refs_monotone[{sk_s}]",
              all(a <= b for a, b in zip(keys, keys[1:])))
        bad = [w for u in cus for w in u["words"]
               if any("a" <= c.lower() <= "z" for c in w)]
        check(f"devanagari_only[{sk_s}]", not bad, f"{len(bad)} IAST residues")
    write_json(out, {"workId": work_id, "gates": checks,
                     "passed": not fails, "failures": fails})
    if fails:
        raise SystemExit(f"[qa:{work_id}] " + "; ".join(fails[:8]))
