#!/usr/bin/env python3
"""Emit occurrence-specific DCS parses for reader works.

Unlike build_morph_dcs.py this never merges analyses by surface form.  A file
is published only when the source and reader token streams align at >=99.5%.
"""
import argparse
import difflib
import glob
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "pipeline"))
from build_morph_dcs import (SRC_DIR, EXTRA_SRC, WORK_OF_SITE_ID, _canonical_keys,
                             conllu_analyses)
from build_morph import parse_analysis
from sanscript import transliterate, DEVA

OUT = os.path.join(HERE, "public", "data", "morph-occurrence", "by-work")
CATALOG = os.path.join(HERE, "public", "data", "catalog.json")
DCS_WORK = {**WORK_OF_SITE_ID, "lalitavistara": "Lalitavistara"}


def canonical(token):
    keys = _canonical_keys(token)
    return keys[0] if keys else ""


def work_part_paths(work_id):
    cat = json.load(open(CATALOG, encoding="utf-8"))
    for author in cat["authors"]:
        for work in author["works"]:
            if work["id"] == work_id:
                return [os.path.join(HERE, "public", "data", p) for p in work["files"]]
    raise KeyError(work_id)


def reader_units(work_id):
    out = []
    for path in work_part_paths(work_id):
        for unit in json.load(open(path, encoding="utf-8"))["units"]:
            out.append((unit["ref"], unit["words"]))
    return out


def conllu_tokens(dcs_dir):
    """Flatten DCS rows. Range rows are represented by their own surface.

    The legacy helper supplies tag conversion and compound member construction;
    its yielded keys let us recover the source form only approximately, so this
    parser retains FORM alongside the same converted entry shape.
    """
    out = []
    for path in sorted(glob.glob(os.path.join(dcs_dir, "*.conllu"))):
        pending_form = None
        pending_left = 0
        pending_members = []
        for line in open(path, encoding="utf-8"):
            if not line.strip() or line.startswith("#"):
                continue
            c = line.rstrip("\n").split("\t")
            if len(c) < 6 or "." in c[0]:
                continue
            if "-" in c[0]:
                lo, _, hi = c[0].partition("-")
                if lo.isdigit() and hi.isdigit():
                    pending_form, pending_left, pending_members = c[1], int(hi)-int(lo)+1, []
                continue
            form, lemma, upos, feats = c[1], c[2], c[3], c[5]
            if upos in ("PUNCT", "SYM"):
                continue
            # Reuse the established DCS conversion by parsing this one row.
            tmp = os.path.join(os.path.dirname(path), ".occ-row.tmp")
            # Avoid temp files: import conversion functions directly.
            from build_morph_dcs import map_pos, map_feats, parse_feats
            fs = parse_feats(feats)
            entry = {"l": transliterate(lemma, "iast", DEVA), "p": map_pos(upos, fs),
                     "f": map_feats(upos, fs), "source": "dcs", "confidence": 1}
            if pending_form is not None:
                pending_members.append({k: entry[k] for k in ("l", "p", "f")})
                pending_left -= 1
                if pending_left == 0:
                    compound = dict(entry)
                    compound["m"] = pending_members
                    out.append((pending_form, compound))
                    pending_form = None
                continue
            out.append((form, entry))
    return out


def bhg_tokens():
    """BhG's curated Samsaadhanii export is the DCS-equivalent local source."""
    rows = json.load(open(os.path.join(HERE, ".cache-corpus", "analysis.json"), encoding="utf-8"))
    # analysis.json is grouped by chapter but not serialized in reader order.
    def numeric(value):
        digits = "".join(c for c in str(value or "") if c.isdigit())
        return int(digits or 0)
    rows.sort(key=lambda r: (numeric(r.get("chpatno")),
                             numeric(r.get("slokano")),
                             numeric(r.get("sentno"))))
    out = []
    for row in rows:
        form = row.get("word") or row.get("sandhied_word")
        analyses = parse_analysis(row.get("morph_in_context") or row.get("morph_analysis") or "")
        if not form or not analyses:
            continue
        lemma, pos, feats = analyses[0]
        ref = f"{numeric(row.get('chpatno'))}.{numeric(row.get('slokano'))}"
        out.append((form, {"l": lemma, "p": pos, "f": feats,
                           "source": "dcs", "confidence": 1}))
        out[-1] = (ref, *out[-1])
    return out


def align(work_id, source):
    units = reader_units(work_id)
    reader = [(ref, i, word) for ref, words in units for i, word in enumerate(words)]
    a, b = [canonical(x[2]) for x in reader], [canonical(x[0]) for x in source]
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    hits = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            hits.extend((reader[i], source[j][1]) for i, j in zip(range(i1, i2), range(j1, j2)))
    return reader, hits


def emit(work_id, source, dry_run=False):
    reader = [(ref, i, word) for ref, words in reader_units(work_id)
              for i, word in enumerate(words)]
    if work_id == "bhagavadgita":
        # Samsaadhanii's rows are syntactic/anvaya order. Match only inside
        # the same verse, consuming each exact canonical source row once.
        available = {}
        for ref, form, parse in source:
            available.setdefault(ref, {}).setdefault(canonical(form), []).append(parse)
        hits = []
        for item in reader:
            choices = available.get(item[0], {}).get(canonical(item[2]), [])
            if choices: hits.append((item, choices.pop(0)))
    else:
        reader, hits = align(work_id, source)
    pct = 100 * len(hits) / len(reader) if reader else 0
    report = {"workId": work_id, "reader_tokens": len(reader), "aligned": len(hits),
              "alignment_pct": round(pct, 3), "emitted": 0, "excluded": None}
    if pct < 99.5:
        report["excluded"] = "sequence alignment below 99.5%"
        return report
    shards = {}
    for (ref, index, surface), parse in hits:
        # A final local invariant: an annotation is only written onto its own form.
        if canonical(surface) == "":
            continue
        shards.setdefault(ref, {})[str(index)] = [parse]
        report["emitted"] += 1
    if not dry_run:
        dest = os.path.join(OUT, work_id)
        shutil.rmtree(dest, ignore_errors=True)
        os.makedirs(dest, exist_ok=True)
        refs = sorted(shards)
        # 100 refs keeps files modest and supports lazy reader loading.
        index = {}
        for n in range(0, len(refs), 100):
            name = f"{n // 100:04d}.json"
            block = {r: shards[r] for r in refs[n:n + 100]}
            with open(os.path.join(dest, name), "w", encoding="utf-8") as f:
                json.dump(block, f, ensure_ascii=False, separators=(",", ":"))
            index.update({r: name for r in block})
        with open(os.path.join(dest, "index.json"), "w", encoding="utf-8") as f:
            json.dump({"version": 1, "source": "dcs", "refs": index}, f,
                      ensure_ascii=False, separators=(",", ":"))
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("works", nargs="*", default=["bhagavadgita"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    reports = []
    for work in args.works:
        if work == "bhagavadgita":
            source, source_name = bhg_tokens(), ".cache-corpus/analysis.json"
        else:
            dcs = DCS_WORK[work]
            root = os.path.join(SRC_DIR, dcs)
            if not os.path.isdir(root): root = os.path.join(EXTRA_SRC, dcs)
            source, source_name = conllu_tokens(root), root
        r = emit(work, source, args.dry_run)
        r["source_files"] = source_name
        reports.append(r)
        print(json.dumps(r, ensure_ascii=False))
    os.makedirs(os.path.join(HERE, "qa-report"), exist_ok=True)
    with open(os.path.join(HERE, "qa-report", "occurrence-dcs.json"), "w", encoding="utf-8") as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
