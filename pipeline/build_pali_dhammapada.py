#!/usr/bin/env python3
"""Build the Pali lane seed corpus from SuttaCentral's bilara-data (CC0).

Emits:
  public/data/texts/pali/dhammapada.json          — Pali root (Mahāsaṅgīti ms)
  public/data/trans/pali-dhammapada-sujato.json   — Bhikkhu Sujato English

Source cache: .cache-bilara/bilara-data, sparse clone of
github.com/suttacentral/bilara-data (depth 1):
  root/pli/ms/sutta/kn/dhp/dhp*_root-pli-ms.json
  translation/en/sujato/sutta/kn/dhp/dhp*_translation-en-sujato.json
Segment files are flat maps keyed `dhp<verse>:<seg>`; keys are IDENTICAL in
root and translation (verified at build time), so alignment is segment-exact.
Verse = merge of that verse's segments in order; Pali stays in segmented form
(tokens split on spaces only — no sandhi splitting).
"""
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, ".cache-bilara", "bilara-data")
ROOT_DIR = os.path.join(SRC, "root", "pli", "ms", "sutta", "kn", "dhp")
TRANS_DIR = os.path.join(SRC, "translation", "en", "sujato", "sutta",
                         "kn", "dhp")
TEXT_OUT = os.path.join(HERE, "public", "data", "texts", "pali",
                        "dhammapada.json")
TRANS_OUT = os.path.join(HERE, "public", "data", "trans",
                         "pali-dhammapada-sujato.json")

SEG = re.compile(r"^dhp(\d+):(\d+)(?:\.(\d+))?$")


def load_pairs():
    """{verse_num: [(seg, pali, en), ...]} merged across vagga files."""
    verses: dict[int, list] = {}
    for fn in sorted(os.listdir(ROOT_DIR)):
        m = re.match(r"(dhp[\d-]+)_root-pli-ms\.json$", fn)
        if not m:
            continue
        rpath = os.path.join(ROOT_DIR, fn)
        tpath = os.path.join(TRANS_DIR,
                             f"{m.group(1)}_translation-en-sujato.json")
        if not os.path.exists(tpath):
            raise SystemExit(f"[pali-dhp] missing translation for {fn}")
        root = json.load(open(rpath, encoding="utf-8"))
        trans = json.load(open(tpath, encoding="utf-8"))
        if sorted(root) != sorted(trans):
            raise SystemExit(f"[pali-dhp] key mismatch in {m.group(1)}")
        for key in root:
            sm = SEG.match(key)
            # 0.x / y.0 = editorial headings (nikāya, vagga, story titles)
            if not sm or int(sm.group(2)) == 0 or sm.group(3) == "0":
                continue
            v, s = int(sm.group(1)), int(sm.group(2))
            pali, en = root[key].strip(), (trans.get(key) or "").strip()
            # Editorial marginalia carry no Sujato segment: vagga uddānas
            # ("...vaggo ...mo."), the gāthā-count block under dhp423, and
            # bhāṇavāra markers (verified corpus-wide, 77 segments).
            if pali and not en:
                continue
            # Closing colophon does have a translation; drop it explicitly.
            if re.search(r"\bsamattā\b", pali) or \
                    "Sayings of the Dhamma are complete" in en:
                continue
            verses.setdefault(v, []).append((s, pali, en))
    for segs in verses.values():
        segs.sort()
    return verses


def main() -> None:
    verses = load_pairs()
    refs, text_units, trans_units = [], [], []
    seg_total = 0
    for v in sorted(verses):
        segs = verses[v]
        seg_total += len(segs)
        pali = " ".join(p for _, p, _ in segs if p)
        eng = " ".join(e for _, _, e in segs if e)
        pali = re.sub(r"\s+", " ", pali).strip()
        eng = re.sub(r"\s+", " ", eng).strip()
        ref = f"dhp {v}"
        refs.append(v)
        text_units.append({"ref": ref, "words": pali.split(),
                           "text": pali})
        trans_units.append({"ref": ref, "text": eng})
    if refs != list(range(1, len(refs) + 1)):
        missing = [n for n in range(1, max(refs) + 1) if n not in set(refs)]
        raise SystemExit(f"[pali-dhp] non-contiguous verses, missing={missing[:10]}")

    for path, obj in (
        (TEXT_OUT, {"workId": "pali-dhammapada", "lang": "pi",
                    "kind": "verse", "units": text_units}),
        (TRANS_OUT, {"workId": "pali-dhammapada",
                     "translator": "Bhikkhu Sujato", "year": 2018,
                     "license": "CC0", "alignment": "segment-exact",
                     "units": trans_units}),
    ):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False)
        print(f"[pali-dhp] {len(obj['units'])} units -> {path}")

    # --- verification -----------------------------------------------------
    t1 = next(u["text"] for u in trans_units if u["ref"] == "dhp 1")
    p1 = next(u["text"] for u in text_units if u["ref"] == "dhp 1")
    tlast = trans_units[-1]["text"]
    print(f"[pali-dhp] {len(text_units)} verses, {seg_total} segments, "
          f"{sum(len(u['words']) for u in text_units)} pali tokens")
    print(f"[check] dhp 1 pali : {p1[:60]!r}")
    print(f"[check] dhp 1 mind/intent: "
          f"{any(w in t1.lower() for w in ('mind', 'intention'))} :: {t1[:70]!r}")
    print(f"[check] dhp 423 (ch26 end) :: {tlast[-90:]!r}")


if __name__ == "__main__":
    main()
