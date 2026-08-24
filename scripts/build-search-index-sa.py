#!/usr/bin/env python3
"""Build the Sanskrit text search index (public/data/search-index-sa.py output: search-index-sa.json).

MANUAL RUN ONLY — this script is not wired into the npm build yet (integration
left to a separate change). Run from the repo root:

    python3 scripts/build-search-index-sa.py

Scans public/data/texts/**/*.json. Each document must be {"id": "<workId>", ...,
"units": [...]}; each unit carries its tokens either as a "words" array or as a
single space-joined "w" string — both forms are handled. Tokens are normalized
(NFC, lowercased, danda/digits/punctuation stripped) while KEEPING diacritics,
so IAST/Devanagari letter+mark characters survive intact.

Output schema:
    { "<normWord>": { "n": <total occurrences>,
                      "hits": [ {"w": "<workId>", "r": "<firstRef>"}, ... ] } }

hits are capped at MAX_HITS_PER_WORD works, sorted by per-work count desc
(tie-break: workId). If the raw JSON exceeds MAX_BYTES (20 MB), the hit cap is
tightened stepwise until the file fits; if even one hit per word is too large,
the build fails loudly rather than silently truncating data.
"""

import json
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEXTS_DIR = REPO_ROOT / "public" / "data" / "texts"
OUT_PATH = REPO_ROOT / "public" / "data" / "search-index-sa.json"

MAX_HITS_PER_WORD = 20          # works kept per word
MAX_BYTES = 20 * 1024 * 1024    # raw output size ceiling
CAP_LADDER = [MAX_HITS_PER_WORD, 10, 5, 2, 1]


def normalize(token):
    """Lowercase + strip danda/digits/punct; keep letters and diacritic marks."""
    token = unicodedata.normalize("NFC", token).lower()
    return "".join(
        ch for ch in token
        if unicodedata.category(ch)[0] in ("L", "M")  # letters + combining marks
    )


def unit_tokens(unit):
    """Yield raw tokens from a unit's `words` array or `w` space-joined string."""
    words = unit.get("words")
    if isinstance(words, list):
        yield from words
    elif isinstance(unit.get("w"), str):
        yield from unit["w"].split()


def build_index(cap):
    """Return ({word: {"n", "hits"}}, stats) using per-word work cap `cap`."""
    totals = defaultdict(int)                    # word -> corpus-wide count
    per_work = defaultdict(lambda: defaultdict(int))   # word -> work -> count
    first_ref = defaultdict(dict)                # word -> work -> first ref

    files = sorted(TEXTS_DIR.rglob("*.json"))
    scanned_units = 0
    for path in files:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"WARN: skipping unparseable {path}: {exc}", file=sys.stderr)
            continue
        work_id = doc.get("id") or path.stem
        for unit in doc.get("units", []):
            ref = unit.get("ref", "")
            scanned_units += 1
            for raw in unit_tokens(unit):
                norm = normalize(raw)
                if not norm:
                    continue
                totals[norm] += 1
                counts = per_work[norm]
                counts[work_id] += 1
                refs = first_ref[norm]
                if work_id not in refs:
                    refs[work_id] = ref

    index = {}
    for word in sorted(totals):
        ranked = sorted(per_work[word].items(), key=lambda kv: (-kv[1], kv[0]))[:cap]
        index[word] = {
            "n": totals[word],
            "hits": [{"w": w, "r": first_ref[word][w]} for w, _ in ranked],
        }
    return index, {"files": len(files), "units": scanned_units, "words": len(index)}


def main():
    if not TEXTS_DIR.is_dir():
        sys.exit(f"No texts directory: {TEXTS_DIR}")

    for cap in CAP_LADDER:
        index, stats = build_index(cap)
        OUT_PATH.write_text(
            json.dumps(index, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        size = OUT_PATH.stat().st_size
        print(f"cap={cap}: {stats['words']} entries from {stats['files']} file(s), "
              f"{stats['units']} units -> {size / 1024:.0f} KiB")
        if size <= MAX_BYTES:
            break
        print(f"Over {MAX_BYTES // (1024*1024)} MiB; raising pruning threshold...", file=sys.stderr)
    else:
        OUT_PATH.unlink(missing_ok=True)
        sys.exit("Index still exceeds 20 MiB at cap=1 — corpus too large for this format.")

    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
