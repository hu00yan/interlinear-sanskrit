#!/usr/bin/env python3
"""Build Vinaya Piṭaka (6 books) from SuttaCentral's bilara-data (CC0).
Mirrors pipeline/build_pali_nikaya.py (DN/MN) output schema exactly:

  public/data/texts/pali/vinaya-pj.json    — Pārājikapāḷi   《波罗夷》
        bu-vb pj(4)+ss(13)+aniyata/ay(2)+nissaggiya/np(30) = the first 49
        sikkhāpadas of the bhikkhu Pātimokkha (Thai-edition book division).
  public/data/texts/pali/vinaya-pc.json    — Pācittiyapāḷi  《波逸提》
        bu-vb pc(92)+pāṭidesanīya/pd(4)+sekhiya/sk(75)+
        adhikaraṇasamatha/as(7) = the remaining 178 sikkhāpadas (227 total,
        verified against the bilara tree: 4+13+2+30+92+4+75+7 files).
  public/data/texts/pali/vinaya-mv.json    — Mahāvagga      《大品》 kd 1–10
  public/data/texts/pali/vinaya-cv.json    — Cūḷavagga      《小品》 kd 11–22
  public/data/texts/pali/vinaya-pvr.json   — Parivāra       《附随》 51 chapters
  public/data/texts/pali/vinaya-bi.json    — Bhikkhunīvibhaṅga 《比丘尼分别》
        bi-vb tree AS FOUND UPSTREAM (partial): pj5-8, ss1-6+10-13, np1-12,
        pc1-96, pd1-8, sk1+75, as1-7. pj1-4 is a "~" cross-ref stub (rules
        in common with the monks) → yields no unit.

Unit granularity: ONE RULE / ONE KHANDHAKA CHAPTER / ONE PARIVĀRA chapter =
ONE UNIT (`pj 1`, `np 30`, `kd 15`, `pvr 3`, `bi-pc 91` …), EXCEPT units
whose kept segment count exceeds SEG_SPLIT (>150): subdivided into sub-units
`<ref>.0`, `<ref>.1`, … cut at canonical X.0 headings (>= MIN_CHUNK open),
hard cap FORCE_CHUNK(+20) at parent-numbering edges — identical mechanics to
build_pali_nikaya.py. Combined files (as1-7, bi ranges like pd2-8) are split
into per-rule units by their inner segment-id stems (pli-tv-bu-vb-asN:…).

Editorial drops (counted, printed per book) — nikāya-builder rules applied:
  * heading segments (any 0 component): title blocks (Theravāda Vinaya /
    Mahāvibhaṅga / kaṇḍa / rule titles) and numbered X.0.Y section heads;
    EXCEPTION: homage lines beginning "Namo tassa" are KEPT wherever they
    sit (full Brahmali translations — narrative opening);
  * bare abbreviation markers: whole-segment …pe… AND "~" (cross-ref stub);
  * closing colophons ("Mahākhandhako niṭṭhito.", "… samattaṁ.");
  * segments whose Pali is EMPTY but whose EN is a structural label
    ("Origin story", "Final ruling", "Non-offenses") — heading-equivalents.
DEVIATION (same as DN/MN): real-text segments whose Brahmali translation is
EMPTY are KEPT; alignment reports both structural key-match (100%, asserted
per file) and honest EN coverage of kept segments.

Pātimokkha recitation files (pli-tv-{bu,bi}-pm) are NOT shipped: their rule
texts all appear inside the shipped vibhaṅgas.

Usage: build_pali_vinaya.py [pj|pc|mv|cv|pvr|bi] ...   # default = all books
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, ".cache-bilara", "bilara-data")
SEG_SPLIT, MIN_CHUNK, FORCE_CHUNK = 150, 60, 160
VIN = os.path.join(SRC, "root", "pli", "ms", "vinaya")
TEN = os.path.join(SRC, "translation", "en", "brahmali", "vinaya")

BOOKS = {
    "pj": dict(file="vinaya-pj", title="Pārājika", titleZh="波罗夷"),
    "pc": dict(file="vinaya-pc", title="Pācittiya", titleZh="波逸提"),
    "mv": dict(file="vinaya-mv", title="Mahāvagga", titleZh="大品"),
    "cv": dict(file="vinaya-cv", title="Cūḷavagga", titleZh="小品"),
    "pvr": dict(file="vinaya-pvr", title="Parivāra", titleZh="附随"),
    "bi": dict(file="vinaya-bi", title="Bhikkhunīvibhaṅga",
               titleZh="比丘尼分别"),
}

COMP = re.compile(r"\d+(?:-\d+)?")
PE_ONLY = re.compile(r'^[\s“"‘]*…\s*pe\s*…[\s”"’]*$')
TILDE_ONLY = re.compile(r"^~\s*$")
QUOTED = re.compile(r'[“”‘’"?]')
MARKERS = {"niṭṭhitaṁ", "niṭṭhitā", "niṭṭhito"}
HOMAGE = "namo tassa"


def is_colophon(pl: str) -> bool:
    """Short unquoted completion marker (mirrors nikāya builder)."""
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


def load_pair(rel: str):
    """rel = path under vinaya root tree including _root-pli-ms suffix.
    Returns (root, trans) dicts; raises when EN side is missing or keys
    diverge (alignment stays segment-exact by construction)."""
    rp = os.path.join(VIN, rel)
    base = rel[:-len("_root-pli-ms.json")]
    tp = os.path.join(TEN, base + "_translation-en-brahmali.json")
    if not os.path.exists(rp):
        raise SystemExit(f"[pali-vin] missing root {rp}")
    if not os.path.exists(tp):
        raise SystemExit(f"[pali-vin] missing translation {tp}")
    root = json.load(open(rp, encoding="utf-8"))
    trans = json.load(open(tp, encoding="utf-8"))
    if sorted(root) != sorted(trans):
        raise SystemExit(f"[pali-vin] key mismatch in {rel}")
    return root, trans


def stream_items(root, trans, prefix=None, drops=None):
    """Yield kept items [(start_comps, pali, en)] for one rule-unit plus its
    head_slots (indexes opening right after a dropped canonical heading)."""
    stream = []
    for k, p in root.items():
        if prefix and not k.startswith(prefix + ":"):
            continue
        c = comps(k)
        pl, en = p.strip(), (trans.get(k) or "").strip()
        stream.append((pl.lower().startswith(HOMAGE), is_heading(c),
                       PE_ONLY.match(pl) is not None,
                       TILDE_ONLY.match(pl) is not None,
                       not pl, c, pl, en))
    stream.sort(key=lambda it: it[5])
    items, head_slots, after_head = [], set(), False
    for hom, head, pe, tilde, empty, c, pl, en in stream:
        if empty:
            if head:
                drops["headings"] += 1       # X.0 labels ("Origin story")
                after_head = True
            else:
                drops["empty"] += 1
            continue
        if hom:                              # homage line — narrative opener
            drops["homage_kept"] += 1        # (kept even though X.0.Y-shaped)
        elif pe:
            drops["pe"] += 1
            continue
        elif tilde:
            drops["tildes"] += 1             # "~" cross-ref stub marker
            continue
        elif head:
            drops["headings"] += 1
            after_head = True
            continue
        if after_head:
            head_slots.add(len(items))
            after_head = False
        items.append((c, pl, en))
    kept = [it for it in items if not is_colophon(it[1])]
    drops["colophons"] += len(items) - len(kept)
    return kept, {h for h in head_slots if h < len(kept)}


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
                chunks.append(cur)           # hard stop at sentence boundary
                cur = []
        cur.append(i)
    if cur:
        if len(cur) < 20 and chunks:
            chunks[-1].extend(cur)           # absorb tiny tail fragment
        else:
            chunks.append(cur)
    return chunks


def emit(units_text, units_en, ref, items, head_slots):
    chunks = split_chunks(items, head_slots)
    for ci, ch in enumerate(chunks):
        segs = [items[i] for i in ch]
        pali = re.sub(r"\s+", " ", " ".join(p for _, p, _ in segs)).strip()
        eng = re.sub(r"\s+", " ", " ".join(e for _, _, e in segs)).strip()
        r = ref if len(chunks) == 1 else f"{ref}.{ci}"
        units_text.append({"ref": r, "words": pali.split(), "text": pali})
        units_en.append({"ref": r, "text": eng})


def inner_stems(rel_root_json):
    """Sorted distinct id prefixes inside one root file (pli-tv-…-asN)."""
    stems = set()
    d = json.load(open(rel_root_json, encoding="utf-8")) \
        if isinstance(rel_root_json, str) else rel_root_json
    for k in d:
        stems.add(k.rsplit(":", 1)[0])
    return sorted(stems, key=lambda s: int(re.search(r"(\d+)$", s).group(1)))


def vb_rules(dirpath):
    """Per-rule entries for one vibhaṅga category dir:
    [(cat, num, full_rel_prefix)] — combined files expand via inner stems."""
    out = []
    absd = os.path.join(VIN, dirpath)
    for fn in sorted(os.listdir(absd)):
        if not fn.endswith("_root-pli-ms.json"):
            continue
        full = f"{dirpath}/{fn[:-len('_root-pli-ms.json')]}"
        r = json.load(open(os.path.join(absd, fn), encoding="utf-8"))
        for s in inner_stems(r):
            m = re.search(r"(?:^|-)([a-z]+)(\d+(?:-\d+)*)$", s)
            out.append((m.group(1), int(m.group(2).split("-")[0]), s, full))
    out.sort(key=lambda g: g[1])
    return out


def main() -> None:
    want = list(sys.argv[1:]) or list(BOOKS)
    for bk in want:
        if bk not in BOOKS:
            raise SystemExit(f"[pali-vin] unknown book {bk}")

    for bk in want:
        meta = BOOKS[bk]
        drops = {"headings": 0, "pe": 0, "colophons": 0, "empty": 0,
                 "tildes": 0, "homage_kept": 0, "stubs": 0, "rootless": 0}
        ut: list[dict] = []
        ue: list[dict] = []
        raw = kept = mapped = 0
        stats: dict[str, int] = {}

        def run_unit(full_prefixes, ref, restrict=None):
            """Load, drop, count, emit one logical unit."""
            nonlocal raw, kept, mapped
            root_all, trans_all = {}, {}
            for fp in dict.fromkeys(full_prefixes):
                r, t = load_pair(fp + "_root-pli-ms.json")
                root_all.update(r)
                trans_all.update(t)
            raw += len(root_all)
            items, hs = stream_items(root_all, trans_all, restrict, drops)
            if not items:
                if not any(p.strip() for p in root_all.values()) or \
                        (restrict and not any(
                            k.startswith(restrict + ":") and p.strip()
                            for k, p in root_all.items())):
                    drops["rootless"] += 1   # EN-only, no root Pali upstream
                else:
                    drops["stubs"] += 1      # "~" cross-ref stub
                return False
            kept += len(items)
            mapped += sum(1 for _, _, e in items if e)
            emit(ut, ue, ref, items, hs)
            return True

        # --- book-specific walkers ---------------------------------------
        if bk == "pj":
            cats = [("pj", "pli-tv-bu-vb/pli-tv-bu-vb-pj"),
                    ("ss", "pli-tv-bu-vb/pli-tv-bu-vb-ss"),
                    ("ay", "pli-tv-bu-vb/pli-tv-bu-vb-ay"),
                    ("np", "pli-tv-bu-vb/pli-tv-bu-vb-np")]
            for cat, dp in cats:
                rules = vb_rules(dp)
                stats[cat] = len(rules)
                assert [g[1] for g in rules] == list(range(1, len(rules) + 1)), \
                    f"{cat} numbering gap"
                for _, num, _stem, full in rules:
                    run_unit([full], f"{cat} {num}")
        elif bk == "pc":
            cats = [("pc", "pli-tv-bu-vb/pli-tv-bu-vb-pc"),
                    ("pd", "pli-tv-bu-vb/pli-tv-bu-vb-pd"),
                    ("sk", "pli-tv-bu-vb/pli-tv-bu-vb-sk")]
            for cat, dp in cats:
                rules = vb_rules(dp)
                stats[cat] = len(rules)
                assert [g[1] for g in rules] == list(range(1, len(rules) + 1)), \
                    f"{cat} numbering gap"
                for _, num, _stem, full in rules:
                    run_unit([full], f"{cat} {num}")
            full = "pli-tv-bu-vb/pli-tv-bu-vb-as1-7"
            stems = inner_stems(os.path.join(VIN, full + "_root-pli-ms.json"))
            stats["as"] = len(stems)
            for s in stems:
                num = int(re.search(r"(\d+)$", s).group(1))
                run_unit([full], f"as {num}", restrict=s)
        elif bk in ("mv", "cv"):
            lo, hi = (1, 10) if bk == "mv" else (11, 22)
            stats["kd"] = hi - lo + 1
            for n in range(lo, hi + 1):
                run_unit([f"pli-tv-kd/pli-tv-kd{n}"], f"kd {n}")
        elif bk == "pvr":
            d = os.path.join(VIN, "pli-tv-pvr")

            def key_num(fn):
                m = re.search(r"pvr([\d.]+)_root", fn)
                return tuple(int(x) for x in m.group(1).split("."))
            files = sorted((f for f in os.listdir(d)
                            if f.endswith("_root-pli-ms.json")), key=key_num)
            stats["chapters"] = len(files)
            for fn in files:
                num = ".".join(str(x) for x in key_num(fn))
                run_unit([f"pli-tv-pvr/{fn[:-len('_root-pli-ms.json')]}"],
                         f"pvr {num}")
        else:                                   # bi — partial upstream tree
            cats = [("pj", "pli-tv-bi-vb/pli-tv-bi-vb-pj"),
                    ("ss", "pli-tv-bi-vb/pli-tv-bi-vb-ss"),
                    ("np", "pli-tv-bi-vb/pli-tv-bi-vb-np"),
                    ("pc", "pli-tv-bi-vb/pli-tv-bi-vb-pc"),
                    ("pd", "pli-tv-bi-vb/pli-tv-bi-vb-pd"),
                    ("sk", "pli-tv-bi-vb/pli-tv-bi-vb-sk")]
            for cat, dp in cats:
                rules = vb_rules(dp)
                stats[cat] = len(rules)
                for _, num, _stem, full in rules:
                    run_unit([full], f"bi-{cat} {num}")
            full = "pli-tv-bi-vb/pli-tv-bi-vb-as1-7"
            stems = inner_stems(os.path.join(VIN, full + "_root-pli-ms.json"))
            stats["as"] = len(stems)
            for s in stems:
                num = int(re.search(r"(\d+)$", s).group(1))
                run_unit([full], f"bi-as {num}", restrict=s)

        # --- validation ---------------------------------------------------
        refs = [u["ref"] for u in ut]
        dup = sorted({r for r in refs if refs.count(r) > 1})
        if dup:
            raise SystemExit(f"[pali-vin] duplicate refs {dup[:5]}")
        if not ut:
            raise SystemExit(f"[pali-vin] {bk}: no units produced")

        def unit_text(ref, units):
            return next((u["text"] for u in units if u["ref"] == ref), "")
        if bk == "pj":
            assert sum(stats.values()) == 49, f"pj canon count {stats}"
            op = unit_text("pj 1" if "pj 1" in refs else "pj 1.0", ue)
            assert "Homage to the Buddha" in op, "pj1 homage missing"
            assert "Verañjā" in op or "Verañja" in op, "pj1 Verañjā opening"
        if bk == "pc":
            assert sum(stats.values()) == 178, f"pc canon count {stats}"
        if bk == "bi":
            # partial upstream tree, verified by enumeration:
            # pj5-8 (+pj1-4 stub), ss1-6+10-13, np1-12, pc1-96, pd1-8,
            # sk1+75, as1-7
            assert stats == {"pj": 5, "ss": 10, "np": 12, "pc": 96,
                             "pd": 8, "sk": 2, "as": 7}, f"bi count {stats}"
            assert drops["stubs"] == 1 and drops["rootless"] == 6, \
                f"expected pj1-4 stub + as2-7 rootless, got {drops}"
        align_cov = round(100 * mapped / kept, 2)

        obj_t = {"workId": f"pali-{meta['file']}", "lang": "pi",
                 "kind": "prose", "units": ut}
        obj_e = {"workId": f"pali-{meta['file']}",
                 "translator": "Bhikkhu Brahmali",
                 "year": 2020, "license": "CC0", "alignment": "segment-exact",
                 "units": ue}
        for path, obj in (
            (os.path.join(HERE, "public", "data", "texts", "pali",
                          f"{meta['file']}.json"), obj_t),
            (os.path.join(HERE, "public", "data", "trans",
                          f"pali-{meta['file']}-brahmali.json"), obj_e),
        ):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(obj, fh, ensure_ascii=False)

        biggest = max(len(u["words"]) for u in ut)
        print(f"[pali-vin-{bk}] {len(ut)} units, cats {stats}, "
              f"drops {drops}, EN coverage {mapped}/{kept} = "
              f"{align_cov}% (key match 100%), max unit {biggest} words")
        print(f"[pali-vin-{bk}] first={ut[0]['ref']!r} last={ut[-1]['ref']!r}")

        # --- spot checks --------------------------------------------------
        if bk == "mv":
            op = unit_text("kd 1" if "kd 1" in refs else "kd 1.0", ut)
            assert op.startswith("Namo tassa"), "kd1 homage"
            assert "uruvelāyaṁ viharati" in op, "kd1 Uruvelā opening"
        if bk == "cv":
            assert "Homage to the Buddha" in unit_text(
                "kd 11" if "kd 11" in refs else "kd 11.0", ue), "cv homage"
            assert "One hundred years" in unit_text(
                "kd 22" if "kd 22" in refs else "kd 22.0", ue), "kd22 opening"
        if bk == "pvr":
            assert unit_text("pvr 1.1" if "pvr 1.1" in refs else "pvr 1.1.0",
                             ut), "pvr1.1 present"
        if bk == "bi":
            assert any(r.startswith("bi-pj ") for r in refs), "bi-pj present"
    print("[pali-vinaya] done")


if __name__ == "__main__":
    main()
