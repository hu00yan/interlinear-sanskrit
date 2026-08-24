#!/usr/bin/env python3
"""Build the Bhagavadgītā work from the GRETIL IAST e-text (Tokunaga/Smith,
BORI-based). Emits public/data/texts/tlg03xx/bhagavadgita-part01.json with
Devanagari display tokens; refs normalized to "2.47" style.

Alignment note: morphology/glosses are keyed by SURFACE FORM (slp1_key), not
by position — see build_morph.py ("alignment": "surface-form").
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "pipeline"))
from sanscript import transliterate, IAST, DEVA  # noqa: E402

SRC = os.path.join(HERE, ".cache-corpus", "bhg_gretil.htm")
OUT_DIR = os.path.join(HERE, "public", "data", "texts", "tlg9000")


def verses():
    """GRETIL BhG layout: optional speaker line (full ref, no pada letter),
    then half-verses tagged Bhg_ch.vvv{a,b,c,d}. Combine halves per verse."""
    s = open(SRC, encoding="utf-8", errors="replace").read()
    txt = re.sub(r"<[^>]+>", "\n", s)
    txt = re.sub(r"[ \t]+", " ", txt)
    half_re = re.compile(
        r"^(.*?)\s*Bhg_(\d{1,2})\.(\d{1,3})([a-d])\s*(?:\[=MBh_[^\]]*\])?\s*$")
    cur: dict[str, dict[str, list[str]]] = {}
    order: list[str] = []
    for line in txt.splitlines():
        line = line.strip()
        if not line:
            continue
        m = half_re.match(line)
        if not m:
            continue
        words_txt, ch, v, pada = (
            m.group(1).strip(), int(m.group(2)), int(m.group(3)), m.group(4))
        words = [w for w in words_txt.split()
                 if re.search(r"[A-Za-z\u0100-\u017f\u1e00-\u1eff]", w)]
        ref = f"{ch}.{v}"
        if ref not in cur:
            cur[ref] = {}
            order.append(ref)
        cur[ref][pada] = words
    out = []
    for ref in order:
        halves = cur[ref]
        words: list[str] = []
        for p in sorted(halves):
            words.extend(halves[p])
        if words:
            out.append((ref, words))
    return out


def main() -> None:
    vs = [(ref, ws) for ref, ws in verses() if ws]
    os.makedirs(OUT_DIR, exist_ok=True)
    units = []
    for ref, iast_words in vs:
        deva_words = [transliterate(w, IAST, DEVA) for w in iast_words]
        units.append({"ref": ref,
                      "words": deva_words,
                      "_iast": " ".join(iast_words)})
    out = {"id": "bhagavadgita", "author": "Vyāsa (trad.)",
           "title": "Bhagavadgītā", "kind": "verse",
           "alignment": "surface-form",
           "units": [{"ref": u["ref"], "words": u["words"]} for u in units]}
    path = os.path.join(OUT_DIR, "bhagavadgita-part01.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    print(f"[bhg] {len(units)} verses -> {path}")


if __name__ == "__main__":
    main()
