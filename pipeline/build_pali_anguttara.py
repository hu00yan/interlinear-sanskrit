#!/usr/bin/env python3
"""Build Aṅguttara Nikāya (11 nipātas) from SuttaCentral's bilara-data (CC0).
Mirrors pipeline/build_pali_nikaya.py (dn/mn) output schema exactly:

  public/data/texts/pali/an.json            — Pali root (Mahāsaṅgīti ms)
  public/data/trans/pali-an-sujato.json     — Bhikkhu Sujato English

AN differences from dn/mn, handled here:
  * bilara stores AN in RANGE-GROUPED files (`an1.1-10_…` holds suttas
    1.1–1.10; peyyāla repeat-groups collapse hundreds of nominal suttas into
    ONE entry keyed `an6.170-649:` …). Unit granularity therefore follows the
    bilara structure itself: ONE KEY PREFIX = ONE UNIT, ref `an <nip>.<sutta>`
    (range prefixes keep SC's own range form, e.g. `an 6.170-649`).
  * >150-segment splits append `.0`, `.1`, … exactly as in dn/mn
    (`an 3.70.0`), cutting at canonical X.0 section headings / paragraph
    edges (SEG_SPLIT/MIN_CHUNK/FORCE_CHUNK unchanged).
  * same editorial drops (headings incl. nikāya/sutta titles, bare …pe…,
    empty-Pali segments, short unquoted niṭṭhitaṁ/samattaṁ colophons —
    counted per batch); empty-EN kept (peyyāla elisions).
  * incremental: CLI takes NIPĀTA specs (`1`, `4-5` …). Requested nipātas are
    rebuilt from source and MERGED into any existing output files, so batches
    can be committed one nipāta at a time.

Usage: build_pali_anguttara.py [SPEC [SPEC …]]   # default: all 11 nipātas
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# BILARA_SRC lets a batch pin a private snapshot of the an trees, immune to
# concurrent sparse-checkout churn from other builders sharing the cache.
SRC = os.environ.get("BILARA_SRC") or os.path.join(HERE, ".cache-bilara",
                                                   "bilara-data")
STEM, WID = "an", "pali-anguttara-nikaya"
SEG_SPLIT, MIN_CHUNK, FORCE_CHUNK = 150, 60, 160

COMP = re.compile(r"\d+(?:-\d+)?")
PE_ONLY = re.compile(r'^[\s“"‘]*…\s*pe\s*…[\s”"’]*$')
QUOTED = re.compile(r'[“”‘’"?]')
MARKERS = {"niṭṭhitaṁ", "niṭṭhitā", "niṭṭhito"}


def is_colophon(pl: str) -> bool:
    """Identical rule to build_pali_nikaya.py."""
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


def natkey(ref: str) -> tuple[int, ...]:
    """Natural sort key over the numeric components of a unit ref."""
    return tuple(int(t.split("-")[0]) for t in COMP.findall(ref))


def load_entries(nip: int, drops):
    """All entries of one nipāta -> [(ref_body, items, head_slots)], where
    items = sorted [(start_comps, pali, en)] kept segments.
    NB: AN nests one level deeper than dn/mn: sutta/an/an<nip>/<files>."""
    out = []
    pat = os.path.join(SRC, "root", "pli", "ms", "sutta", "an", f"an{nip}",
                       f"an{nip}.*_root-pli-ms.json")
    files = sorted(glob.glob(pat),
                   key=lambda f: natkey(os.path.basename(f)))
    if not files:
        raise SystemExit(f"[pali-{STEM}] no source files for nipāta {nip}")
    for rpath in files:
        tpath = rpath.replace(
            os.path.join("root", "pli", "ms"),
            os.path.join("translation", "en", "sujato")).replace(
            "_root-pli-ms.json", "_translation-en-sujato.json")
        assert os.path.exists(tpath), f"missing translation {tpath}"
        root = json.load(open(rpath, encoding="utf-8"))
        trans = json.load(open(tpath, encoding="utf-8"))
        if sorted(root) != sorted(trans):
            raise SystemExit(f"[pali-{STEM}] key mismatch in "
                             f"{os.path.basename(rpath)}")
        # group segments by sutta key prefix (`an6.54:…`), ordered by first comp
        groups: dict[str, list] = {}
        for k, p in root.items():
            groups.setdefault(k.split(":", 1)[0], []).append(k)
        for pref in sorted(groups, key=lambda p: comps(groups[p][0])):
            body = pref[len(f"an{nip}") + 1:]  # 'an6.170-649' -> '170-649'
            stream = []
            for k in groups[pref]:
                c = comps(k)
                pl, en = root[k].strip(), (trans.get(k) or "").strip()
                stream.append((is_heading(c), PE_ONLY.match(pl) is not None,
                               not pl, c, pl, en))
            stream.sort(key=lambda it: it[3])
            items, head_slots, after_head = [], set(), False
            for head, pe, empty, c, pl, en in stream:
                if head or empty:
                    if head:
                        drops["headings"] += 1  # titles + numbered section heads
                        after_head = True
                    else:
                        drops["empty"] += 1
                    continue
                if pe:
                    drops["pe"] += 1            # bare …pe… abbreviation markers
                    continue
                if after_head:
                    head_slots.add(len(items))
                    after_head = False
                items.append((c, pl, en))
            # colophons dropped whether or not translated (edition marginalia)
            kept = []
            for it in items:
                if is_colophon(it[1]):
                    drops["colophons"] += 1
                else:
                    kept.append(it)
            items = kept
            head_slots = {h for h in head_slots if h < len(items)}
            out.append((body, items, head_slots))
    return out


def split_chunks(items, head_slots):
    """Identical MIN/FORCE chunking to build_pali_nikaya.py."""
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
                chunks.append(cur)        # hard stop at a sentence boundary
                cur = []
        cur.append(i)
    if cur:
        if len(cur) < 20 and chunks:      # absorb tiny tail fragment
            chunks[-1].extend(cur)
        else:
            chunks.append(cur)
    return chunks


def merge(path: str, fresh: dict[str, dict], wanted: set[int]):
    """Merge freshly built units (keyed by ref) into an existing output
    file, replacing every unit whose nipāta is in `wanted`."""
    old = {}
    if os.path.exists(path):
        old = {u["ref"]: u for u in json.load(open(path))["units"]
               if int(re.findall(r"\d+", u["ref"])[0]) not in wanted}
    merged = dict(old)
    merged.update(fresh)
    return sorted(merged.values(), key=lambda u: natkey(u["ref"]))


def main() -> None:
    specs = sys.argv[1:] or ["1-11"]
    want: list[int] = []
    for sp in specs:
        a, _, b = sp.partition("-")
        want.extend(range(int(a), int(b or a) + 1))

    drops = {"headings": 0, "pe": 0, "colophons": 0, "empty": 0}
    raw = kept = mapped = 0
    text_fresh, trans_fresh = {}, {}
    entries_total = 0
    for nip in want:
        for body, items, head_slots in load_entries(nip, drops):
            entries_total += 1
            kept += len(items)
            mapped += sum(1 for _, _, e in items if e)
            chunks = split_chunks(items, head_slots)
            for ci, ch in enumerate(chunks):
                segs = [items[i] for i in ch]
                pali = re.sub(r"\s+", " ", " ".join(p for _, p, _ in segs)).strip()
                eng = re.sub(r"\s+", " ", " ".join(e for _, _, e in segs)).strip()
                base_ref = f"{STEM} {nip}.{body}"
                ref = base_ref if len(chunks) == 1 else f"{base_ref}.{ci}"
                text_fresh[ref] = {"ref": ref, "words": pali.split(),
                                   "text": pali}
                trans_fresh[ref] = {"ref": ref, "text": eng}
        for f in glob.glob(os.path.join(SRC, "root", "pli", "ms", "sutta",
                                        "an", f"an{nip}",
                                        "an*_root-pli-ms.json")):
            raw += len(json.load(open(f, encoding="utf-8")))

    text_path = os.path.join(HERE, "public", "data", "texts", "pali",
                             f"{STEM}.json")
    trans_path = os.path.join(HERE, "public", "data", "trans",
                              f"pali-{STEM}-sujato.json")
    wanted = set(want)
    text_units = merge(text_path, text_fresh, wanted)
    trans_units = merge(trans_path, trans_fresh, wanted)

    assert len(text_units) == len(trans_units), "text/trans unit drift"
    assert {u["ref"] for u in text_units} == \
           {u["ref"] for u in trans_units}, "ref set mismatch"

    for path, obj in (
        (text_path,
         {"workId": WID, "lang": "pi", "kind": "prose", "units": text_units}),
        (trans_path,
         {"workId": WID, "translator": "Bhikkhu Sujato", "year": 2018,
          "license": "CC0", "alignment": "segment-exact",
          "units": trans_units}),
    ):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False)

    align_cov = round(100 * mapped / kept, 2)
    # Segment-key alignment is asserted == 100% per file above (sorted keys
    # equal) and via ref-set equality below; like dn/mn, EN *coverage* runs
    # lower where Sujato elides verbatim repeat formulas (~88% here).
    assert align_cov >= 70.0, f"EN coverage {align_cov}% collapsed, batch {want}"
    n_split = sum(1 for r in text_fresh if r.split()[1].count(".") >= 2)
    biggest = max(len(u["words"]) for u in text_units)
    print(f"[pali-{STEM}] nipātas {want}: {entries_total} entries -> "
          f"{len(text_fresh)} units ({n_split} sub-units), total file now "
          f"{len(text_units)} units; raw {raw} -> kept {kept} (drops {drops}), "
          f"EN coverage {mapped}/{kept} = {align_cov}% (key match 100%), "
          f"max unit {biggest} words")

    def unit_text(units, ref):
        return next(u["text"] for u in units if u["ref"] == ref)

    # --- spot checks ------------------------------------------------------
    if 1 in wanted:
        assert unit_text(trans_units, "an 1.1").startswith("So I have heard"), \
            "an 1.1 opening"
        assert "ekaṁ samayaṁ bhagavā sāvatthiyaṁ" in \
            unit_text(text_units, "an 1.1"), "an 1.1 pali opening"
    if 5 in wanted:
        for su in ("an 5.77", "an 5.88"):
            assert su in {u["ref"] for u in text_units}, f"{su} present"
        assert len(unit_text(text_units, "an 5.77")) > 200, "an 5.77 body"
    if 10 in wanted:
        assert len(unit_text(text_units, "an 10.1").split()) > 100, \
            "an 10.1 famous list body"
    print(f"[pali-{STEM}] first={text_units[0]['ref']!r} "
          f"last={text_units[-1]['ref']!r}")
    print(f"[{WID}] done")


if __name__ == "__main__":
    main()
