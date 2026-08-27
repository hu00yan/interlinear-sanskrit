#!/usr/bin/env python3
"""Build Monier-Williams gloss shards + join glosses into morph entries.

Input : .cache-dcs/mw.txt  (Cologne digitization, SLP1-native, open data)
        public/data/morph/*.json (slp1-keyed, from build_morph.py)
Output: public/data/gloss/{a-z}.json keyed by case-preserving SLP1 headword
        -> {u,g}; morph entries gain the same compact `g` field.

SLP1 is case-sensitive: `Darma` is dharma while `darma` is a different
headword. Never case-fold a dictionary key. Shard filenames are lower-case,
but the keys inside each JSON object retain canonical SLP1 exactly.

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
  * SHORT gloss selection takes the first substantive lexical sense and
    removes citations, examples, bibliographic abbreviations and grammar
    apparatus. It is capped at 90 characters for inline display.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "pipeline"))
from sanscript import transliterate, SLP1, IAST, DEVA  # noqa: E402

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
MAX_GLOSS = 90
VALID_KEY = re.compile(r"[A-Za-z~]+$")


def mw_key(text: str) -> str:
    """One strict SLP1 key for MW and morphology lemmas.

    This deliberately has no case-folding or stem/prefix fallback: SLP1
    capitals encode different phonemes. It only removes editorial accent
    marks which are not part of Cologne's `<k1>` search-key alphabet.
    """
    text = text.strip().replace("/", "").replace("\\", "")
    if any("\u0900" <= c <= "\u097f" for c in text):
        text = transliterate(text, DEVA, SLP1)
    elif any(c in text for c in "āīūṛṝḷḹṅñṭḍṇśṣṃṁḥ"):
        text = transliterate(text, IAST, SLP1)
    return text


def clean(line: str) -> str:
    # MW's div markers separate lexical senses within very large verb entries.
    line = re.sub(r'<div n="to"\s*/>', "\n", line)
    line = re.sub(r"<(?:ls|s|s1|etym|gk)\b[^>]*>.*?</(?:ls|s|s1|etym|gk)>",
                  " ", line)
    return re.sub(r"[ \t]+", " ", TAG.sub(" ", line)).strip()


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


GRAMMAR_ONLY = re.compile(
    r"^(?:[IVXLC]+\)?\s*)?(?:Ved\.|Class\.|cl\.|[PĀ]\.|Impv\.|Subj\.|Pot\.|"
    r"impf\.|aor\.|perf\.|pr\. p\.|Caus\.|Desid\.|Intens\.|nom\.|acc\.|"
    r"du\.|sg\.|pl\.).*", re.I)
GRAMMAR_FRAGMENT = re.compile(
    r"^(?:prec|imperf|aor|perf|part|nom|acc|dat|abl|gen|loc|voc|sg|du|pl)\.?(?:\s|$)",
    re.I)
NON_SENSE_PREFIX = re.compile(
    r"^(?:for\s+(?:[PĀ]\.|Ā\.|[A-Z][a-z]+)|(?:\d+(?:st|nd|rd|th)\s+)?"
    r"(?:fut|pres|aor|perf|form)|with\s+prepositions|cf\.)\b", re.I)
CITATION_TAIL = re.compile(
    r"(?:\s*[;,]\s*(?:RV|AV|VS|TS|ŚBr|MBh|BhP|R|Mn|Pāṇ|Kāś|Śak|Hit|"
    r"Kāv|L|Sch|ib|cf)\.[^;,.]*[;,.]?)+$", re.I)
LEADING_META = re.compile(
    r"^(?:(?:m|f|n|mf|mfn|ind|adj|adv)\.?\s+|(?:only|especially)\s+ifc\.\s+)+",
    re.I)


def compact_gloss(t: str):
    """Return one readable lexical sense, never an MW grammar/citation essay."""
    t = tidy(cut_tail(t))
    t = HOM_NOISE.sub("", t).strip(" ¦")
    t = LEADING_META.sub("", t)
    t = CITATION_TAIL.sub("", t).strip(" ,;.")
    t = re.split(r"\s*(?:&c\.|&|:)\s*", t, maxsplit=1)[0].strip(" ,;.")
    if (GRAMMAR_ONLY.match(t) or GRAMMAR_FRAGMENT.match(t) or
            NON_SENSE_PREFIX.match(t) or "˚" in t or
            len(t) < 3):
        return None
    words = re.findall(r"[A-Za-z]{2,}", t)
    # A lone “Ved.”/“Class.” label is neither a sense nor useful gloss.
    if len(words) < 2:
        return None
    return truncate(t)


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
    """First substantive English sense in MW order, across continuation records."""
    for rec in records:
        for line in rec["lines"]:
            for sense in line.split("\n"):
                if not sense or XREF_ONLY.match(sense):
                    continue
                gloss = compact_gloss(sense)
                if gloss:
                    return gloss
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
                key = mw_key(cur_key)
                if VALID_KEY.fullmatch(key):
                    by_key.setdefault(key, []).append(
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
        if not VALID_KEY.fullmatch(k):
            continue
        shards.setdefault(k[0].lower(), {})[k] = gloss[k]
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
                lk = mw_key(lemma)
                g = gloss.get(lk)
                old = e.get("g")
                if g:
                    if old != g["g"]:
                        e["g"] = g["g"]
                        changed = True
                        joined += 1
                elif old:
                    # `g` is source-derived and must never survive under a
                    # different, case-folded SLP1 headword.
                    del e["g"]
                    changed = True
        if changed:
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"[morph<-gloss] joined {joined} entries")


if __name__ == "__main__":
    main()
