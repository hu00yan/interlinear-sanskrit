#!/usr/bin/env python3
"""check_words_clean.py — fail-loud QA gate against GRETIL reference-marker
and critical-apparatus leakage into units[].words[].

Background (qa-report/lotus-keys.md): ingest tokenizers kept transliterated
GRETIL marker stems ({Saddhp_1.11} -> "Saddhp" -> सद्ध्प्), standalone
section numbers, page anchors and <b>…</b> markup as WORDS. Users see them
as unparsable garbage rows and they inflate morph miss-rates.

What counts as dirty:

  Devanagari-script word arrays (any token):
    * ASCII letters/digits/underscore          -> marker stem + numbering
    * Devanagari digits ०-९                    -> section-number fragments
    * known bare marker stems                  -> सद्ध्प् लल् ग्व् इइ …
    * apparatus/header signs  < > | )          -> lacuna marks, running heads
    * URL-ish tokens                           -> scraped link slugs

  Roman-script word arrays (Pali IAST, RV, darshana):
    * standalone numbers / section refs        -> "1.", "(3)", "2.10.", "1–4"
    * bracketed annotations with digits        -> "[Savipāka—5]", "[69]"
    * <b>/</b> markup                          -> stripped, word kept
    * RV page anchors  "31//. -rv_6:8/32- …"   -> stripped, trailing word kept
    * digits fused inside a word               -> "āsī3t" -> "āsīt"
    * URL-ish tokens                           -> removed

Usage:
  # gate (fail-loud, exit 1 on any violation):
  python3 check_words_clean.py --in FILE.json [FILE.json ... | DIR]

  # remediation sweep (rewrites dirty files in place; drops units whose
  # words[] become empty because they were ONLY markers):
  python3 check_words_clean.py --in DIR --fix

Accepts full text documents ({"units":[{ref,words}]}) and pipeline tokenize
artifacts ({"text_units":[{ref,words}],"trans_units":...}); any list of
dicts with ref+words keys anywhere in the document is validated.
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import Counter

DEVA_CONS = re.compile(r"[\u0915-\u0939]")
DEVA_LETTER = re.compile(r"[\u0900-\u097F]")
ASCII_ALNUM = re.compile(r"[A-Za-z0-9_]")
DEVA_DIGIT = re.compile(r"[\u0966-\u096F]")
# bare transliterated GRETIL marker stems, each verified against the raw
# source marker formats or qa-report/lotus-keys.md (see
# qa-report/refmarker-cleanup.md for the evidence table)
BARE_STEMS = {
    "सद्ध्प्": "Saddhp/saddharmapundarika",
    "लल्": "Lal/lalitavistara",
    "ग्व्": "Gv/gandavyuha",
    "इइ": "II/tantrakhyayika-siglum",
}
APPARATUS = re.compile(r"[<>|)]")            # deva: lacuna/pipe/header signs
URLISH = re.compile(r"http|www\.|[a-z]?htm?$", re.I)
NUMSHAPE = re.compile(r"^[\s\d.,()\[\]\-–—;:]*\d[\s\d.,()\[\]\-–—;:.]*$")
BRACKET_ANN = re.compile(r"^\[[^\]]*\d[^\]]*\]$")
TAG = re.compile(r"</?b>")
RV_ANCHOR = re.compile(r"^\s*\d+\s*//.*?-\s+")
RV_PAREN = re.compile(r"\(rv_[^)]*\)\s*")
# residual page-anchor fragments after partial stripping ("rv_6:8/32- janayan")
RV_LEFTOVER = re.compile(r"^rv_[0-9A-Za-z:/.,*\-]*-\s*(\S.*)$")
IAST_WORD = re.compile(r"^[A-Za-zĀ-žā-ž'’\-]+$")
SEP_SPLIT = re.compile(r"[#|~\\]")


def dominant_script(units):
    nd = nl = 0
    for u in units:
        for w in u.get("words", []) or []:
            if DEVA_CONS.search(w):
                nd += 1
            elif re.search(r"[A-Za-z]", w):
                nl += 1
    if nd == 0 and nl == 0:
        return "other"
    return "deva" if nd >= nl else "latin"


def check_token(w, dom):
    """None if clean; else ('remove', None, why) or ('repair', new, why).

    repair value is either the replacement token or '\\x01'-joined parts
    when one contaminated token splits into several clean words.
    """
    if dom == "deva":
        if ASCII_ALNUM.search(w):
            return ("remove", None, "ascii-alnum-in-deva")
        if DEVA_DIGIT.search(w):
            return ("remove", None, "devanagari-digit")
        if w in BARE_STEMS:
            return ("remove", None,
                    "bare-marker-stem:" + BARE_STEMS[w])
        if URLISH.search(w):
            return ("remove", None, "url-ish")
        if APPARATUS.search(w):
            return ("remove", None, "apparatus-header-signs")
        core = w.replace("[", "").replace("]", "")
        if core != w and core and DEVA_LETTER.search(core) \
                and not ASCII_ALNUM.search(core) and not DEVA_DIGIT.search(core):
            return ("repair", core, "editorial-bracket-strip")
        return None
    # roman-script arrays (Pali IAST, Rigveda, darshana IAST)
    if URLISH.search(w):
        return ("remove", None, "url-ish")
    if TAG.search(w):
        core = TAG.sub("", w).strip().strip(".,;:!?—–-")
        if core and re.search(r"[A-Za-z]", core):
            return ("repair", core, "html-tag-strip")
        return ("remove", None, "html-tag-only")
    if BRACKET_ANN.match(w):
        return ("remove", None, "bracketed-annotation")
    if RV_LEFTOVER.match(w):
        core = RV_LEFTOVER.match(w).group(1).strip()
        if core and re.search(r"[A-Za-z]{2}", core):
            parts = [p for p in core.split() if IAST_WORD.match(p)]
            if parts:
                return ("repair", "\x01".join(parts), "rv-leftover-strip")
        return ("remove", None, "rv-anchor-only")
    if NUMSHAPE.match(w):
        return ("remove", None, "standalone-number")
    if RV_ANCHOR.match(w):
        core = RV_PAREN.sub("", RV_ANCHOR.sub("", w)).strip()
        if core and re.search(r"[A-Za-z]{2}", core):
            return ("repair", core, "rv-anchor-strip")
        return ("remove", None, "rv-anchor-only")
    if re.search(r"\d", w):
        core = re.sub(r"\d+", "", w)
        if len(core) >= 2 and IAST_WORD.match(core):
            return ("repair", core, "digit-strip-word")
        return ("remove", None, "digit-contaminated")
    if SEP_SPLIT.search(w):
        parts = [p.strip().strip("/|#~\\") for p in w.split()]
        parts = [p for p in parts if p and IAST_WORD.match(p)]
        if len(parts) >= 2:
            return ("repair", "\x01".join(parts), "separator-split")
        return None
    if "#" in w or "\\" in w:
        core = w.replace("#", "").replace("\\", "")
        if len(core) >= 2 and IAST_WORD.match(core):
            return ("repair", core, "separator-strip")
    return None


def iter_unit_lists(node):
    """Yield every list of {ref, words} dicts anywhere in the document."""
    if isinstance(node, list):
        if node and all(isinstance(u, dict) and "ref" in u and "words" in u
                        for u in node):
            yield node
        else:
            for x in node:
                yield from iter_unit_lists(x)
    elif isinstance(node, dict):
        for v in node.values():
            yield from iter_unit_lists(v)


def scan_file(fp):
    """Return ({'units':n,'words':n}, violations[]) without modifying."""
    doc = json.load(open(fp, encoding="utf-8"))
    st = {"units": 0, "words": 0}
    viol = []
    for ulist in iter_unit_lists(doc):
        dom = dominant_script(ulist)
        for u in ulist:
            st["units"] += 1
            for w in u.get("words", []) or []:
                st["words"] += 1
                res = check_token(w, dom)
                if res:
                    viol.append({"file": fp, "ref": u.get("ref"),
                                 "token": w, "action": res[0], "why": res[2],
                                 "new": res[1]})
    return st, viol


def fix_file(fp):
    """Remediate in place. Returns (removed, repaired, dropped_refs, log)."""
    doc = json.load(open(fp, encoding="utf-8"))
    raw = open(fp, encoding="utf-8").read()   # to preserve spacing style
    spaced = '", "' in raw
    removed = repaired = 0
    dropped = []
    log = []
    for ulist in iter_unit_lists(doc):
        dom = dominant_script(ulist)
        for u in list(ulist):                 # copy: units may be removed
            words = u.get("words", []) or []
            out = []
            changed = False
            for w in words:
                res = check_token(w, dom)
                if res is None:
                    out.append(w)
                    continue
                changed = True
                act, val, why = res
                if act == "remove":
                    removed += 1
                    log.append(f"{os.path.basename(fp)}: drop token {w!r}"
                               f"@{u.get('ref')} ({why})")
                else:
                    parts = val.split("\x01")
                    out.extend(parts)
                    repaired += 1
                    log.append(f"{os.path.basename(fp)}: repair {w!r}->"
                               f"{parts[0][:28]!r}@{u.get('ref')} ({why})")
            if changed:
                if out:
                    u["words"] = out
                else:
                    dropped.append(u.get("ref"))
                    log.append(f"{os.path.basename(fp)}: DROP unit "
                               f"{u.get('ref')!r} (only markers; text="
                               f"{(u.get('text') or '')[:40]!r})")
                    ulist.remove(u)
    if changed_files_needed(removed, repaired, dropped):
        json.dump(doc, open(fp, "w", encoding="utf-8"), ensure_ascii=False,
                  separators=(", ", ": ") if spaced else (",", ":"))
    return removed, repaired, dropped, log


def changed_files_needed(r, p, d):
    return bool(r or p or d)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--in", dest="inp", action="append", required=True,
                    help="json file(s) or directory to check")
    ap.add_argument("--fix", action="store_true",
                    help="rewrite files removing/repairing dirty tokens, "
                         "then re-run the gate; still fails loud if dirty")
    ap.add_argument("--report", help="write JSON summary here")
    ap.add_argument("--max-show", type=int, default=30)
    args = ap.parse_args()

    files = []
    for p in args.inp:
        if os.path.isdir(p):
            files += sorted(glob.glob(os.path.join(p, "**", "*.json"),
                                      recursive=True))
        else:
            files.append(p)

    if args.fix:
        t_r = t_p = t_d = 0
        for fp in files:
            r, p, dropped, _log = fix_file(fp)
            t_r, t_p, t_d = t_r + r, t_p + p, t_d + len(dropped)
            if r or p or dropped:
                print(f"  {fp}: removed={r} repaired={p} "
                      f"units_dropped={len(dropped)} {dropped}")
        print(f"[check_words_clean] FIX pass: removed={t_r} repaired={t_p} "
              f"units_dropped={t_d} across {len(files)} files")

    per_file = {}
    total_viol = 0
    shown = 0
    for fp in files:
        try:
            st, viol = scan_file(fp)
        except Exception as e:  # unreadable/garbage input fails loudly too
            print(f"[check_words_clean] ERROR reading {fp}: {e}",
                  file=sys.stderr)
            sys.exit(1)
        total_viol += len(viol)
        if viol:
            per_file[fp] = {"violations": len(viol),
                            "samples": viol[:10]}
        print(f"  {fp}: units={st['units']} words={st['words']} "
              f"dirty={len(viol)}")
        for v in viol[: max(0, args.max_show - shown)]:
            print(f"  VIOLATION [{v['why']}] {v['file']}:{v['ref']} "
                  f"{v['token']!r}")
            shown += 1
    print(f"[check_words_clean] {len(files)} files, {total_viol} dirty "
          f"tokens")
    if args.report:
        json.dump({"files_checked": len(files),
                   "violations": total_viol, "per_file": per_file},
                  open(args.report, "w"), indent=2, ensure_ascii=False)
    if total_viol:
        print("[check_words_clean] FAIL: reference-marker/apparatus tokens "
              "present in words[] (fail-loud)")
        sys.exit(1)
    print("[check_words_clean] PASS")


if __name__ == "__main__":
    main()
