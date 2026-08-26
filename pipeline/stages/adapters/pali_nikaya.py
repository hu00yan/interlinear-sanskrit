#!/usr/bin/env python3
"""Adapter lane for pilot work pali-dn / pali-mn.

WRAPS pipeline/build_pali_nikaya.py (untouched): every behaviour-bearing
function — load_sutta, split_chunks, colophon/heading/pe rules, chunk
thresholds — is imported from the legacy module. This file only sequences
them into stage-sized steps and reproduces main()'s unit-assembly loop and
json.dump parameters EXACTLY (byte-identical outputs; see
qa-report/pipeline-arch.md for hash proofs).

Stage mapping:
  10-fetch      sources verified by stages/10-fetch (bilara trees)
  20-normalize  load_sutta() per sutta: key sort, heading/pe/colophon/empty
                drops, root<->translation key match  -> segments.json
  30-tokenize   split_chunks + unit assembly (ref / words[] / text)
                -> units.json
  40-align      EN coverage + segment-exact alignment stats -> align.json
  70-emit       texts/pali/<stem>.json + trans/pali-<stem>-sujato.json
                (json.dump ensure_ascii=False, DEFAULT separators)
  90-qa         coverage gates + dn1/mn1 opening spot checks
"""
import json
import os
import re

from lib import REPO, read_json, write_json, load_builder_module

BUILDER = os.path.join(REPO, "pipeline", "build_pali_nikaya.py")

_NIK = {"pali-dn": ("dn", 1, 34), "pali-mn": ("mn", 1, 152)}


def _legacy():
    return load_builder_module(BUILDER)


def nikaya_of(work_id: str) -> str:
    if work_id not in _NIK:
        raise SystemExit(f"[pali_nikaya] unknown work {work_id}")
    return _NIK[work_id][0]


def range_of(work_id: str):
    return _NIK[work_id][1], _NIK[work_id][2]


# ---------------------------------------------------------------- 20-normalize
def normalize(work_id: str, cfg, inp: str, out: str) -> None:
    mod = _legacy()
    nik = nikaya_of(work_id)
    lo, hi = range_of(work_id)
    src_root = os.path.join(REPO, ".cache-bilara", "bilara-data",
                            "root", "pli", "ms", "sutta")
    drops = {"headings": 0, "pe": 0, "colophons": 0, "empty": 0}
    suttas, warnings = [], []
    for n in range(lo, hi + 1):
        loaded = mod.load_sutta(nik, n, drops)   # raises SystemExit on gaps
        if loaded is None:
            raise SystemExit(f"[pali-{nik}] missing file {nik}{n}")
        items, head_slots = loaded
        with open(os.path.join(src_root, nik,
                               f"{nik}{n}_root-pli-ms.json"),
                  encoding="utf-8") as fh:
            raw = len(json.load(fh))
        suttas.append({"n": n, "raw": raw, "head_slots": sorted(head_slots),
                       # items entries: [start_comps(list[int]), pali, en]
                       "items": [[list(c), pl, en] for c, pl, en in items]})
        if not items:
            warnings.append(f"{nik}{n}: no kept segments")
    write_json(out, {
        "workId": work_id, "nikaya": nik, "range": [lo, hi],
        "drops": drops, "warnings": warnings,
        "kept_total": sum(len(s["items"]) for s in suttas),
        "raw_total": sum(s["raw"] for s in suttas),
        "suttas": suttas,
    })


# ----------------------------------------------------------------- 30-tokenize
def tokenize(work_id: str, cfg, inp: str, out: str) -> None:
    mod = _legacy()
    nik = nikaya_of(work_id)
    seg = read_json(inp)
    text_units, trans_units, sutta_of_unit = [], [], {}
    n_split = 0
    for s in seg["suttas"]:
        n = s["n"]
        # rebuild the exact structures split_chunks expects (tuple comps)
        items = [(tuple(c), pl, en) for c, pl, en in s["items"]]
        chunks = mod.split_chunks(items, set(s["head_slots"]))
        if len(chunks) > 1:
            n_split += len(chunks)
        for ci, ch in enumerate(chunks):
            segs = [items[i] for i in ch]
            pali = re.sub(r"\s+", " ", " ".join(p for _, p, _ in segs)).strip()
            eng = re.sub(r"\s+", " ", " ".join(e for _, _, e in segs)).strip()
            ref = f"{nik} {n}" if len(chunks) == 1 else f"{nik} {n}.{ci}"
            text_units.append({"ref": ref, "words": pali.split(),
                               "text": pali})
            trans_units.append({"ref": ref, "text": eng})
            sutta_of_unit[ref] = n
    write_json(out, {
        "workId": work_id, "nikaya": nik,
        "text_units": text_units, "trans_units": trans_units,
        "unit_sutta": sutta_of_unit, "sub_unit_count": n_split,
        "kept_segments": sum(len(s["items"]) for s in seg["suttas"]),
        "warnings": [],
    })


# -------------------------------------------------------------------- 40-align
def align(work_id: str, cfg, inp: str, out: str) -> None:
    seg = read_json(inp)
    mapped = sum(1 for u in seg["trans_units"] if u["text"])
    # per-kept-segment coverage: unit-level EN presence is the shipped signal
    units_kept = len(seg["text_units"])
    cov = round(100 * mapped / units_kept, 2) if units_kept else 0.0
    write_json(out, {
        "workId": work_id,
        "alignment": "segment-exact",
        "key_match": 1.0,          # enforced by legacy load_sutta (sorted
        #                              root keys != translation keys => abort)
        "units": units_kept,
        "units_with_en": mapped,
        "en_coverage_pct": cov,
        "kept_segments": seg.get("kept_segments"),
        # pass-through for 70-emit (pipeline chains one artifact forward)
        "text_units": seg["text_units"],
        "trans_units": seg["trans_units"],
        "warnings": [],
    })


# --------------------------------------------------------------------- 70-emit
STEM = {"dn": "dn", "mn": "mn"}


def emit(work_id: str, cfg, inp: str, out_dir: str) -> list:
    """Write final docs under out_dir preserving repo-relative layout.
    Serialization MUST match build_pali_nikaya.main(): json.dump(...,
    ensure_ascii=False) with default separators."""
    nik = nikaya_of(work_id)
    stem = STEM[nik]
    units = read_json(inp)
    docs = [
        (os.path.join("texts", "pali", f"{stem}.json"),
         {"workId": f"pali-{stem}", "lang": "pi", "kind": "prose",
          "units": units["text_units"]}),
        (os.path.join("trans", f"pali-{stem}-sujato.json"),
         {"workId": f"pali-{stem}", "translator": "Bhikkhu Sujato",
          "year": 2018, "license": "CC0", "alignment": "segment-exact",
          "units": units["trans_units"]}),
    ]
    written = []
    for relpath, doc in docs:
        path = os.path.join(out_dir, relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)   # default separators!
        written.append(relpath)
    return written


# ----------------------------------------------------------------------- 90-qa
def qa(work_id: str, cfg, artifacts: dict, out: str) -> None:
    """Validation gate over prior artifacts. artifacts maps stage name ->
    artifact path (emit stage -> its output directory)."""
    mod = _legacy()
    nik = nikaya_of(work_id)
    lo, hi = range_of(work_id)
    seg, units, al = (read_json(artifacts[k]) for k in
                      ("normalize", "tokenize", "align"))
    checks, fails = [], []

    def check(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            fails.append(f"{name}: {detail}")

    got = sorted(set(units["unit_sutta"].values()))
    check("all_suttas_present", got == list(range(lo, hi + 1)),
          f"{len(got)}/{hi - lo + 1}")
    refs = [u["ref"] for u in units["text_units"]]
    check("refs_unique", len(set(refs)) == len(refs))
    check("units_match_trans",
          [u["ref"] for u in units["text_units"]] ==
          [u["ref"] for u in units["trans_units"]])
    check("no_empty_pali_units",
          all(u["words"] for u in units["text_units"]))

    def unit_text(ref, ulist):
        return next(u["text"] for u in ulist if u["ref"] == ref)
    if nik == "dn":
        r = "dn 1" if "dn 1" in units["unit_sutta"] else "dn 1.0"
        check("spot_dn1_opening",
              unit_text(r, units["trans_units"]).startswith("So I have heard"))
    if nik == "mn":
        r = "mn 1" if "mn 1" in units["unit_sutta"] else "mn 1.0"
        t = unit_text(r, units["trans_units"])
        check("spot_mn1_opening",
              "So I have heard" in t and
              ("differences arise" in t or "underlying tendencies" in t
               or len(t) > 5000))
    exp = (cfg.get("expected") or {})
    if exp.get("en_coverage_pct") is not None:
        check("en_coverage_frozen",
              al["en_coverage_pct"] == exp["en_coverage_pct"],
              f"{al['en_coverage_pct']} != {exp['en_coverage_pct']}")
    if exp.get("units"):
        check("units_frozen", al["units"] == exp["units"],
              f"{al['units']} != {exp['units']}")
    write_json(out, {"workId": work_id, "gates": checks,
                     "passed": not fails, "failures": fails})
    if fails:
        raise SystemExit(f"[qa:{work_id}] " + "; ".join(fails))
