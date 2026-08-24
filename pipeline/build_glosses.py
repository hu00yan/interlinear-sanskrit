#!/usr/bin/env python3
"""Build Monier-Williams gloss shards + join glosses into morph entries.

Input : .cache-dcs/mw.txt  (Cologne digitization, SLP1-native, open data)
        public/data/morph/*.json (slp1-keyed, from build_morph.py)
Output: public/data/gloss/{a-z}.json keyed slp1_key(headword) -> {u,g}
        morph entries gain "g": first MW sense truncated to 200 chars.

MW headwords are SLP1 already -> zero-conversion alignment with our keys.

Extraction rules (audit fix — previously ~77% of headwords were silently
dropped and survivors were polluted):
  * The SLP1 search key is <k1>; <k2> is the accented DISPLAY form
    ("ka/rman", "yo/ga") whose accent slashes broke the shard filter.
    Parse <k1> only, never prefer <k2>.
  * Every <L>...<LEND> record is a sense block; homonyms share one key.
  * Sense lines are stripped of markup, leading homonym/page-number
    colophons ("^\\d+\\.\\s*"), and leading "¦".
  * Cross-reference-only lines ("&c. See pp...", "See p. N, col. M") are
    skipped in favour of the first semantic line; trailing "&c." /
    "See pp..." tails are cut from the kept line.
  * SHORT gloss selection: lowercased keys merge several printed MW
    lemmas, so the dominant reading comes from the LARGEST entry block
    (entry opener + its '<e>NNNA' continuations); within it the longest
    sensible English candidate wins with scripture markers penalized and
    (...) / [...] asides stripped from the stored gloss.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "pipeline"))
from sanscript import transliterate, SLP1, DEVA  # noqa: E402

MW = os.path.join(HERE, ".cache-dcs", "mw.txt")
MORPH_DIR = os.path.join(HERE, "public", "data", "morph")
OUT_DIR = os.path.join(HERE, "public", "data", "gloss")

TAG = re.compile(r"<[^>]+>")
HOM_NOISE = re.compile(r"^\d+\.\s*")           # homonym / page-colophon number
XREF_ONLY = re.compile(                        # pure cross-reference line
    r"^(?:&c\.?|see\s+\S|=|cf\.|q\.\s*v\.?|pp?\.)", re.I)
XREF_TAIL = re.compile(                        # trailing cross-ref tail
    r"\s*(?:,\s*)?&c\.?(?:\s*(?:see|pp?\.).*)?$|\s+see\s+(?:pp?\.|under).*$"
    r"|\s*,?\s*[Ss]ee\s+.*$",                  # ', see so-and-so' pointers
    re.I)
MAX_GLOSS = 200


def clean(line: str) -> str:
    return re.sub(r"\s+", " ", TAG.sub(" ", line)).strip()


def sense_lines(body_lines):
    """Cleaned, de-noised candidate gloss lines for one <L> record."""
    out = []
    for raw in body_lines:
        t = clean(raw)
        if not t or set(t) <= {"¦"}:
            continue
        t = HOM_NOISE.sub("", t).lstrip()
        # drop headword echo: "<s>HW</s> ¦ sense" -> keep what follows ¦
        if "¦" in t:
            head, _, rest = t.partition("¦")
            t = rest.strip() or head.strip()
        t = HOM_NOISE.sub("", t).lstrip()
        t = t.lstrip("¦").strip()          # leading sense separator
        if not t:
            continue
        out.append(t)
    return out


def is_sensible(t: str) -> bool:
    """>20 chars of mostly-English containing at least one vowel-run word."""
    if len(t) <= 20 or " " not in t:
        return False
    ok = sum(c.isalpha() or c in ",-()'" or c.isspace() for c in t)
    if ok / len(t) < 0.75:
        return False
    return bool(re.search(r"[aeiou]{2}", t.lower()))


def cut_tail(t: str) -> str:
    """Drop trailing '&c.' / 'See pp...' cross-reference tails."""
    prev = None
    while prev != t:
        prev = t
        m = XREF_TAIL.search(t)
        if m and m.start() > 0:
            t = t[:m.start()].rstrip(" ,;")
    return t


CITE = re.compile(r"[A-Z\u00c0-\u017f][A-Za-z\u00c0-\u017f]{0,3}\.")
DIGITS = re.compile(r"\b\d+\b")
BRACKETS = re.compile(r"\[[^\]]*\]")
PARENS = re.compile(r"\([^()]*\)")
SCORE_CAP = 120      # a SHORT gloss must not favour encyclopedic rambling


def definitional_score(t: str) -> float:
    """Longest-sensible ranking, degraded by scripture-reference markers
    (RV., ŚBr., MBh., ...) and locus numerals ('x, 8, 44') so citation
    chains lose to plain definitions."""
    return (min(len(t), SCORE_CAP)
            - 18 * len(CITE.findall(t))
            - 6 * len(DIGITS.findall(t)))


def tidy(t: str) -> str:
    """Stored form: strip editorial [...] and (...) asides (etymology,
    citation apparatus), collapse whitespace and stray separators."""
    prev = None
    while prev != t:
        prev = t
        t = BRACKETS.sub(" ", t)
        t = PARENS.sub(" ", t)
        # asides left open at a record boundary: '[ e.g. ...' / '( cf. ...'
        t = re.sub(r"\s*\[[^\]]*$", " ", t)
        t = re.sub(r"\s*\([^)]*$", " ", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s+([,;.])", r"\1", t)
    t = re.sub(r"(?:,\s*){2,}", ", ", t)   # ",," left by stripped parens
    return re.sub(r"^[,\s]+", "", t).strip(" ;,")


def pick_gloss(records):
    """Best SHORT gloss for one headword key.

    Lowercased SLP1 keys merge several printed MW lemmas/homonyms, so the
    dominant reading is taken from the LARGEST entry block (a block is an
    entry-opening record plus its '<e>NNNA' continuations). MW orders
    senses by priority, so the block's FIRST semantic line wins once
    (...) / [...] asides are stripped ('that which is established or firm,
    steadfast decree, statute, ordinance, law' — not 'a thing', not 'Law
    personified as Indra, ŚBr. &c.'); if it is too fragmentary we fall
    back to the block's longest sensible line, then to plain first text.
    """
    def candidates(recs):
        """(scored sensibles, first non-xref raw line) for these records."""
        scored, first_raw = [], None
        for rec in recs:
            for t in rec["lines"]:
                if XREF_ONLY.match(t):
                    continue
                t2 = cut_tail(t)
                if not t2 or XREF_ONLY.match(t2):
                    continue
                if first_raw is None:
                    first_raw = t2
                stored = tidy(t2)
                if is_sensible(stored):
                    scored.append((definitional_score(stored), stored))
        return scored, first_raw

    # split records into entry blocks; the largest belongs to the dominant
    # lemma sharing this key (dharma-the-law vs darma 'a thing', etc.)
    blocks, cur = [], []
    for rec in records:
        if rec["primary"] and cur:
            blocks.append(cur)
            cur = []
        cur.append(rec)
    if cur:
        blocks.append(cur)

    if blocks:
        biggest = max(blocks, key=len)
        _, block_first = candidates(biggest[:1])   # sense-1 line only
        if block_first:
            stored = tidy(block_first)
            if is_sensible(stored):
                return truncate(stored)
        pool, _ = candidates(biggest)              # else best of the block
        if pool:
            return truncate(max(pool, key=lambda x: x[0])[1])

    # fallback: first plain-text line anywhere under this key
    _, any_first = candidates(records)
    if any_first:
        return truncate(tidy(any_first))
    return None


def truncate(g: str) -> str:
    if g and len(g) > MAX_GLOSS:
        cut = g.rfind(" ", 0, MAX_GLOSS)
        g = g[:cut if cut > 60 else MAX_GLOSS].rstrip(" ,;")
    return g


def parse_mw():
    """key(lowered slp1 <k1>) -> list of records {primary, lines}.

    A record whose <e> code ends in 'A' is a page/entry continuation; the
    record that opens an entry (<e> plain, usually with <h>) is primary.
    """
    by_key: dict[str, list] = {}
    cur_key = None
    cur_primary = True
    cur_body = []

    def flush():
        if cur_key and cur_body:
            lines = sense_lines(cur_body)
            if lines:
                by_key.setdefault(cur_key.lower(), []).append(
                    {"primary": cur_primary, "lines": lines})

    for line in open(MW, encoding="utf-8"):
        if line.startswith("<L>"):
            flush()
            cur_body = []
            m = re.search(r"<k1>([^<]*)", line)   # search key only, not <k2>
            cur_key = m.group(1).strip() if m else None
            e = re.search(r"<e>([^<>]*)", line)
            # continuation blocks carry an 'A' suffix on the <e> code
            cur_primary = not (e and e.group(1).strip().rstrip(".0123456789")
                               .endswith("A"))
        elif line.startswith("<LEND>"):
            flush()
            cur_key, cur_body = None, []
        elif cur_key:
            cur_body.append(line.rstrip("\n"))
    flush()
    return by_key


def main() -> None:
    # ---- parse mw.txt ---------------------------------------------------
    by_key = parse_mw()

    gloss: dict[str, dict] = {}
    for key, records in by_key.items():
        txt = pick_gloss(records)
        if not txt:
            continue
        try:
            deva = transliterate(key, SLP1, DEVA)
        except Exception:
            continue
        gloss[key] = {"u": deva, "g": txt}

    # ---- emit gloss shards ----------------------------------------------
    os.makedirs(OUT_DIR, exist_ok=True)
    shards: dict[str, dict] = {}
    for k in sorted(gloss):
        if not k or not re.fullmatch(r"[a-z~]+", k):
            continue
        shards.setdefault(k[0], {})[k] = gloss[k]
    for f in os.listdir(OUT_DIR):
        if f.endswith(".json"):
            os.remove(os.path.join(OUT_DIR, f))
    n = 0
    for letter, bucket in sorted(shards.items()):
        with open(os.path.join(OUT_DIR, f"{letter}.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(bucket, fh, ensure_ascii=False, separators=(",", ":"))
        n += len(bucket)
    print(f"[mw] {len(by_key)} distinct headword keys parsed")
    print(f"[gloss] {len(shards)} shards, {n} entries")

    # ---- join glosses into morph entries --------------------------------
    joined = 0
    for f in sorted(os.listdir(MORPH_DIR)):
        if not f.endswith(".json") or f.startswith("_"):
            continue
        p = os.path.join(MORPH_DIR, f)
        data = json.load(open(p, encoding="utf-8"))
        changed = False
        for key, entries in data.items():
            for e in entries:
                lemma = e.get("l") or ""
                lk = None
                if any("\u0900" <= c <= "\u097f" for c in lemma):
                    lk = transliterate(lemma, DEVA, SLP1).lower()
                g = gloss.get(lk or "") or gloss.get(key)
                if g and not e.get("g"):
                    e["g"] = g["g"]
                    changed = True
                    joined += 1
        if changed:
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"[morph<-gloss] joined {joined} entries")


if __name__ == "__main__":
    main()
