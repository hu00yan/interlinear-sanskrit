#!/usr/bin/env python3
"""Build five small Khuddaka works from SuttaCentral's bilara-data (CC0).

Mirrors pipeline/build_pali_dhammapada.py output schema exactly:
  public/data/texts/pali/<book>.json           — Pali root (Mahāsaṅgīti ms)
  public/data/trans/pali-<book>-sujato.json    — Bhikkhu Sujato English

Books (uid prefix -> file stem): ud->udana, iti->itivuttaka, snp->suttanipata,
thag->theragatha, thig->therigatha.
Source cache: .cache-bilara/bilara-data, sparse clone of
github.com/suttacentral/bilara-data (depth 1, sparse-checkout extended to the
six KN books). Segment files are flat maps keyed `<uid>:<seg>`; keys are
IDENTICAL in root and translation (verified at build time), so alignment is
segment-exact. Unit = merge of that sutta's/poem's segments in order; Pali
stays in segmented form (tokens split on spaces only — no sandhi splitting).

Editorial drops (all counted, printed per book):
  * heading segments (`:0.…`) — book/vagga/sutta titles;
  * editorial sub-headings with a `0` component after the first — poem-title
    lines ("Subhūtittheragāthā"), commentarial "Nidānagāthā"/"Background",
    and homage formulas ("Namo tassa …");
  * root segments carrying no Sujato segment — vagga uddānas ("Dasamaṁ.",
    "…vaggo paṭhamo."), uddāna gāthās, name banners ("… Devasabho thero …."),
    closing counters ("Paṭhamaṁ.");
  * book/vatthugāthā colophons ending in "niṭṭhitā." ("Udānapāḷi niṭṭhitā.").
NOTE: unlike dhp we do NOT drop `\bsamattā\b` — in snp4.12 it is real verse
("Diṭṭhī hi tesampi tathā samattā").
"""
import json
import os
import re

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, ".cache-bilara", "bilara-data")

BOOKS = {
    # uid prefix: (file stem, display label, kind, expected units)
    "ud":   ("udana",       "ud",  "prose", 80),
    "iti":  ("itivuttaka",  "iti", "prose", 112),
    "snp":  ("suttanipata", "snp", "verse", 73),
    "thag": ("theragatha",  "thag", "verse", 264),
    "thig": ("therigatha",  "thig", "verse", 73),
}

SEG = re.compile(r"^([a-z]+)((?:\d+)(?:\.\d+)?):([\d.]+)$")
COLOPHON = re.compile(r"niṭṭhitā\.\s*$")


def load_pairs(prefix):
    """{unit_uid_tuple: [(segpath_tuple, pali, en), ...]} across vagga dirs."""
    root_dir = os.path.join(SRC, "root", "pli", "ms", "sutta", "kn", prefix)
    trans_dir = os.path.join(SRC, "translation", "en", "sujato", "sutta",
                             "kn", prefix)
    drops = {"headings": 0, "editorial0": 0, "no-en": 0, "colophons": 0}
    stats = {"raw": 0}
    units: dict[tuple[int, ...], list] = {}
    for dirpath, _, fns in sorted(os.walk(root_dir)):
        for fn in sorted(fns):
            m = re.match(rf"({prefix}[\d.]+)_root-pli-ms\.json$", fn)
            if not m:
                continue
            rpath = os.path.join(dirpath, fn)
            # mirror any vaggaN/ subdirectory under the translation tree
            rel = os.path.relpath(dirpath, root_dir)
            tpath = os.path.join(
                trans_dir, rel,
                fn.replace("_root-pli-ms.json", "_translation-en-sujato.json"))
            if not os.path.exists(tpath):
                raise SystemExit(f"[pali-kn:{prefix}] missing translation "
                                 f"for {fn}")
            root = json.load(open(rpath, encoding="utf-8"))
            trans = json.load(open(tpath, encoding="utf-8"))
            if sorted(root) != sorted(trans):
                raise SystemExit(f"[pali-kn:{prefix}] key mismatch in {fn}")
            for key in root:
                sm = SEG.match(key)
                if not sm:
                    raise SystemExit(f"[pali-kn:{prefix}] unparsed key {key}")
                stats["raw"] += 1
                seg = tuple(int(x) for x in sm.group(3).split("."))
                pali, en = root[key].strip(), (trans.get(key) or "").strip()
                # 0.x = headings (nikāya/book/vagga titles)
                if seg[0] == 0:
                    drops["headings"] += 1
                    continue
                # x.0.y = poem titles, Nidānagāthā/background, homage formulas
                if any(c == 0 for c in seg[1:]):
                    drops["editorial0"] += 1
                    continue
                # Editorial marginalia carry no Sujato segment: uddānas,
                # uddāna gāthās, name banners, closing counters (verified).
                if pali and not en:
                    drops["no-en"] += 1
                    continue
                # Closing colophons do have a translation; drop explicitly.
                if COLOPHON.search(pali):
                    drops["colophons"] += 1
                    continue
                uid = tuple(int(x) for x in sm.group(2).split("."))
                units.setdefault(uid, []).append((seg, pali, en))
    for segs in units.values():
        segs.sort()
    return units, drops, stats


def main() -> None:
    for prefix, (stem, label, kind, expected) in BOOKS.items():
        units, drops, stats = load_pairs(prefix)
        refs, text_units, trans_units = [], [], []
        seg_kept = seg_mapped = 0
        for uid in sorted(units):
            segs = units[uid]
            seg_kept += len(segs)
            pali = " ".join(p for _, p, _ in segs if p)
            eng = " ".join(e for _, _, e in segs if e)
            pali = re.sub(r"\s+", " ", pali).strip()
            eng = re.sub(r"\s+", " ", eng).strip()
            seg_mapped += sum(1 for _, _, e in segs if e)
            ref = f"{label} " + ".".join(str(x) for x in uid)
            refs.append(ref)
            text_units.append({"ref": ref, "words": pali.split(),
                               "text": pali})
            trans_units.append({"ref": ref, "text": eng})

        # --- validation ---------------------------------------------------
        if len(refs) != expected:
            raise SystemExit(f"[pali-kn:{prefix}] unit count {len(refs)} != "
                             f"expected {expected}")
        if all(len(uid) == 1 for uid in units):     # flat series (iti)
            nums = sorted(uid[0] for uid in units)
            if nums != list(range(1, expected + 1)):
                missing = [n for n in range(1, expected + 1)
                           if n not in set(nums)]
                raise SystemExit(f"[pali-kn:{prefix}] gaps in series: "
                                 f"{missing[:10]}")
        else:
            by_ch: dict[int, list[int]] = {}
            for uid in units:
                by_ch.setdefault(uid[0], []).append(uid[1])
            gaps = []
            for ch, subs in by_ch.items():
                subs.sort()
                if subs != list(range(1, max(subs) + 1)):
                    missing = [n for n in range(1, max(subs) + 1)
                               if n not in set(subs)]
                    gaps.append((ch, missing))
            if gaps:
                raise SystemExit(f"[pali-kn:{prefix}] non-contiguous refs, "
                                 f"gaps={gaps[:10]}")

        text_out = os.path.join(HERE, "public", "data", "texts", "pali",
                                f"{stem}.json")
        trans_out = os.path.join(HERE, "public", "data", "trans",
                                 f"pali-{stem}-sujato.json")
        for path, obj in (
            (text_out, {"workId": f"pali-{stem}", "lang": "pi", "kind": kind,
                        "units": text_units}),
            (trans_out, {"workId": f"pali-{stem}",
                         "translator": "Bhikkhu Sujato", "year": 2018,
                         "license": "CC0", "alignment": "segment-exact",
                         "units": trans_units}),
        ):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(obj, fh, ensure_ascii=False)

        align = round(100 * seg_mapped / seg_kept, 1)
        print(f"[pali-kn:{prefix}] {len(units)} units ({expected} expected), "
              f"{stats['raw']} raw segments -> {seg_kept} kept "
              f"(drops: {drops}), alignment {seg_mapped}/{seg_kept} = {align}%")
        print(f"[pali-kn:{prefix}] first={refs[0]!r} last={refs[-1]!r}, "
              f"{sum(len(u['words']) for u in text_units)} pali tokens")


if __name__ == "__main__":
    main()
