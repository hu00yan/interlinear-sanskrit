#!/usr/bin/env python3
"""Build Saṃyutta Nikāya (56 saṃyuttas, 3,024 numbered suttas in 1,819 bilara
files) from SuttaCentral's bilara-data (CC0). Mirrors pipeline/
build_pali_nikaya.py (DN/MN) output schema exactly:

  public/data/texts/pali/sn.json            — Pali root (Mahāsaṅgīti ms)
  public/data/trans/pali-sn-sujato.json     — Bhikkhu Sujato English

Unit granularity: ONE SUTTA = ONE UNIT, ref `sn <saṃyutta>.<sutta>` — but SN
bilara layout differs from DN/MN in one respect: some FILES cover several
suttas as peyyāla ranges (`sn56.105-107_*.json` holds segments keyed
`sn56.105-107:0.1`, `sn12.93-103:1.1`, `sn12.104-114:1.1`, …). Each distinct
key stem inside a file therefore becomes its own unit, referenced by its
START sutta number (`sn 56.105`, `sn 12.93`, …) — the compressed repetitions
stay one unit per covered number-range rather than being duplicated.

As in DN/MN, suttas whose kept segment count exceeds SEG_SPLIT (>150) are
subdivided into sub-units `sn 35.95.0`, `sn 35.95.1`, … (a third ref level;
boundaries = numbered internal headings / force rules identical to DN/MN).
7 suttas trigger this (largest: sn42.13, sn40.10, sn22.85).

Editorial drops identical to DN/MN: heading segments (any `0` component —
collection/vagga/sutta titles), bare `…pe…` markers, short unquoted
colophons ("X niṭṭhitaṁ.", "…samattaṁ." incl. SN uddāna enders);
Pali-without-EN segments KEPT (Sujato elides repeat formulas).

Batching: `build_pali_sn.py [A-B] [C-D] …` takes SAṂYUTTA numbers/ranges;
each run merges into the existing JSON (replacing that saṃyutta's units),
so incremental commits stay consistent. Default = full 1-56.
Also refreshes public/data/catalog.json: appends/updates ONE work
`pali-samyutta-nikaya` under the existing "Pali Canon" group.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, ".cache-bilara", "bilara-data")
SEG_SPLIT, MIN_CHUNK, FORCE_CHUNK = 150, 60, 160
NSAM = 56
WORK_ID = "pali-samyutta-nikaya"
STEM = "sn"

COMP = re.compile(r"\d+(?:-\d+)?")
PE_ONLY = re.compile(r'^[\s“"‘]*…\s*pe\s*…[\s”"’]*$')
QUOTED = re.compile(r'[“”‘’"?]')
MARKERS = {"niṭṭhitaṁ", "niṭṭhitā", "niṭṭhito"}
STEMLINE = re.compile(r"^sn(\d+)\.(\d+)(?:-(\d+))?$")


def is_colophon(pl: str) -> bool:
    """Same rule as DN/MN builder: short unquoted completion marker."""
    if QUOTED.search(pl):
        return False
    ws = pl.strip().rstrip(".").split()
    if not ws or len(ws) > 8:
        return False
    if any(i > 0 and w.lower() in MARKERS for i, w in enumerate(ws)):
        return True
    return ws[-1].lower() in ("samattaṁ", "samatto")


def stem_of(key: str):
    """'sn12.104-114:1.1' -> ((12, 104, 114), ('1.1' comps...)) or None."""
    st, _, rest = key.partition(":")
    m = STEMLINE.match(st)
    if not m:
        return None
    a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3) or m.group(2))
    segs = tuple(int(t.split("-")[0]) for t in COMP.findall(rest))
    return (a, b, c), segs


def is_heading(segs_comps: tuple[int, ...]) -> bool:
    return any(x == 0 for x in segs_comps)


def load_file(sam: int, fname: str):
    """-> sorted [(stem_start, seg_comps, pali, en)] for one bilara file."""
    rpath = os.path.join(SRC, "root", "pli", "ms", "sutta", STEM,
                         f"{STEM}{sam}", fname)
    tpath = os.path.join(SRC, "translation", "en", "sujato", "sutta", STEM,
                         f"{STEM}{sam}",
                         fname.replace("_root-pli-ms",
                                       "_translation-en-sujato"))
    root = json.load(open(rpath, encoding="utf-8"))
    trans = json.load(open(tpath, encoding="utf-8"))
    if sorted(root) != sorted(trans):
        raise SystemExit(f"[pali-{STEM}] key mismatch in {fname}")
    stream = []
    for k, p in root.items():
        parsed = stem_of(k)
        if parsed is None:
            raise SystemExit(f"[pali-{STEM}] unparsable key {k} in {fname}")
        st, segc = parsed
        pl, en = p.strip(), (trans.get(k) or "").strip()
        stream.append((st, segc, pl, en))
    stream.sort(key=lambda it: (it[0], it[1]))
    return stream


def split_chunks(items, head_slots):
    """Identical MIN/FORCE chunking to DN/MN; items = [(comps, pl, en)]."""
    n = len(items)
    if n <= SEG_SPLIT:
        return [list(range(n))]

    def struct_edge(j):
        return j in head_slots or items[j][0][:-1] != items[j - 1][0][:-1]

    chunks, cur = [], []
    for i in range(n):
        if cur:
            if (i in head_slots and len(cur) >= MIN_CHUNK) or \
                    (len(cur) >= FORCE_CHUNK and struct_edge(i)):
                chunks.append(cur)
                cur = []
            elif len(cur) >= FORCE_CHUNK + 20:
                chunks.append(cur)
                cur = []
        cur.append(i)
    if cur:
        if len(cur) < 20 and chunks:
            chunks[-1].extend(cur)
        else:
            chunks.append(cur)
    return chunks


def file_list(sam: int):
    d = os.path.join(SRC, "root", "pli", "ms", "sutta", STEM, f"{STEM}{sam}")

    def num(f):
        m = re.match(rf"{STEM}{sam}\.(\d+)(?:-(\d+))?_", f)
        return int(m.group(1)), int(m.group(2) or m.group(1))
    return sorted(os.listdir(d), key=num)


def build_samyutta(sam: int, drops, stats):
    """Yield text/trans units for one saṃyutta + per-sam stats."""
    # group every segment of every file by stem-start (unit identity);
    # remember each stem's covered span for the structural check
    groups: dict[int, list] = {}
    stem_spans: set[tuple[int, int]] = set()
    for fname in file_list(sam):
        for st, segc, pl, en in load_file(sam, fname):
            groups.setdefault(st[1], []).append((segc, pl, en))
            stem_spans.add((st[1], st[2]))
    # structural check: merged stem spans must cover 1..max contiguously
    merged: list[list[int]] = []
    for a, b in sorted(stem_spans):
        if merged and a <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    if merged != [[1, merged[-1][1]]]:
        raise SystemExit(f"[pali-{STEM}] sn{sam}: span gaps {merged}")

    text_units, trans_units = [], []
    for start in sorted(groups):
        raw_segs = groups[start]
        stats["raw"] += len(raw_segs)
        items, head_slots, after_head = [], set(), False
        for segc, pl, en in raw_segs:
            if is_heading(segc):
                drops["headings"] += 1
                after_head = True
                continue
            if not pl:
                drops["empty"] += 1
                continue
            if PE_ONLY.match(pl):
                drops["pe"] += 1
                continue
            if after_head:
                head_slots.add(len(items))
                after_head = False
            items.append((segc, pl, en))
        kept = []
        for it in items:
            if is_colophon(it[1]):
                drops["colophons"] += 1
            else:
                kept.append(it)
        items = kept
        head_slots = {h for h in head_slots if h < len(items)}
        stats["kept"] += len(items)
        stats["mapped"] += sum(1 for _, _, e in items if e)
        chunks = split_chunks(items, head_slots)
        base = f"{STEM} {sam}.{start}"
        for ci, ch in enumerate(chunks):
            segs = [items[i] for i in ch]
            pali = re.sub(r"\s+", " ", " ".join(p for _, p, _ in segs)).strip()
            eng = re.sub(r"\s+", " ", " ".join(e for _, _, e in segs)).strip()
            ref = base if len(chunks) == 1 else f"{base}.{ci}"
            text_units.append({"ref": ref, "words": pali.split(),
                               "text": pali})
            trans_units.append({"ref": ref, "text": eng})
    return text_units, trans_units


REFKEY = re.compile(r"^sn (\d+)\.(\d+)(?:\.(\d+))?$")


def ref_key(ref: str):
    m = REFKEY.match(ref)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3) or -1))


def main() -> None:
    args = sys.argv[1:]
    want: list[int] = list(range(1, NSAM + 1))
    if args:
        want = []
        for a in args:
            lo, _, hi = a.partition("-")
            want.extend(range(int(lo), int(hi or lo) + 1))
        bad = [w for w in want if not 1 <= w <= NSAM]
        if bad:
            raise SystemExit(f"[pali-{STEM}] saṃyuttas out of range: {bad}")

    tp = os.path.join(HERE, "public", "data", "texts", "pali", f"{STEM}.json")
    ep = os.path.join(HERE, "public", "data", "trans",
                      f"pali-{STEM}-sujato.json")
    old_t = json.load(open(tp, encoding="utf-8")) if os.path.exists(tp) else None
    old_e = json.load(open(ep, encoding="utf-8")) if os.path.exists(ep) else None
    keep_t = [u for u in (old_t["units"] if old_t else [])
              if ref_key(u["ref"])[0] not in want]
    keep_e = [u for u in (old_e["units"] if old_e else [])
              if ref_key(u["ref"])[0] not in want]
    have = {ref_key(u["ref"])[:2] for u in keep_t}

    drops = {"headings": 0, "pe": 0, "colophons": 0, "empty": 0}
    stats = {"raw": 0, "kept": 0, "mapped": 0}
    new_t: list = []
    new_e: list = []
    per_sam: dict[int, int] = {}
    for sam in sorted(want):
        tu, eu = build_samyutta(sam, drops, stats)
        overlap = have & {ref_key(u["ref"])[:2] for u in tu}
        if overlap:
            raise SystemExit(f"[pali-{STEM}] sn{sam} would duplicate "
                             f"{sorted(overlap)[:5]}")
        new_t += tu
        new_e += eu
        per_sam[sam] = len(tu)

    text_units = sorted(new_t + keep_t, key=lambda u: ref_key(u["ref"]))
    trans_units = sorted(new_e + keep_e, key=lambda u: ref_key(u["ref"]))
    assert [u["ref"] for u in text_units] == [u["ref"] for u in trans_units]

    for path, obj in (
        (tp, {"workId": WORK_ID, "lang": "pi", "kind": "prose",
              "units": text_units}),
        (ep, {"workId": WORK_ID, "translator": "Bhikkhu Sujato", "year": 2018,
              "license": "CC0", "alignment": "segment-exact",
              "units": trans_units}),
    ):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False)

    align_cov = round(100 * stats["mapped"] / stats["kept"], 2) \
        if stats["kept"] else 100.0
    n_en = sum(1 for u in new_e if u["text"].strip())
    unit_cov = round(100 * n_en / len(new_e), 2) if new_e else 100.0
    biggest = max(len(u["words"]) for u in text_units)
    table = " ".join(f"{s}:{per_sam[s]}" for s in sorted(per_sam))
    print(f"[pali-{STEM}] saṃyuttas {want[0]}-{want[-1]}: "
          f"+{sum(per_sam.values())} units ({n_en} with EN = {unit_cov}%; "
          f"total now {len(text_units)}), "
          f"raw {stats['raw']} -> kept {stats['kept']} (drops {drops}), "
          f"segment EN coverage {stats['mapped']}/{stats['kept']} = "
          f"{align_cov}% (key match 100%), max unit {biggest} words")
    print(f"[pali-{STEM}] per-sam: {table}")
    print(f"[pali-{STEM}] first={text_units[0]['ref']!r} "
          f"last={text_units[-1]['ref']!r}")

    # --- spot checks ------------------------------------------------------
    def unit_text(ref, units):
        return next((u["text"] for u in units if u["ref"] == ref), "")

    if 1 in per_sam:
        t = unit_text("sn 1.1", trans_units).lower()
        p = unit_text("sn 1.1", text_units).lower()
        assert "flood" in t and "ogha" in p, "sn 1.1 Oghataraṇa"
    if 56 in per_sam:
        t = unit_text("sn 56.11", trans_units).lower()
        p = unit_text("sn 56.11", text_units).lower()
        assert "wheel" in t and "dhammacakka" in p, "sn 56.11 Dhammacakka"
        assert "deer park" in t or "isipatana" in t, "sn 56.11 opening"
    print(f"[pali-{STEM}] done")


if __name__ == "__main__":
    main()
