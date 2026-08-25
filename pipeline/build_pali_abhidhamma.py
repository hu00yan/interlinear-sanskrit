#!/usr/bin/env python3
"""Build the Abhidhamma Piṭaka (7 treatises, 1,102 bilara files) from SuttaCentral's
bilara-data (CC0). Mirrors pipeline/build_pali_sn.py output schema:

  public/data/texts/pali/abhidhamma-<tid>.json          — Pali root (Mahāsaṅgīti ms)
      (Paṭṭhāna split: abhidhamma-patthana-part01..03.json, each ≤8MB)

EN translations are ABSENT upstream (no translation/en/*/abhidhamma tree), so these
are TEXT-ONLY works — catalog entries carry "translation": null exactly like the
Bhāgavatapurāṇa skandhas. No trans files are produced.

Unit granularity: ONE bilara file stem = ONE unit (ref = stem with a space:
`ds 1.1`, `vb 3`, `kv 12.4`, `ya 10.2.1`, `patthana 24.2`); units whose kept
segment count exceeds SEG_SPLIT (>150) are subdivided `.0`, `.1`, … at mātikā
heading boundaries (same MIN/FORCE chunking as DN/MN/SN).

Unlike the suttas, abhidhamma mātikā/heading segments (any `0` component) are
CONTENT and are KEPT ("Tikamātikä", "1. Kusalattika", "2.1 Cittuppādakaṇḍa"…).
Drops limited to: bare `…pe…` markers, short unquoted colophons ("X niṭṭhitaṁ.",
"…samattaṁ." — identical rule to DN/MN/SN). Debate replies like kv "Āmantā." stay.

Edition markup: PTS paragraph cross-refs "(<b>1, 363, 985, 1384</b>)" in the
mātikā are editorial apparatus → removed whole; remaining inline <b> terms are
unwrapped to plain text.

Batching: `build_pali_abhidhamma.py [tid ...]` (ds vb dt pp kv ya patthana);
default all. Also refreshes public/data/catalog.json: appends ONE work per
built treatise under the existing "Pali Canon" group.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, ".cache-bilara", "bilara-data")
ROOTDIR = os.path.join(SRC, "root", "pli", "ms", "abhidhamma")
SEG_SPLIT, MIN_CHUNK, FORCE_CHUNK = 150, 60, 160

# id, title, titleZh (standard 汉译名)
TREATISES = [
    ("ds", "Dhammasaṅgaṇī", "法聚论"),
    ("vb", "Vibhaṅga", "分别论"),
    ("dt", "Dhātukathā", "界论"),
    ("pp", "Puggalapaññatti", "人施设论"),
    ("kv", "Kathāvatthu", "论事"),
    ("ya", "Yamaka", "双论"),
    ("patthana", "Paṭṭhāna", "发趣论"),
]
WORK_ID = {t[0]: f"pali-abhidhamma-{t[0]}" for t in TREATISES}
LICENSE = "CC0 (SuttaCentral bilara-data Pali root text)"
EDITION = ("SuttaCentral bilara-data root/pli/ms/abhidhamma "
           "(Mahāsaṅgīti Tipiṭaka)")

PE_ONLY = re.compile(r'^[\s“"‘]*…\s*pe\s*…[\s”"’]*$')
QUOTED = re.compile(r'[“”‘’"?]')
MARKERS = {"niṭṭhitaṁ", "niṭṭhitā", "niṭṭhito"}
PTS_REF = re.compile(r"\s*\(<b>[^<]*</b>\)")
ANY_TAG = re.compile(r"</?b>")
COMP = re.compile(r"\d+(?:-\d+)?")
STEM_RE = re.compile(r"^([a-z]+)([\d.]+)$")


def is_colophon(pl: str) -> bool:
    """Same rule as DN/MN/SN builders: short unquoted completion marker."""
    if QUOTED.search(pl):
        return False
    ws = pl.strip().rstrip(".").split()
    if not ws or len(ws) > 8:
        return False
    if any(i > 0 and w.lower() in MARKERS for i, w in enumerate(ws)):
        return True
    return ws[-1].lower() in ("samattaṁ", "samatto")


def clean(text: str) -> str:
    t = PTS_REF.sub("", text)          # drop PTS paragraph cross-refs
    t = ANY_TAG.sub("", t)             # unwrap inline bold
    return re.sub(r"\s+", " ", t).strip()


def sortkey(fname: str):
    m = STEM_RE.match(fname.replace("_root-pli-ms.json", ""))
    parts = m.group(2).split(".")
    return [int(x) for x in parts]


def file_list(tid: str):
    """All root json paths under treatise dir (flat vb or nested ds/dt/pp/kv/ya/
    patthana dirs), naturally sorted by numeric stem."""
    base = os.path.join(ROOTDIR, tid)
    out = []
    for dirpath, _dirs, files in os.walk(base):
        for f in files:
            if f.endswith("_root-pli-ms.json"):
                out.append(os.path.join(dirpath, f))
    return sorted(out, key=lambda p: sortkey(os.path.basename(p)))


def ref_of(stem: str):
    m = STEM_RE.match(stem)
    return f"{m.group(1)} {m.group(2)}"


def load_file(path: str):
    """-> [(suffix_comps, cleaned_text)] in canonical order."""
    d = json.load(open(path, encoding="utf-8"))
    stems = {k.split(":")[0] for k in d}
    if len(stems) != 1:
        raise SystemExit(f"[pali-abhi] mixed stems in {path}: {stems}")
    stream = []
    for k, v in d.items():
        comps = tuple(int(t.split("-")[0]) for t in COMP.findall(k.split(":")[1]))
        stream.append((comps, v))
    stream.sort(key=lambda it: it[0])
    return stream


def split_chunks(items, head_slots):
    """Identical MIN/FORCE chunking to DN/MN/SN; items = [(comps, txt)];
    break candidates = mātikā heading segments (any 0 component)."""
    n = len(items)
    if n <= SEG_SPLIT:
        return [list(range(n))]

    def struct_edge(j):
        return j in head_slots

    chunks, cur = [], []
    for i in range(n):
        if cur:
            if (i in head_slots and len(cur) >= MIN_CHUNK) or \
                    len(cur) >= FORCE_CHUNK + 20:
                chunks.append(cur)
                cur = []
        cur.append(i)
    if cur:
        if len(cur) < 20 and chunks:
            chunks[-1].extend(cur)
        else:
            chunks.append(cur)
    return chunks


def build_treatise(tid: str, drops, stats):
    files = file_list(tid)
    if not files:
        raise SystemExit(f"[pali-abhi] no files for {tid}")
    text_units = []
    for path in files:
        stem = os.path.basename(path).split("_root-pli-ms")[0]
        raw = load_file(path)
        stats["raw"] += len(raw)
        items, head_slots = [], set()
        for comps, v in raw:
            pl = clean(v)
            if not pl:
                drops["empty"] += 1
                continue
            if PE_ONLY.match(pl):
                drops["pe"] += 1
                continue
            if is_colophon(pl):
                drops["colophons"] += 1
                continue
            if any(c == 0 for c in comps):   # heading kept as content,
                head_slots.add(len(items))    # but marks a split point
            items.append((comps, pl))
        stats["kept"] += len(items)
        base_ref = ref_of(stem)
        chunks = split_chunks(items, head_slots)
        for ci, ch in enumerate(chunks):
            pali = " ".join(items[i][1] for i in ch).strip()
            ref = base_ref if len(chunks) == 1 else f"{base_ref}.{ci}"
            text_units.append({"ref": ref, "words": pali.split(), "text": pali})
    return text_units


def write_work(tid: str, units, drops, stats):
    wid = WORK_ID[tid]
    if tid == "patthana":
        # split into parts by book: 1 | 2 | 3-24 (each part ≤8MB on disk)
        groups = {"part01": range(1, 2), "part02": range(2, 3),
                  "part03": range(3, 25)}
        fnames, written = [], 0
        for part, books in groups.items():
            sel = [u for u in units
                   if int(u["ref"].split()[1].split(".")[0]) in books]
            fname = f"abhidhamma-patthana-{part}.json"
            path = os.path.join(HERE, "public", "data", "texts", "pali", fname)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"workId": wid, "lang": "pi", "kind": "prose",
                           "units": sel}, fh, ensure_ascii=False)
            fnames.append(f"texts/pali/{fname}")
            written += os.path.getsize(path)
            assert os.path.getsize(path) <= 8 * 1024 * 1024, f"{fname} >8MB"
        print(f"[pali-abhi] patthana parts: {[f.split('/')[-1] for f in fnames]} "
              f"total {written/1e6:.1f}MB")
    else:
        fname = f"abhidhamma-{tid}.json"
        path = os.path.join(HERE, "public", "data", "texts", "pali", fname)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"workId": wid, "lang": "pi", "kind": "prose",
                       "units": units}, fh, ensure_ascii=False)
        assert os.path.getsize(path) <= 8 * 1024 * 1024, f"{fname} >8MB"
        fnames = [f"texts/pali/{fname}"]
    update_catalog(tid, fnames, len(units))
    biggest = max(len(u["words"]) for u in units)
    align_cov = round(100 * stats["kept"] / stats["raw"], 1) if stats["raw"] else 100
    print(f"[pali-abhi] {wid}: {len(units)} units, "
          f"raw {stats['raw']} -> kept {stats['kept']} ({align_cov}%; "
          f"drops {drops}), max unit {biggest} words, "
          f"first={units[0]['ref']!r} last={units[-1]['ref']!r}")


def update_catalog(tid: str, fnames, n_units):
    cp = os.path.join(HERE, "public", "data", "catalog.json")
    cat = json.load(open(cp, encoding="utf-8"))
    title, tzh = next((t[1], t[2]) for t in TREATISES if t[0] == tid)
    wid = WORK_ID[tid]
    entry = {
        "id": wid,
        "title": title,
        "titleZh": tzh,
        "urn": f"urn:pali:{wid}",
        "lang": "pi",
        "kind": "prose",
        "license": LICENSE,
        "files": fnames,
        "unitCount": n_units,
        "edition": EDITION,
        "translation": None,
    }
    grp = next(g for g in cat["authors"] if g.get("name") == "Pali Canon")
    grp["works"] = [w for w in grp["works"] if w["id"] != wid]
    idx = max((i for i, w in enumerate(grp["works"])
               if w["id"] in {f"pali-abhidhamma-{t}" for t, _, _ in TREATISES}),
              default=len(grp["works"]) - 1)
    grp["works"].insert(idx + 1, entry)
    with open(cp, "w", encoding="utf-8") as fh:
        json.dump(cat, fh, ensure_ascii=False)


def main() -> None:
    want = [t[0] for t in TREATISES]
    if sys.argv[1:]:
        want = sys.argv[1:]
    bad = [w for w in want if w not in WORK_ID]
    if bad:
        raise SystemExit(f"[pali-abhi] unknown treatise ids: {bad}")
    # EN translations absent upstream by design; verify once per run
    endir = os.path.join(SRC, "translation", "en")
    for tr in os.listdir(endir):
        p = os.path.join(endir, tr, "abhidhamma")
        if os.path.isdir(p):
            raise SystemExit(f"[pali-abhi] upstream now HAS en/{tr}/abhidhamma "
                             "— alignment work needed before shipping text-only")

    for tid in want:
        drops = {"empty": 0, "pe": 0, "colophons": 0}
        stats = {"raw": 0, "kept": 0}
        units = build_treatise(tid, drops, stats)
        refs = [u["ref"] for u in units]
        assert len(refs) == len(set(refs)), f"[pali-abhi] dup refs in {tid}"
        # spot checks -------------------------------------------------------
        joined = "\n".join(u["text"] for u in units)
        assert "<" not in joined, "[pali-abhi] leftover markup"
        if tid == "ds":
            first = units[0]["text"]
            assert first.startswith("Dhammasaṅgaṇī"), "ds opening title"
            assert "Kusalā dhammā." in first or \
                any(u["text"].startswith("Kusalā dhammā.") for u in units[:5]), \
                "ds mātikā kusalā dhammā"
            assert "Tikamātikā" in joined, "mātikā headings must be content"
        if tid == "kv":
            assert "Āmantā." in joined, "kv debate reply must be kept"
        if tid == "patthana":
            assert "Namo tassa Bhagavato" in joined, "patthana salutation"
        write_work(tid, units, drops, stats)
        # JSON round-trip ---------------------------------------------------
        for f in ([f"abhidhamma-{tid}.json"] if tid != "patthana" else
                  [f"abhidhamma-patthana-part0{i}.json" for i in (1, 2, 3)]):
            p = os.path.join(HERE, "public", "data", "texts", "pali", f)
            back = json.load(open(p, encoding="utf-8"))
            assert back["workId"] == WORK_ID[tid]
            assert [u["ref"] for u in back["units"]] == refs or tid == "patthana"
    print("[pali-abhi] done")


if __name__ == "__main__":
    main()
