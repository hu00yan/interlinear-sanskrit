#!/usr/bin/env python3
"""Build source-locked DCS occurrence data and its reader edition.

The Samsaadhanii export records each Bhagavadgita source token's verse-order
(`poem`) and contextual parse (`morph_in_context`).  Its syntactic
(`anvaya_no`) order is deliberately not used for display.
"""
import json
import glob
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "pipeline"))
from build_morph import parse_analysis
from build_morph_dcs import map_feats, map_pos, parse_feats
from sanscript import transliterate, DEVA

SRC = os.path.join(HERE, ".cache-corpus", "analysis.json")
TEXT = os.path.join(HERE, "public", "data", "texts", "tlg9000", "bhagavadgita-part01.json")
OUT = os.path.join(HERE, "public", "data", "morph-occurrence", "by-work", "bhagavadgita")
REPORT = os.path.join(HERE, "qa-report", "occurrence-dcs.json")


def number(value):
    try:
        return float(str(value))
    except ValueError:
        return None


def contextual_parse(row):
    analyses = parse_analysis(row.get("morph_in_context", ""))
    if len(analyses) != 1:
        return None
    lemma, pos, feats = analyses[0]
    return {
        "l": lemma, "p": pos, "f": feats,
        "g": row.get("english_meaning", "").replace("_", " "),
        "r": row["sourceIndex"],
        "source": "dcs", "confidence": 1,
    }


def build():
    rows = json.load(open(SRC, encoding="utf-8"))
    by_ref = {}
    omitted = []
    for source_index, row in enumerate(rows):
        row = dict(row, sourceIndex=source_index)
        poem = number(row.get("poem"))
        parsed = contextual_parse(row) is not None
        if not row.get("word") or poem is None or not parsed:
            omitted.append({"sourceIndex": source_index, "ref": f"{int(row.get('chpatno', 0))}.{int(row.get('slokano', 0))}", "word": row.get("word", "")})
            continue
        ref = f"{int(row['chpatno'])}.{int(row['slokano'])}"
        by_ref.setdefault(ref, []).append((poem, source_index, row))

    units, shard = [], {}
    for ref, entries in sorted(by_ref.items(), key=lambda item: tuple(map(int, item[0].split(".")))):
        # poem is the published verse order. Source index resolves rare tied
        # positions without changing either row's occurrence identity.
        entries.sort(key=lambda item: (item[0], item[1]))
        words = [row["word"] for _, _, row in entries]
        units.append({"ref": ref, "words": words})
        shard[ref] = {str(i): [contextual_parse(row)] for i, (_, _, row) in enumerate(entries)}

    os.makedirs(os.path.dirname(TEXT), exist_ok=True)
    with open(TEXT, "w", encoding="utf-8") as fh:
        json.dump({"id": "bhagavadgita", "author": "Vyāsa (trad.)", "title": "Bhagavadgītā", "kind": "verse", "edition": "dcs-source-locked", "units": units}, fh, ensure_ascii=False, separators=(",", ":"))
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "0000.json"), "w", encoding="utf-8") as fh:
        json.dump(shard, fh, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8") as fh:
        json.dump({"version": 2, "source": "dcs", "edition": "dcs-source-locked", "refs": {ref: "0000.json" for ref in shard}}, fh, ensure_ascii=False, separators=(",", ":"))
    report = [{"workId": "bhagavadgita", "edition": "dcs-source-locked", "source_files": ".cache-corpus/analysis.json", "reader_tokens": sum(len(u["words"]) for u in units), "aligned": sum(len(u["words"]) for u in units), "alignment_pct": 100, "emitted": sum(len(u["words"]) for u in units), "excluded": None, "omitted_unparsed_editorial_rows": omitted}]
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(report[0], ensure_ascii=False))


def build_conllu_work(work_id, dcs_name, text_path):
    """Use DCS's sentence surface itself as the displayed edition."""
    root = os.path.join(HERE, ".cache-dcs", "dcs-conllu", dcs_name)
    units, shard, sequence = [], {}, 0
    for path in sorted(glob.glob(os.path.join(root, "*.conllu"))):
        sent_id, rows = None, []
        def finish():
            nonlocal sequence, sent_id, rows
            if not sent_id or not rows:
                return
            ref = f"dcs-{sent_id}"
            units.append({"ref": ref, "words": [x[0] for x in rows]})
            shard[ref] = {str(i): [x[1]] for i, x in enumerate(rows)}
            sequence += len(rows)
            sent_id, rows = None, []
        for line in open(path, encoding="utf-8"):
            if not line.strip():
                finish()
                continue
            if line.startswith("# sent_id = "):
                sent_id = line.split("=", 1)[1].strip()
                continue
            if line.startswith("#"):
                continue
            c = line.rstrip("\n").split("\t")
            if len(c) < 6 or "." in c[0] or "-" in c[0]:
                continue
            form, lemma, upos, feats = c[1], c[2], c[3], c[5]
            if upos in ("PUNCT", "SYM"):
                continue
            occ = re.search(r"(?:^|\|)OccId=([^|]+)", c[9] if len(c) > 9 else "")
            entry = {
                "l": transliterate(lemma, "iast", DEVA),
                "p": map_pos(upos, parse_feats(feats)),
                "f": map_feats(upos, parse_feats(feats)),
                "r": occ.group(1) if occ else f"{os.path.basename(path)}:{c[0]}",
                "source": "dcs",
                "confidence": 1,
            }
            rows.append((transliterate(form, "iast", DEVA), entry))
        finish()
    # CoNLL-U FORM is source order and each emitted display token owns its row.
    with open(text_path, "w", encoding="utf-8") as fh:
        json.dump({"id": work_id, "author": "DCS", "title": work_id, "kind": "verse", "edition": "dcs-source-locked", "units": units}, fh, ensure_ascii=False, separators=(",", ":"))
    dest = os.path.join(HERE, "public", "data", "morph-occurrence", "by-work", work_id)
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest, exist_ok=True)
    with open(os.path.join(dest, "0000.json"), "w", encoding="utf-8") as fh:
        json.dump(shard, fh, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(dest, "index.json"), "w", encoding="utf-8") as fh:
        json.dump({"version": 2, "source": "dcs", "edition": "dcs-source-locked",
                   "refs": {r: "0000.json" for r in shard}}, fh,
                  ensure_ascii=False, separators=(",", ":"))
    return {"workId": work_id, "edition": "dcs-source-locked", "source_files": root, "reader_tokens": sequence, "aligned": sequence, "alignment_pct": 100, "emitted": sequence, "excluded": None}


if __name__ == "__main__":
    build()
    extra = build_conllu_work("buddhacarita", "Buddhacarita", os.path.join(HERE, "public", "data", "texts", "buddhist", "buddhacarita-part01.json"))
    report = json.load(open(REPORT, encoding="utf-8")); report.append(extra)
    with open(REPORT, "w", encoding="utf-8") as fh: json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(extra, ensure_ascii=False))
