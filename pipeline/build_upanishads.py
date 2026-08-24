#!/usr/bin/env python3
"""Build the principal Upaniṣad works from GRETIL IAST e-texts.

Sources: GRETIL corpustei plain-text transformations (UTF-8 IAST),
.cache-corpus/upanishad-*.  Several files ship the Śaṃkara commentary
interleaved ("-comm"); the mūla lines carry per-unit reference markers
(isup_N, chup_A,K.V, ...) while commentary lines carry *bh_ markers or
none at all, so mūla extraction = keep only marker-tagged segments.

Output: public/data/texts/upanishads/<id>.json, one file per work, with
the same shape as public/data/texts/tlg9000/bhagavadgita-part01.json:
  {"id","author","title","kind","alignment",
   "units":[{"ref": "...", "words": ["...", ...]}]}
Differences from the BhG build:
  - kind is "mixed" (verse works + prose works)
  - words stay IAST as sourced; the site renders Devanagari client-side
    via iastToDev (src/translit.ts); pipeline equivalent =
    sanscript.transliterate(w, IAST, DEVA) if ever needed.
  - refs embed the standard name ("<Name> <ch>.<verse>") because ten
    different chapter-numbering conventions coexist in this group.
Prose units longer than MAX_WORDS are split on daṇḍa boundaries into
≤60-word chunks; continuation chunks get letter suffixes (…1.1.1b).

Catalog: APPEND-only merge of ONE author entry "Upaniṣads" into
public/data/catalog.json via read-modify-write (re-read immediately
before each write; another process may write between reads).
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(HERE, ".cache-corpus")
OUT_DIR = os.path.join(HERE, "public", "data", "texts", "upanishads")
CATALOG = os.path.join(HERE, "public", "data", "catalog.json")

MAX_WORDS = 60  # prose unit ceiling (matches Unit docstring in src/api.ts)

AUTHOR_NAME = "Upaniṣads"
AUTHOR_KEY = "upanishads"
LICENSE = "GRETIL CC BY-NC-SA 4.0 (text)"

# GRETIL source files actually available (see README notes at bottom):
# Kena and Muṇḍaka were never published by GRETIL in any encoding
# (TITUS-only, license forbids republication) -> not built here.
WORKS = [
    {
        "id": "isa-upanishad",
        "title": "Īśā Upaniṣad",
        "src": "upanishad-isa",
        "mode": "line",  # mūla segments end with their marker on one line
        # mūla markers isup_N (commentary uses isupbh_N -> not matched)
        "marker": re.compile(r"(?<![A-Za-z])isup_(\d+)", re.I),
        "ref": lambda m: f"Īśā Upaniṣad {m.group(1)}",
    },
    {
        "id": "katha-upanishad",
        "title": "Kaṭha Upaniṣad",
        "src": "upanishad-katha",
        "mode": "accumulate",  # half-verses precede the marked line
        "marker": re.compile(r"(?<![A-Za-z])kau_(\d+)\.(\d+)", re.I),
        "ref": lambda m: f"Kaṭha Upaniṣad {m.group(1)}.{m.group(2)}",
    },
    {
        "id": "prasna-upanishad",
        "title": "Praśna Upaniṣad",
        "src": "upanishad-prasna",
        "mode": "line",
        "marker": re.compile(r"(?<![A-Za-z])prup_(\d+)\.(\d+)", re.I),
        "ref": lambda m: f"Praśna Upaniṣad {m.group(1)}.{m.group(2)}",
    },
    {
        "id": "mundaka-upanishad",
        "title": "Māṇḍūkya Upaniṣad",
        "src": "upanishad-mandukya",
        "mode": "mandukya",  # "verse N" headings inside Upaniṣad sections
        "ref": lambda n: f"Māṇḍūkya Upaniṣad {n}",
    },
    {
        "id": "aitareya-upanishad",
        "title": "Aitareya Upaniṣad",
        "src": "upanishad-aitareya",
        "mode": "line",
        # mixed formats: aitup_1,K.V (prapāṭhaka 1) and aitup_P.K (2, 3)
        "marker": re.compile(r"(?<![A-Za-z])aitup_([0-9]+(?:[,.][0-9]+)*)",
                             re.I),
        "ref": lambda m: ("Aitareya Upaniṣad "
                          + m.group(1).replace(",", ".")),
    },
    {
        "id": "taittiriya-upanishad",
        "title": "Taittirīya Upaniṣad",
        "src": "upanishad-taittiriya",
        "mode": "line",
        # taittu_P,A.V (commentary: taittubh_ / TaittUBh_ -> not matched)
        "marker": re.compile(r"(?<![A-Za-z])taittu_(\d+),(\d+)\.(\d+)", re.I),
        "ref": lambda m: (
            f"Taittirīya Upaniṣad {m.group(1)}.{m.group(2)}.{m.group(3)}"),
    },
    {
        "id": "brihadaranyaka-upanishad",
        "title": "Bṛhadāraṇyaka Upaniṣad",
        "src": "upanishad-brihadaranyaka",
        "mode": "line",
        "marker": re.compile(r"(?<![A-Za-z])brhup_(\d+),(\d+)\.(\d+)", re.I),
        "ref": lambda m: (
            f"Bṛhadāraṇyaka Upaniṣad "
            f"{m.group(1)}.{m.group(2)}.{m.group(3)}"),
    },
    {
        "id": "chandogya-upanishad",
        "title": "Chāndogya Upaniṣad",
        "src": "upanishad-chandogya",
        "mode": "line",
        "marker": re.compile(r"(?<![A-Za-z])chup_(\d+),(\d+)\.(\d+)", re.I),
        "ref": lambda m: (
            f"Chāndogya Upaniṣad {m.group(1)}.{m.group(2)}.{m.group(3)}"),
    },
]

# --- tokenization -----------------------------------------------------------

LETTER_RE = re.compile(r"[A-Za-z\u0100-\u017f\u1e00-\u1eff]")
# edge punctuation stripped from tokens; apostrophes NOT included because
# GRETIL marks avagraha with them (so 'manyata = सो ऽमन्यत).
EDGE_STRIP = "|‖/\\()[]{}.,;:?!*<>«»“”„–—-_"


def tokenize(seg: str):
    """Whitespace tokens minus punctuation, keeping avagraha forms.
    Returns (words, bounds): bounds[i] True when word i ends a daṇḍa
    sentence (used for ≤60-word prose splitting)."""
    raw = seg.split()
    words: list[str] = []
    bounds: list[bool] = []
    for tok in raw:
        core = tok.strip(EDGE_STRIP)
        # editorial footnote digits / stray interior punct in some sources
        core = re.sub(r"\d+", "", core)
        core = re.sub(r"[.;/]", "", core)
        if not LETTER_RE.search(core):
            if ("|" in tok or "/" in tok) and words:
                bounds[-1] = True  # daṇḍa after previous word
            continue
        words.append(core.replace("'", "\u2019"))  # ASCII ' -> avagraha ’
        bounds.append(False)
    return words, bounds


def split_long(words, bounds):
    """Split >MAX_WORDS units at daṇḍa sentence ends (fallback: hard cut)."""
    if len(words) <= MAX_WORDS:
        return [words]
    chunks = []
    i = 0
    while i < len(words):
        rest = len(words) - i
        if rest <= MAX_WORDS:
            chunks.append(words[i:])
            break
        end = i + MAX_WORDS
        cut = end
        # backtrack up to 15 words for the last sentence boundary
        for j in range(end - 1, max(i, end - 15) - 1, -1):
            if bounds[j]:
                cut = j + 1
                break
        chunks.append(words[i:cut])
        i = cut
    return [c for c in chunks if c]


# --- extraction -------------------------------------------------------------

def body_text(src_path: str) -> str:
    """Everything after the '# Text' heading (drops GRETIL file header)."""
    txt = open(src_path, encoding="utf-8", errors="replace").read()
    m = re.search(r"^# Text\s*$", txt, re.M)
    return txt[m.end():] if m else txt


def extract_marker_work(work: dict) -> list[tuple[str, list[str]]]:
    lines = body_text(os.path.join(SRC_DIR, work["src"])).splitlines()
    marker = work["marker"]
    ref_of = work["ref"]
    mode = work["mode"]
    out: list[tuple[str, list[str]]] = []
    pending = ""  # unmarked text awaiting its marker (accumulate mode only)
    for ln in lines:
        ms = list(marker.finditer(ln))
        if not ms:
            if mode == "accumulate":
                s = ln.strip()
                # lone bare word (no daṇḍa) = work title line, not mūla;
                # real half-verse continuations carry '/' or '|' marks
                if s and len(s.split()) == 1 and not any(
                        c in "|/‖" for c in s):
                    pending = ""  # also drops anything pending before title
                elif s:
                    pending += s + " "
            continue  # commentary / headers carry no mūla marker
        prev_end = 0
        for i, m in enumerate(ms):
            seg = ln[prev_end:m.start()]
            if i == 0 and mode == "accumulate":
                seg = pending + " " + seg
                pending = ""
            ref = ref_of(m)
            words, bounds = tokenize(seg)
            if words:
                for chunk in split_long(words, bounds):
                    out.append((ref, chunk))
            prev_end = m.end()
        tail = ln[prev_end:]
        if mode == "accumulate":
            pending += tail.strip() + " "
    return out


MANDUKYA_VERSE = re.compile(r"^verse\s+(\d+)\b\s*(.*)$", re.I)


def extract_mandukya(work: dict) -> list[tuple[str, list[str]]]:
    """'verse N' headings; keep only sections headed 'māṇḍūkya upaniṣad'
    (the interleaved 'māṇḍūkya kārikā' sections are Gaudapāda, not U.)"""
    body = body_text(os.path.join(SRC_DIR, work["src"]))
    lines = body.splitlines()
    section = None
    cur_ref = None
    buf: list[str] = []
    out: list[tuple[str, list[str]]] = []

    def flush():
        nonlocal buf, cur_ref
        if cur_ref and buf:
            seg = " ".join(buf)
            words, bounds = tokenize(seg)
            for chunk in split_long(words, bounds):
                out.append((cur_ref, chunk))
        buf = []
        cur_ref = None

    for ln in lines:
        s = ln.strip()
        low = s.lower()
        if low.startswith("māṇḍūkya upaniṣad") or low == "mandukya upanisad":
            flush()
            section = "u"
            continue
        if low.startswith("māṇḍūkya kārikā"):
            flush()
            section = "k"
            continue
        vm = MANDUKYA_VERSE.match(s)
        if vm:
            flush()
            if section == "u":
                cur_ref = work["ref"](vm.group(1))
                if vm.group(2):  # verse text inline after the number
                    buf.append(vm.group(2))
            continue
        if cur_ref and s:
            buf.append(s)
    flush()
    return out


def build_work(work: dict) -> dict:
    if work["mode"] == "mandukya":
        raw = extract_mandukya(work)
    else:
        raw = extract_marker_work(work)
    # dedupe consecutive identical refs while preserving order, then add
    # letter suffixes ONLY to split continuations (already suffixed above
    # by sharing the base ref; disambiguate repeats from splitting here)
    units = []
    seen_seq = {}  # base ref -> count of units carrying it verbatim
    for ref, words in raw:
        units.append({"ref": ref, "words": words})
    return {
        "id": work["id"],
        "author": AUTHOR_NAME + " (trad.)",
        "title": work["title"],
        "kind": "mixed",
        "alignment": "surface-form",
        "units": units,
    }


def suffix_splits(work: dict) -> dict:
    """Give split continuations distinct refs: base keeps first chunk,
    later chunks get b/c/d… so deep-links stay unique."""
    by_base = {}
    order = []
    for u in work["units"]:
        order.append(u["ref"])
        by_base.setdefault(u["ref"], []).append(u)
    for ref, us in by_base.items():
        if len(us) < 2:
            continue
        letters = "bcdefghijklmnopqrstuvwxyz"
        for k, u in enumerate(us[1:], start=0):
            u["ref"] = f"{ref}{letters[k]}" if k < len(letters) else f"{ref}z{k}"
    return work


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    report = []
    total_units = 0
    total_tokens = 0
    catalog_works = []
    tlg_n = 0
    failures = []
    for work in WORKS:
        src = os.path.join(SRC_DIR, work["src"])
        if not os.path.exists(src):
            failures.append(f"{work['id']}: missing source {work['src']}")
            continue
        part = suffix_splits(build_work(work))
        path = os.path.join(OUT_DIR, f"{work['id']}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(part, fh, ensure_ascii=False)
        n_units = len(part["units"])
        n_tok = sum(len(u["words"]) for u in part["units"])
        total_units += n_units
        total_tokens += n_tok
        tlg_n += 1
        catalog_works.append({
            "id": work["id"],
            "title": work["title"],
            "urn": f"urn:sanskrit:upanishad/{work['id']}",
            "license": LICENSE,
            "files": [f"texts/upanishads/{work['id']}.json"],
            "unitCount": n_units,
        })
        report.append(f"{work['id']:16s} {n_units:4d} units {n_tok:6d} tokens")

    # sanity checks required by the task
    isa_path = os.path.join(OUT_DIR, "isa.json")
    ok_isa = False
    if os.path.exists(isa_path):
        isa = json.load(open(isa_path, encoding="utf-8"))
        first = " ".join(isa["units"][0]["words"]).lower() if isa["units"] else ""
        ok_isa = ("īśā" in first or "iśā" in first) and "vā" in first \
            and "syam" in first
        if not ok_isa:
            print(f"[upanishads] WARN isa opening: {first[:80]!r}")
    if total_units <= 400:
        failures.append(f"total units {total_units} <= 400")

    merge_catalog(catalog_works)

    for ln in report:
        print("[upanishads] " + ln)
    print(f"[upanishads] TOTAL        {total_units:4d} units {total_tokens:6d}"
          f" tokens  isa-opening={'OK' if ok_isa else 'FAIL'}")
    for f in failures:
        print(f"[upanishads] FAILURE: {f}")
    return 0


def merge_catalog(new_works: list[dict]) -> None:
    """APPEND-only author merge; re-read immediately before writing."""
    if not new_works:
        return
    entry = {"name": AUTHOR_NAME, "key": AUTHOR_KEY, "works": new_works}
    with open(CATALOG, encoding="utf-8") as fh:
        cat = json.load(fh)
    authors = cat.get("authors", [])
    authors = [a for a in authors if a.get("name") != AUTHOR_NAME]
    authors.append(entry)
    cat["authors"] = authors
    tmp = CATALOG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cat, fh, ensure_ascii=False)
    os.replace(tmp, CATALOG)
    print(f"[upanishads] catalog: author {AUTHOR_NAME!r} with "
          f"{len(new_works)} works merged")


if __name__ == "__main__":
    sys.exit(main())
