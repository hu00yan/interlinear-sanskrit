#!/usr/bin/env python3
"""Build Dīgha Nikāya (34 suttas) + Majjhima Nikāya (152 suttas) from
SuttaCentral's bilara-data (CC0). Mirrors pipeline/build_pali_dhammapada.py
and pipeline/build_pali_kn_books.py output schema exactly:

  public/data/texts/pali/dn.json           — Pali root (Mahāsaṅgīti ms)
  public/data/trans/pali-dn-sujato.json    — Bhikkhu Sujato English
  public/data/texts/pali/mn.json           — idem, Majjhima
  public/data/trans/pali-mn-sujato.json

Unit granularity: ONE SUTTA = ONE UNIT (`dn 1` … `dn 34`; `mn 1` … `mn 152`),
EXCEPT suttas whose kept segment count exceeds SEG_SPLIT (>150): these are
subdivided into sub-units `dn 16.0`, `dn 16.1`, … Sub-unit boundaries:
  * canonical section breaks — every numbered internal heading segment
    (`X.0` component, e.g. dn1:1.0 "1. Paribbājakakathā"), taken only when the
    open chunk already holds >= MIN_CHUNK segments;
  * plus a hard cap: any chunk reaching > FORCE_CHUNK (>160) segments is cut
    at the nearest paragraph boundary (change of first key component).
Sub-index is a plain ordinal from 0 (MN suttas mostly carry no canonical
internal headings, so mechanical paragraph cuts fill the gap).

Key shapes handled: `dn1:1.2.3`, range merges `mn10:18-23.1`,
`dn10:1.12.1-1.27` (sort by START components; root/translation share ids —
verified equal at build time, so alignment stays segment-exact).

Editorial drops (counted, printed per nikāya):
  * heading segments (any `0` component) — nikāya/sutta titles + numbered
    internal section headings;
  * bare peyyāla markers (whole segment is just `…pe…`) — abbreviation signs,
    never rendered by SC either;
  * closing colophons — short unquoted completion markers ("Xsuttaṁ
    niṭṭhitaṁ paṭhamaṁ.", "Sīlakkhandhavaggapāḷi niṭṭhitā.",
    "Mūlapaṇṇāsakaṁ samattaṁ.", "dīghanikāyo samatto."), dropped with or
    without a translation (edition marginalia, incl. internal enders like
    "Cūḷasīlaṁ niṭṭhitaṁ." and mn1's nayabhūmiparicchedo lines);
DEVIATION from the KN builders: segments whose Pali is real text but whose
Sujato translation is EMPTY are KEPT (≈12–15% here vs 77 corpus-wide in KN).
These are verbatim repeat formulas Sujato elides after first occurrence (SC
renders them Pali-only); dropping them would corrupt the root text. Homage
lines ("namo tassa …") inside DN21/MN27/87/91/100 carry full translations and
are narrative content — kept. Alignment below therefore reports BOTH the
structural key-match (always 100%) and EN coverage of kept segments.

Usage: build_pali_nikaya.py [dn A-B] [mn C-D]   # inclusive sutta ranges;
       default = full canon (dn 1-34, mn 1-152).
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, ".cache-bilara", "bilara-data")
SEG_SPLIT, MIN_CHUNK, FORCE_CHUNK = 150, 60, 160

NIK = {
    "dn": dict(stem="dn", title="Dīgha Nikāya", expect=34),
    "mn": dict(stem="mn", title="Majjhima Nikāya", expect=152),
}

COMP = re.compile(r"\d+(?:-\d+)?")
PE_ONLY = re.compile(r'^[\s“"‘]*…\s*pe\s*…[\s”"’]*$')
QUOTED = re.compile(r'[“”‘’"?]')
MARKERS = {"niṭṭhitaṁ", "niṭṭhitā", "niṭṭhito"}


def is_colophon(pl: str) -> bool:
    """Short unquoted completion marker: "X niṭṭhitaṁ [ordinal]." /
    "…paṇṇāsakaṁ samattaṁ." / "majjhimanikāyo samatto.". Narrative words
    like sentence-initial niṭṭhitacīvaro (mn65) never match."""
    if QUOTED.search(pl):
        return False
    ws = pl.strip().rstrip(".").split()
    if not ws or len(ws) > 8:
        return False
    if any(i > 0 and w.lower() in MARKERS for i, w in enumerate(ws)):
        return True
    return ws[-1].lower() in ("samattaṁ", "samatto")


def comps(key: str) -> tuple[int, ...]:
    """Start components of a (possibly range) segment id, as ints."""
    return tuple(int(t.split("-")[0]) for t in COMP.findall(key.split(":", 1)[1]))


def is_heading(c: tuple[int, ...]) -> bool:
    return any(x == 0 for x in c)


def load_sutta(nik, n, drops):
    """-> (items, head_slots): sorted [(start_comps, pali, en)] kept segments,
    plus indexes that open right after a canonical section heading."""
    base = os.path.join(SRC, "root", "pli", "ms", "sutta", nik)
    tdir = os.path.join(SRC, "translation", "en", "sujato", "sutta", nik)
    rpath = os.path.join(base, f"{nik}{n}_root-pli-ms.json")
    tpath = os.path.join(tdir, f"{nik}{n}_translation-en-sujato.json")
    if not os.path.exists(rpath):
        return None
    root = json.load(open(rpath, encoding="utf-8"))
    trans = json.load(open(tpath, encoding="utf-8"))
    if sorted(root) != sorted(trans):
        raise SystemExit(f"[pali-{nik}] key mismatch in {nik}{n}")
    stream = []
    for k, p in root.items():
        c = comps(k)
        pl, en = p.strip(), (trans.get(k) or "").strip()
        stream.append((is_heading(c), PE_ONLY.match(pl) is not None,
                       not pl, c, pl, en))
    stream.sort(key=lambda it: it[3])
    items, head_slots, after_head = [], set(), False
    for head, pe, empty, c, pl, en in stream:
        if head or empty:
            if head:
                drops["headings"] += 1   # titles + numbered section heads
                after_head = True
            else:
                drops["empty"] += 1
            continue
        if pe:
            drops["pe"] += 1             # bare …pe… abbreviation markers
            continue
        if after_head:
            head_slots.add(len(items))
            after_head = False
        items.append((c, pl, en))
    # colophons: "…niṭṭhitaṁ …." / "… samattaṁ." completion markers —
    # dropped whether or not Sujato translated them (edition marginalia,
    # cf. the KN builders' niṭṭhitā rule). Covers sutta enders, vagga/
    # paṇṇāsaka enders, bhāṇavāra marks and mn1's division summaries.
    kept = []
    for it in items:
        if is_colophon(it[1]):
            drops["colophons"] += 1
        else:
            kept.append(it)
    items = kept
    head_slots = {h for h in head_slots if h < len(items)}
    return items, head_slots


def split_chunks(items, head_slots):
    """Apply MIN/FORCE chunking; returns lists of kept-segment indexes."""
    n = len(items)
    if n <= SEG_SPLIT:
        return [list(range(n))]

    def struct_edge(j):
        """Cutting before j lands on a parent-numbering change."""
        return j in head_slots or items[j][0][:-1] != items[j - 1][0][:-1]

    chunks, cur = [], []
    for i in range(n):
        if cur:
            if (i in head_slots and len(cur) >= MIN_CHUNK) or \
                    (len(cur) >= FORCE_CHUNK and struct_edge(i)):
                chunks.append(cur)
                cur = []
            elif len(cur) >= FORCE_CHUNK + 20:
                chunks.append(cur)        # hard stop at a sentence boundary
                cur = []
        cur.append(i)
    if cur:
        if len(cur) < 20 and chunks:      # absorb tiny tail fragment
            chunks[-1].extend(cur)
        else:
            chunks.append(cur)
    return chunks


def main() -> None:
    args = sys.argv[1:]
    # default: full canon; explicit pairs restrict BOTH range and which
    # nikāyas get written (for incremental batch commits).
    want: dict[str, tuple[int, int]] = {"dn": (1, 34), "mn": (1, 152)}
    if args:
        want = {}
        for i in range(0, len(args), 2):
            nik, rng = args[i], args[i + 1]
            if nik not in NIK:
                raise SystemExit(f"[pali-nikaya] unknown nikāya {nik}")
            a, b = rng.split("-")
            want[nik] = (int(a), int(b))

    for nik, (lo, hi) in want.items():
        meta = NIK[nik]
        drops = {"headings": 0, "pe": 0, "colophons": 0, "empty": 0}
        raw = kept = mapped = 0
        text_units, trans_units, sutta_of_unit = [], [], {}
        for n in range(lo, hi + 1):
            loaded = load_sutta(nik, n, drops)
            if loaded is None:
                raise SystemExit(f"[pali-{nik}] missing file {nik}{n}")
            items, head_slots = loaded
            with open(os.path.join(SRC, "root", "pli", "ms", "sutta",
                                   nik, f"{nik}{n}_root-pli-ms.json"),
                      encoding="utf-8") as fh:
                raw += len(json.load(fh))
            kept += len(items)
            mapped += sum(1 for _, _, e in items if e)
            chunks = split_chunks(items, head_slots)
            for ci, ch in enumerate(chunks):
                segs = [items[i] for i in ch]
                pali = re.sub(r"\s+", " ", " ".join(p for _, p, _ in segs)).strip()
                eng = re.sub(r"\s+", " ", " ".join(e for _, _, e in segs)).strip()
                ref = f"{nik} {n}" if len(chunks) == 1 else f"{nik} {n}.{ci}"
                text_units.append({"ref": ref, "words": pali.split(),
                                   "text": pali})
                trans_units.append({"ref": ref, "text": eng})
                sutta_of_unit[ref] = n

        # --- validation ---------------------------------------------------
        got = sorted(set(sutta_of_unit.values()))
        if got != list(range(lo, hi + 1)):
            missing = [x for x in range(lo, hi + 1) if x not in set(got)]
            raise SystemExit(f"[pali-{nik}] missing suttas {missing[:10]}")
        n_split = sum(1 for r in sutta_of_unit if "." in r.split()[1])
        align_cov = round(100 * mapped / kept, 2)

        for path, obj in (
            (os.path.join(HERE, "public", "data", "texts", "pali",
                          f"{meta['stem']}.json"),
             {"workId": f"pali-{meta['stem']}", "lang": "pi", "kind": "prose",
              "units": text_units}),
            (os.path.join(HERE, "public", "data", "trans",
                          f"pali-{meta['stem']}-sujato.json"),
             {"workId": f"pali-{meta['stem']}",
              "translator": "Bhikkhu Sujato", "year": 2018,
              "license": "CC0", "alignment": "segment-exact",
              "units": trans_units}),
        ):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(obj, fh, ensure_ascii=False)

        biggest = max(len(u["words"]) for u in text_units)
        print(f"[pali-{nik}] suttas {lo}-{hi}: {len(text_units)} units "
              f"({n_split} sub-units), raw {raw} -> kept {kept} "
              f"(drops {drops}), EN coverage {mapped}/{kept} = "
              f"{align_cov}% (key match 100%), max unit {biggest} words")
        print(f"[pali-{nik}] first={text_units[0]['ref']!r} "
              f"last={text_units[-1]['ref']!r}")

        # --- spot checks --------------------------------------------------
        def unit_text(ref, units):
            return next(u["text"] for u in units if u["ref"] == ref)
        if nik == "dn" and lo <= 1 <= hi:
            assert unit_text("dn 1" if "dn 1" in sutta_of_unit else "dn 1.0",
                             trans_units).startswith("So I have heard"), "dn1 opening"
        if nik == "mn" and lo <= 1 <= hi:
            ref = "mn 1" if "mn 1" in sutta_of_unit else "mn 1.0"
            assert "So I have heard" in unit_text(ref, trans_units), "mn1 opening"
            assert "differences arise" in unit_text(ref, trans_units) or \
                "underlying tendencies" in unit_text(ref, trans_units) or \
                len(unit_text(ref, trans_units)) > 5000, "mn1 body"
    print("[pali-nikaya] done")


if __name__ == "__main__":
    main()
