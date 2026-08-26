#!/usr/bin/env python3
"""check_morph_pali.py — fail-loud QA gate for the Pali DPD morphology
shards (public/data/morph-pali/**, built by stages/50-analyze/pali_dpd.py).

Gates:
  1. SHARD SHAPE   every letter shard is {"_provenance":…, key:[analyses]}
                   with key ∈ [a-z~]+, analyses non-empty and shape-valid
                   ({l,p,f,x} strings + optional g; m-chains {d,l,p,f});
                   provenance carries source:"dpd" +
                   license:"CC BY-NC-SA 4.0" on EVERY file.
  2. COVERAGE      sample words[] from every pali-canon text file, resolve
                   through _surface/by-work slices -> shards; overall token-
                   weighted coverage must clear --min-coverage and no work
                   may fall below --min-work.
  3. NIGGAHITA     for sampled corpus tokens containing ṁ/ṃ: BOTH spellings
                   resolve to the SAME shard entry (fold sanity — a miss in
                   either direction means the ṁ→ṃ fold broke).

Self-skips (exit 0) when morph-pali is absent so worker.py can run it
unconditionally after publish.

Usage:
  python3 pipeline/stages/90-qa/check_morph_pali.py \
      [--data-root public/data] [--sample-units 40] [--report PATH]
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "50-analyze"))
from pali_dpd import canon_key, lookup_key_of, fold_niggahita  # noqa: E402

VALID_KEY = set("abcdefghijklmnopqrstuvwxyz~")


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def gate_shards(data_root: str, errors: list) -> dict:
    base = os.path.join(data_root, "morph-pali")
    shards = {}
    files = sorted(glob.glob(os.path.join(base, "[a-z].json")))
    if not files:
        errors.append("no letter shards under morph-pali/")
        return shards
    n_keys = n_analyses = 0
    for fp in files:
        doc = load_json(fp)
        prov = doc.get("_provenance")
        if not isinstance(prov, dict) or \
                prov.get("source") != "dpd" or \
                prov.get("license") != "CC BY-NC-SA 4.0":
            errors.append(f"{os.path.basename(fp)}: bad/missing _provenance "
                          f"(need source=dpd + CC BY-NC-SA 4.0)")
        for key, analyses in doc.items():
            if key == "_provenance":
                continue
            if not key or any(c not in VALID_KEY for c in key):
                errors.append(f"{os.path.basename(fp)}: invalid key {key!r}")
                continue
            if not isinstance(analyses, list) or not analyses:
                errors.append(f"{key!r}: empty analysis array")
                continue
            shards[key] = analyses
            n_keys += 1
            for a in analyses:
                n_analyses += 1
                if not isinstance(a.get("l"), str) or not a["l"] or \
                        not isinstance(a.get("p"), str) or not a["p"] or \
                        not all(isinstance(a.get(k), str)
                                for k in ("f", "x")):
                    errors.append(f"{key!r}: analysis missing l/p/f/x: "
                                  f"{json.dumps(a, ensure_ascii=False)[:80]}")
                    break
                if a["p"] not in ("noun", "verb", "part", "indecl"):
                    errors.append(f"{key!r}: POS {a['p']!r} outside house "
                                  f"vocab noun|verb|part|indecl")
                    break
                chain = a.get("m")
                if chain is not None and (
                        not isinstance(chain, list) or not chain or
                        not all(isinstance(m, dict) and m.get("d") and
                                m.get("l") and m.get("p") and
                                isinstance(m.get("f"), str)
                                for m in chain)):
                    errors.append(f"{key!r}: malformed member chain")
                    break
    print(f"[check_morph_pali] shape: {n_keys} keys / {n_analyses} "
          f"analyses across {len(files)} shards")
    return shards


def iter_pali_files(catalog):
    for author in catalog["authors"]:
        if author.get("key") != "pali-canon":
            continue
        for w in author["works"]:
            yield w["id"], w["files"]


def sampled_units(path: str, max_units: int) -> list:
    units = load_json(path)
    units = units.get("units", []) if isinstance(units, dict) else units
    if len(units) <= max_units:
        return units
    step = len(units) / max_units
    return [units[int(i * step)] for i in range(max_units)]


def gate_coverage(data_root: str, shards: dict, surface_by_work: dict,
                  max_units: int, min_work: float, min_overall: float,
                  errors: list) -> dict:
    catalog = load_json(os.path.join(data_root, "catalog.json"))
    per_work = {}
    tot = hit = 0
    for wid, files in iter_pali_files(catalog):
        slice_ = surface_by_work.get(wid, {})
        wt = wh = 0
        for relpath in files:
            for u in sampled_units(os.path.join(data_root, relpath),
                                   max_units):
                for tok in u.get("words", []) or []:
                    k = slice_.get(tok) or canon_key(tok)
                    wt += 1
                    if k and k in shards:
                        wh += 1
        pct = round(100.0 * wh / wt, 1) if wt else 0.0
        per_work[wid] = {"tokens": wt, "hit": wh, "coverage_pct": pct}
        tot += wt
        hit += wh
    overall = round(100.0 * hit / tot, 1) if tot else 0.0
    worst = sorted(per_work.items(), key=lambda kv: kv[1]["coverage_pct"])
    print(f"[check_morph_pali] coverage: overall {overall}% over {tot} "
          f"sampled tokens / {len(per_work)} works; worst: "
          + ", ".join(f"{w} {v['coverage_pct']}%"
                      for w, v in worst[:5]))
    if overall < min_overall:
        errors.append(f"overall coverage {overall}% < floor "
                      f"{min_overall}%")
    for w, v in per_work.items():
        if v["coverage_pct"] < min_work:
            errors.append(f"work {w}: coverage {v['coverage_pct']}% < "
                          f"per-work floor {min_work}%")
    return {"overall_pct": overall, "per_work": per_work}


def gate_niggahita(surface_by_work: dict, shards: dict, probes: int,
                   errors: list) -> int:
    """ṁ/ṃ fold sanity: both spellings must land on identical entries."""
    checked = 0
    for wid, slice_ in surface_by_work.items():
        for tok, key in slice_.items():
            if "\u1e41" not in tok and "\u1e43" not in tok:
                continue
            other = (tok.replace("\u1e41", "\u2468")
                        .replace("\u1e43", "\u1e41")
                        .replace("\u2468", "\u1e43"))
            ok_other = lookup_key_of(other) == key and key in shards
            if not ok_other:
                errors.append(f"niggahita fold broken for {tok!r} ({wid}): "
                              f"swapped spelling does not hit {key!r}")
            checked += 1
            if checked >= probes:
                return checked
    return checked


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-root",
                    default=os.path.join(REPO, "public", "data"))
    ap.add_argument("--sample-units", type=int, default=40,
                    help="units sampled per text file (even spread)")
    ap.add_argument("--min-coverage", type=float, default=None,
                    help="overall %% floor (default from measured baseline)")
    ap.add_argument("--min-work", type=float, default=None,
                    help="per-work %% floor (default from measured baseline)")
    ap.add_argument("--probes", type=int, default=200)
    ap.add_argument("--max-show", type=int, default=20)
    ap.add_argument("--report")
    args = ap.parse_args()
    # floors sit far below measured Pass-A reality; they catch catastrophic
    # regressions (empty/missing shards, broken folding), not honest misses
    min_overall = args.min_coverage if args.min_coverage is not None else 20.0
    min_work = args.min_work if args.min_work is not None else 5.0

    if not os.path.isdir(os.path.join(args.data_root, "morph-pali")):
        print("[check_morph_pali] SKIP: no public/data/morph-pali (not "
              "built yet)")
        return
    errors = []
    shards = gate_shards(args.data_root, errors)
    slices_dir = os.path.join(args.data_root, "morph-pali", "_surface",
                              "by-work")
    surface_by_work = {}
    for fp in sorted(glob.glob(os.path.join(slices_dir, "*.json"))):
        wid = os.path.splitext(os.path.basename(fp))[0]
        doc = load_json(fp)
        prov = doc.pop("_provenance", None)
        if not isinstance(prov, dict) or prov.get("source") != "dpd":
            errors.append(f"_surface/by-work/{wid}.json: bad _provenance")
        surface_by_work[wid] = doc
    cov = gate_coverage(args.data_root, shards, surface_by_work,
                        args.sample_units, min_work,
                        min_overall, errors) if shards else {}
    if shards:
        n_probe = gate_niggahita(surface_by_work, shards, args.probes,
                                 errors)
        print(f"[check_morph_pali] niggahita probes: {n_probe}")
        if n_probe == 0:
            errors.append("niggahita sanity found no \u1e41/\u1e43 tokens to "
                          "probe (slices lost them?)")

    shown = 0
    for e in errors[:args.max_show]:
        print(f"  VIOLATION: {e}")
        shown += 1
    if len(errors) > shown:
        print(f"  … +{len(errors) - shown} more")

    summary = {"errors": len(errors),
               "coverage": cov.get("overall_pct"),
               "per_work": cov.get("per_work")}
    if args.report:
        os.makedirs(os.path.dirname(args.report), exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, ensure_ascii=False, indent=1)
    if errors:
        print(f"[check_morph_pali] FAIL: {len(errors)} violations "
              f"(fail-loud)")
        sys.exit(1)
    print("[check_morph_pali] PASS")


if __name__ == "__main__":
    main()
