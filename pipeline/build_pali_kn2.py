#!/usr/bin/env python3
"""Build the REMAINING Khuddaka Nikāya books (wave 2) from SuttaCentral's
bilara-data (CC0). Mirrors pipeline/build_pali_kn_books.py (EN-aligned books)
and pipeline/build_pali_abhidhamma.py (text-only books) output schemas:

  public/data/texts/pali/<stem>.json          — Pali root (Mahāsaṅgīti ms)
  public/data/trans/pali-<stem>-<tr>.json     — EN translation where upstream

Books (bilara uid prefix -> file stem):
  kp  khuddakapatha    《小诵经》   EN sujato full (9 files)
  vv  vimanavatthu     《天宫事》   text-only (85 stories)
  pv  petavatthu       《饿鬼事》   text-only (51 stories)
  cp  cariyapitaka     《所行藏》   EN sujato full (35)
  bv  buddhavamsa      《佛种姓》   text-only (29 chapters)
  mnd mahaniddesa      《大义释》   text-only (16)
  cnd culaniddesa      《小义释》   text-only (23)
  ps  patisambhidamagga《无碍解道》 text-only (31, incl ps1.0 mātikā)
  ne  netti            《指导论》   text-only, 准canonical (37)
  pe  petakopadesa     《藏释》     text-only, 准canonical (9)
  mil milindapanha     《弥兰陀王问经》 EN kelly partial (100/248), 准canonical
  ja  jataka           《本生经》   EN sujato partial (83/547); batchable by
                                    nipāta: `build_pali_kn2.py ja:1-6`
  ap  apadana          《譬喻》     text-only (tha-ap 563 + thi-ap 40)

Unit granularity: ONE bilara file stem = ONE unit (`kp 3`, `vv 33`, `ja 547`,
`mil 3.1.1`, `tha-ap 392` …); units whose kept segment count exceeds SEG_SPLIT
(>150) subdivided `.0`, `.1`… at X.0/X.0.Y heading boundaries (identical
MIN/FORCE chunking to DN/MN/SN/Vinaya/Abhidhamma builders).

Drop rules —
  * ALIGNED files (EN counterpart exists): build_pali_kn_books rules — drop
    0-component headings (kept only as split slots), pali-without-EN segments
    (uddānas, closing counters "X jātakaṁ paṭhamaṁ."), short unquoted
    colophons ("… niṭṭhitā."). Keys asserted identical root↔EN per file.
  * TEXT-ONLY files: build_pali_abhidhamma rules — headings are CONTENT
    (story/chapter names kept) and double as split slots; drops limited to
    bare `…pe…` markers and colophons.

Bare-pe markers and colophon rule shared with all prior builders. Output
files guarded ≤8MB. Catalog: appends under the EXISTING "Pali Canon" group,
inserted after therigatha in canonical Khuddaka order.

Usage: build_pali_kn2.py [book|ja:N[-M]|ap] ...   # default = all (ja full)
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, ".cache-bilara", "bilara-data")
KN = os.path.join(SRC, "root", "pli", "ms", "sutta", "kn")
SEG_SPLIT, MIN_CHUNK, FORCE_CHUNK = 150, 60, 160

LICENSE_ROOT = "CC0 (SuttaCentral bilara-data Pali root text)"
EDITION = "SuttaCentral bilara-data root/pli/ms/sutta/kn (Mahāsaṅgīti Tipiṭaka)"

BOOKS = {
    # uid: stem, title, titleZh, kind, en=(edition_dir, translator), note
    "kp":  dict(stem="khuddakapatha", title="Khuddakapāṭha", zh="小诵经",
                kind="verse", tr=("sujato", "Bhikkhu Sujato")),
    "vv":  dict(stem="vimanavatthu", title="Vimānavatthu", zh="天宫事",
                kind="verse"),
    "pv":  dict(stem="petavatthu", title="Petavatthu", zh="饿鬼事",
                kind="verse"),
    "cp":  dict(stem="cariyapitaka", title="Cariyāpiṭaka", zh="所行藏",
                kind="verse", tr=("sujato", "Bhikkhu Sujato")),
    "bv":  dict(stem="buddhavamsa", title="Buddhavaṃsa", zh="佛种姓",
                kind="verse"),
    "mnd": dict(stem="mahaniddesa", title="Mahāniddesa", zh="大义释",
                kind="prose"),
    "cnd": dict(stem="culaniddesa", title="Cūḷaniddesa", zh="小义释",
                kind="prose"),
    "ps":  dict(stem="patisambhidamagga", title="Paṭisambhidāmagga",
                zh="无碍解道", kind="prose"),
    "ne":  dict(stem="netti", title="Netti", zh="指导论", kind="prose",
                note="准canonical (semi-canonical)"),
    "pe":  dict(stem="petakopadesa", title="Peṭakopadesa", zh="藏释",
                kind="prose", note="准canonical (semi-canonical)"),
    "mil": dict(stem="milindapanha", title="Milindapañha", zh="弥兰陀王问经",
                kind="prose", tr=("kelly", "John Kelly"),
                note="准canonical (semi-canonical)"),
    "ap":  dict(stem="apadana", title="Apadāna", zh="譬喻", kind="verse",
                prefixes=["tha-ap", "thi-ap"]),
    "ja":  dict(stem="jataka", title="Jātaka", zh="本生经", kind="verse",
                tr=("sujato", "Bhikkhu Sujato")),
}

# canonical Khuddaka order used to place catalog entries after therigatha
CANON_ORDER = ["pali-khuddakapatha", "pali-dhammapada", "pali-udana",
               "pali-itivuttaka", "pali-suttanipata", "pali-vimanavatthu",
               "pali-petavatthu", "pali-theragatha", "pali-therigatha",
               "pali-jataka", "pali-mahaniddesa", "pali-culaniddesa",
               "pali-patisambhidamagga", "pali-apadana", "pali-buddhavamsa",
               "pali-cariyapitaka", "pali-milindapanha", "pali-netti",
               "pali-petakopadesa"]

TRANSLATOR_YEAR = {"Bhikkhu Sujato": 2018}   # kelly: undated upstream

PE_ONLY = re.compile(r'^[\s“"‘]*…\s*pe\s*…[\s”"’]*$')
QUOTED = re.compile(r'[“”‘’"?]')
MARKERS = {"niṭṭhitaṁ", "niṭṭhitā", "niṭṭhito"}
COMP = re.compile(r"\d+(?:-\d+)?")
STEM_RE = re.compile(r"^([a-z-]+?)(\d+(?:\.\d+)*)$")


def is_colophon(pl: str) -> bool:
    """Same rule as DN/MN/SN/KN/Vinaya/Abhidhamma builders."""
    if QUOTED.search(pl):
        return False
    ws = pl.strip().rstrip(".").split()
    if not ws or len(ws) > 8:
        return False
    if any(i > 0 and w.lower() in MARKERS for i, w in enumerate(ws)):
        return True
    return ws[-1].lower() in ("samattaṁ", "samatto")


def comps(key: str) -> tuple[int, ...]:
    return tuple(int(t.split("-")[0]) for t in COMP.findall(key.split(":", 1)[1]))


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def sortkey(path: str):
    m = STEM_RE.match(os.path.basename(path).replace("_root-pli-ms.json", ""))
    if not m:
        raise SystemExit(f"[pali-kn2] unparsable stem in {path}")
    return [int(x.split("-")[0]) for x in m.group(2).split(".")]


def uid_ref(prefix: str, num: str) -> str:
    return f"{prefix} {num}"


def file_list(uid: str):
    base = os.path.join(KN, uid)
    return sorted((os.path.join(base, f) for f in os.listdir(base)
                   if f.endswith("_root-pli-ms.json")), key=sortkey)


def split_chunks(items, head_slots):
    """Identical MIN/FORCE chunking to build_pali_nikaya.py/abhidhamma."""
    n = len(items)
    if n <= SEG_SPLIT:
        return [list(range(n))]
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


def ja_nipata_of(headings: list[str], registry: dict) -> int:
    """Map a ja file's nipāta heading (its 0.2 segment) to an ordinal."""
    nip = next((h for h in headings if h.strip().endswith("nipāta")
                and "Jātaka" not in h), None)
    if nip is None:
        raise SystemExit(f"[pali-kn2:ja] no nipāta heading in {headings}")
    nip = clean(nip)
    if nip not in registry:
        registry[nip] = len(registry) + 1
    return registry[nip]


def build_book(uid: str, spec: dict, nip_filter=None, drops=None, stats=None):
    """-> (text_units, en_units, n_files_covered_by_en)."""
    prefixes = spec.get("prefixes", [uid])
    edir, etr = spec.get("tr", (None, None))
    ut: list[dict] = []
    ue: list[dict] = []
    en_files = 0
    registry: dict[str, int] = {}
    for prefix in prefixes:
        for rp in file_list(prefix):
            stem = os.path.basename(rp).split("_root-pli-ms")[0]
            m = STEM_RE.match(stem)
            base_ref = uid_ref(m.group(1), m.group(2))
            root = json.load(open(rp, encoding="utf-8"))
            tp = None
            if edir:
                cand = os.path.join(SRC, "translation", "en", edir, "sutta",
                                    "kn", prefix,
                                    stem + f"_translation-en-{edir}.json")
                if os.path.exists(cand):
                    tp = cand
            aligned = tp is not None
            trans = json.load(open(tp, encoding="utf-8")) if aligned else {}
            if aligned and sorted(root) != sorted(trans):
                raise SystemExit(f"[pali-kn2:{uid}] key mismatch in {stem}")
            if aligned:
                stats["en_files"] += 1
            raw = stats.get("raw", 0) + len(root)
            stats["raw"] = raw
            heads_txt = [clean(root[k]) for k in sorted(root)
                         if comps(k)[:1] == (0,)][:2]
            if uid == "ja":
                nip = ja_nipata_of(heads_txt, registry)
                if nip_filter and nip not in nip_filter:
                    continue
            items, head_slots, after_head = [], set(), False
            for k in sorted(root, key=comps):
                c = comps(k)
                pl = clean(root[k])
                en = clean(trans.get(k)) if aligned else ""
                if aligned:
                    if not pl and not en:
                        drops["empty"] += 1
                        continue
                    if any(x == 0 for x in c):        # heading → split slot
                        drops["headings"] += 1
                        after_head = True
                        continue
                    if pl and not en:                 # uddāna / counter
                        drops["no-en"] += 1
                        continue
                    if is_colophon(pl):
                        drops["colophons"] += 1
                        continue
                    if after_head:
                        head_slots.add(len(items))
                        after_head = False
                    items.append((c, True, pl, en))
                else:
                    if not pl:
                        drops["empty"] += 1
                        continue
                    if PE_ONLY.match(pl):
                        drops["pe"] += 1
                        continue
                    if is_colophon(pl):
                        drops["colophons"] += 1
                        continue
                    if any(x == 0 for x in c):        # heading kept as content
                        head_slots.add(len(items))
                    items.append((c, False, pl, en))
            stats["kept"] += len(items)
            chunks = split_chunks(items, head_slots)
            for ci, ch in enumerate(chunks):
                sel = [items[i] for i in ch]
                pali = clean(" ".join(it[2] for it in sel))
                eng = clean(" ".join(it[3] for it in sel))
                r = base_ref if len(chunks) == 1 else f"{base_ref}.{ci}"
                ut.append({"ref": r, "words": pali.split(), "text": pali})
                ue.append({"ref": r, "text": eng})
                stats["mapped"] += sum(1 for it in sel if it[3])
    return ut, ue


def update_catalog(uid: str, spec: dict, fnames: list[str], tnames,
                   n_units, align_note):
    cat = json.load(open(os.path.join(HERE, "public", "data", "catalog.json"),
                         encoding="utf-8"))
    grp = next(a for a in cat["authors"] if a.get("name") == "Pali Canon")
    wid = f"pali-{spec['stem']}"
    entry = {
        "id": wid, "title": spec["title"], "titleZh": spec["zh"],
        "urn": f"urn:pali:{wid}", "lang": "pi", "kind": spec["kind"],
        "license": LICENSE_ROOT, "files": fnames, "unitCount": n_units,
        "edition": EDITION,
    }
    if spec.get("note"):
        entry["note"] = spec["note"]
    if tnames:
        tr = {"translator": spec["tr"][1], "license": "CC0",
              "files": tnames}
        yr = TRANSLATOR_YEAR.get(spec["tr"][1])
        if yr:
            tr["year"] = yr
        if align_note:
            tr["alignment"] = align_note
        entry["translation"] = tr
    else:
        entry["translation"] = None
    grp["works"] = [w for w in grp["works"] if w["id"] != wid]
    idx_in_canon = {w: i for i, w in enumerate(CANON_ORDER)}
    a = idx_in_canon[wid]
    pos = None
    for i, w in enumerate(grp["works"]):
        wi = idx_in_canon.get(w["id"])
        if wi is None:
            continue
        if wi < a:
            pos = i + 1                    # after the latest preceding canon work
        elif wi > a and pos is None:
            pos = i                        # before the first following one
    if pos is None:
        raise SystemExit(f"[catalog] no canonical anchor for {wid}")
    grp["works"].insert(pos, entry)
    with open(os.path.join(HERE, "public", "data", "catalog.json"), "w",
              encoding="utf-8") as fh:
        fh.write(json.dumps(cat, ensure_ascii=False))
    print(f"[catalog] {wid}: unitCount={n_units} at pos {pos}")


def main() -> None:
    want = sys.argv[1:] or list(BOOKS)
    jobs: dict[str, set[int] | None] = {}
    for w in want:
        if ":" in w:
            bk, rng = w.split(":")
            sel: set[int] = set()
            for part in rng.split(","):
                if "-" in part:
                    lo, hi = part.split("-")
                    sel.update(range(int(lo), int(hi) + 1))
                else:
                    sel.add(int(part))
            jobs.setdefault(bk, set()).update(sel)
        else:
            jobs[w] = jobs.get(w)
    bad = [w for w in jobs if w not in BOOKS]
    if bad:
        raise SystemExit(f"[pali-kn2] unknown books: {bad}")

    for uid, nipf in jobs.items():
        spec = BOOKS[uid]
        drops = {"headings": 0, "no-en": 0, "colophons": 0, "empty": 0,
                 "pe": 0}
        stats = {"raw": 0, "kept": 0, "mapped": 0, "en_files": 0}
        ut, ue = build_book(uid, spec, nipf, drops, stats)
        refs = [u["ref"] for u in ut]
        assert refs and len(refs) == len(set(refs)), \
            f"[pali-kn2:{uid}] empty/dup refs"
        # every emitted unit must exist in both lists with same refs
        assert [u["ref"] for u in ue] == refs
        # spot checks ------------------------------------------------------
        def nbase(pref):
            return len({r.split()[1].split(".")[0] for r in refs
                        if r.startswith(pref + " ")})
        if uid == "ja" and (not nipf or 1 in nipf):
            j1 = next(u for u in ut if u["ref"] == "ja 1")
            assert "Apaṇṇakaṁ ṭhānameke" in j1["text"], "ja 1 opening verse"
            assert j1["text"].startswith("Namo tassa"), "ja 1 homage"
            j1e = next(u for u in ue if u["ref"] == "ja 1")
            assert j1e["text"].startswith("Homage"), "ja 1 EN homage"
        if uid == "vv":
            assert nbase("vv") == 85, f"vv 85 story files, got {nbase('vv')}"
        if uid == "pv":
            assert nbase("pv") == 51, f"pv 51 story files"
        if uid == "cp":
            assert nbase("cp") == 35, "cp 35"
        if uid == "bv":
            assert nbase("bv") == 29, "bv 29"
        if uid == "ap":
            assert nbase("tha-ap") == 563, \
                f"tha-ap 563, got {nbase('tha-ap')}"
            assert nbase("thi-ap") == 40, \
                f"thi-ap 40, got {nbase('thi-ap')}"

        # --- write --------------------------------------------------------
        stem = spec["stem"]
        tpath = os.path.join(HERE, "public", "data", "texts", "pali",
                             f"{stem}.json")
        with open(tpath, "w", encoding="utf-8") as fh:
            json.dump({"workId": f"pali-{stem}", "lang": "pi",
                       "kind": spec["kind"], "units": ut}, fh,
                      ensure_ascii=False)
        assert os.path.getsize(tpath) <= 8 * 1024 * 1024, f"{stem}.json >8MB"
        fnames = [f"texts/pali/{stem}.json"]
        tnames = None
        align_note = None
        ue_cov = [u for u in ue if u["text"]]     # refs actually translated
        if ue_cov:
            edir = spec["tr"][0]
            total_files = sum(len(file_list(p))
                              for p in spec.get("prefixes", [uid]))
            cov = f"{stats['en_files']}/{total_files}"
            align_note = ("segment-exact" if stats["en_files"] == total_files
                          else f"segment-exact where translated ({cov} files)")
            tf = os.path.join(HERE, "public", "data", "trans",
                              f"pali-{stem}-{edir}.json")
            with open(tf, "w", encoding="utf-8") as fh:
                hdr = {"workId": f"pali-{stem}",
                       "translator": spec["tr"][1], "license": "CC0",
                       "alignment": align_note}
                yr = TRANSLATOR_YEAR.get(spec["tr"][1])
                if yr:
                    hdr["year"] = yr
                json.dump({**hdr, "units": ue_cov}, fh,
                          ensure_ascii=False)
            tnames = [f"trans/pali-{stem}-{edir}.json"]
        elif uid in ("vv", "pv", "bv", "mnd", "cnd", "ps", "ne", "pe", "ap"):
            pass                                  # text-only by design
        else:
            raise SystemExit(f"[pali-kn2:{uid}] expected EN but none kept")
        update_catalog(uid, spec, fnames, tnames, len(ut),
                       align_note)

        cov_pct = round(100 * stats["mapped"] / stats["kept"], 1)
        biggest = max(len(u["words"]) for u in ut)
        nfiles = sum(len(file_list(p)) for p in spec.get("prefixes", [uid]))
        print(f"[pali-kn2:{uid}] {len(ut)} units from {nfiles} files "
              f"(raw {stats['raw']} -> kept {stats['kept']}, drops {drops}), "
              f"EN {stats['en_files']} files, coverage {cov_pct}%, "
              f"max unit {biggest}w, first={refs[0]!r} last={refs[-1]!r}, "
              f"{os.path.getsize(tpath)//1024}KB")
    print("[pali-kn2] done")


if __name__ == "__main__":
    main()
