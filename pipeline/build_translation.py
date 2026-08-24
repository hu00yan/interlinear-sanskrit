#!/usr/bin/env python3
"""Build public/data/trans/bhagavadgita.json from K. T. Telang's SBE Vol. 8
(1882) translation — Public Domain.

Source pages: sacred-texts.com/hin/sbe08/sbe0803.htm..sbe0820.htm (verified
against the volume index; the task's sbe0808..sbe0819 guess was off by five).
The live site sits behind a Cloudflare JS challenge, so raw HTML is captured
via Wayback snapshots (`web.archive.org/web/2023id_/...`, curl --compressed)
into .cache-trans/sbe08NN.htm. Fetching is out-of-band; this script only
reads the cache (repo convention, cf. build_bhg_text.py).

The 1882 translation prints NO per-verse numbers — Telang's prose runs as
continuous paragraphs. We therefore split each chapter into clauses
(sentence / semicolon boundaries) and align clauses monotonically onto the
Sanskrit verse sequence parsed read-only from .cache-corpus/bhg_gretil.htm,
scoring clause<->verse lexical overlap over an alias table (Telang's SBE
orthography: Arguna/Krishna/Dhanangaya... -> arjuna/krsna/dhananjaya...).
alignment:"loose" — per-verse refs are constructed, not printed in the book.
"""
import html
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(HERE, ".cache-trans")
GRETL = os.path.join(HERE, ".cache-corpus", "bhg_gretil.htm")
OUT = os.path.join(HERE, "public", "data", "trans", "bhagavadgita.json")

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7,
         "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12, "XIII": 13,
         "XIV": 14, "XV": 15, "XVI": 16, "XVII": 17, "XVIII": 18}
# Canonical BORI counts, fallback when the GRETIL cache is absent.
FALLBACK_COUNTS = {1: 47, 2: 72, 3: 43, 4: 42, 5: 29, 6: 47, 7: 30, 8: 28,
                   9: 34, 10: 42, 11: 55, 12: 20, 13: 34, 14: 27, 15: 20,
                   16: 24, 17: 28, 18: 78}

# Telang's rendering -> folded Sanskrit key (see fold()).
ALIAS = {    "arguna": "arjuna", "krishna": "krsna", "keshava": "kesava",
    "hrishikesa": "hrsikesa", "hrishikesa": "hrsikesa",
    "dhanangaya": "dhananjaya", "gudakesa": "gudakesa",
    "vasudeva": "vasudeva", "madhava": "madhava", "govinda": "govinda",
    "pritha": "partha", "kunti": "kaunteya", "vrishni": "vrsni",
    "keshin": "kesin", "savyasakin": "savyasacin", "madhu": "madhu",
    "bhishma": "bhishma", "drona": "drona", "karna": "karna",
    "yudhistira": "yudhisthira", "bhima": "bhima", "arjuna": "arjuna",
    "brahmana": "brahmana", "kshatriya": "ksatriya", "vaisya": "vaisya",
    "sudra": "sudra", "sankhya": "samkhya", "sankhyas": "samkhya",
    "sankhya": "samkhya", "yogin": "yogin", "yogins": "yogin",
    "yoga": "yoga", "yogas": "yoga", "karma": "karman", "karmas": "karman",
    "adhyatma": "adhyatma", "adhibhuta": "adhibhuta",
    "adhidaivata": "adhidaivata", "adhiyagna": "adhiyajna",
    "om": "om", "asvattha": "asvattha", "kshetra": "ksetra",
    "kshetragna": "ksetrajna", "yagna": "yajna", "yagya": "yajna",
    "yaksha": "yaksa", "yakshas": "yaksa", "rakshas": "raksasa",
    "rakshases": "raksasa", "bhuta": "bhuta", "bhutas": "bhuta",
    "siddha": "siddha", "siddhas": "siddha", "gandharva": "gandharva",
    "gandharvas": "gandharva", "vasus": "vasu", "rudra": "rudra",
    "rudras": "rudra", "aditya": "aditya", "adityas": "aditya",
    "marut": "marut", "maruts": "marut", "sadhyas": "sadhya",
    "visvas": "visve", "mariki": "marici", "usmapas": "ushmapas",
    "varuna": "varuna", "soma": "soma", "kapila": "kapila",
    "narada": "narada", "vyasa": "vyasa", "tad": "tad", "sat": "sat",
    "asat": "asat", "brahman": "brahman", "brahmic": "brahma",
    "veda": "veda", "vedas": "veda", "vedantas": "vedanta",
    "mantra": "mantra", "mantras": "mantra", "dakshina": "daksina",
    "kratu": "kratu", "svadha": "svadha", "guna": "guna", "gunas": "guna",
    "fruit": "phala", "fruits": "phala", "duty": "dharma",
    "inaction": "akarman", "devotion": "yoga",
}

# Inflected GRETIL tokens -> stem key shared with ALIAS targets.
S_STEM = {"phala": "phala", "phalesu": "phala", "dharmam": "dharma",
          "dharmasya": "dharma", "yogam": "yoga", "yogena": "yoga",
          "yogah": "yoga", "karmana": "karman", "karmane": "karman",
          "akarmani": "akarman"}


def fold(word: str) -> str:
    """IAST/ASCII -> lowercase ascii key (hṛṣīkeśa -> hrsikesa)."""
    d = unicodedata.normalize("NFD", word.lower())
    return "".join(c for c in d if not unicodedata.combining(c))


def en_tokens(text: str):
    out = []
    for raw in re.findall(r"[A-Za-zÂÀÆà-ÿ']+", text):
        tok = fold(raw).strip("'")
        key = ALIAS.get(tok) or (tok if len(tok) >= 4 else None)
        if key:
            out.append(key)
    return set(out)


def sanskrit_verses():
    """Parse read-only GRETIL cache: {(ch, v): folded-token-set}."""
    if not os.path.exists(GRETL):
        return {}, {}
    txt = re.sub(r"<[^>]+>", "\n", open(GRETL, encoding="utf-8",
                                        errors="replace").read())
    half = re.compile(r"^(.*?)\s*Bhg_(\d{1,2})\.(\d{1,3})([a-d])\b")
    words: dict = {}
    for line in txt.splitlines():
        m = half.match(line.strip())
        if not m:
            continue
        ws, ch, v = m.group(1), int(m.group(2)), int(m.group(3))
        words.setdefault((ch, v), []).extend(re.findall(r"[^\W\d_]+", ws))
    verses = {k: {S_STEM.get(w, w) for w in map(fold, ws)}
              for k, ws in words.items()}
    counts: dict[int, int] = {}
    for (ch, v) in verses:
        counts[ch] = max(counts.get(ch, 0), v)
    return verses, counts


def load_chapter(n: int):
    """HTML cache -> (list of clause strings, speaker-label count)."""
    path = os.path.join(CACHE, f"sbe08{n + 2:02d}.htm")
    raw = open(path, encoding="utf-8", errors="replace").read()
    body = re.search(r"<H[12][^>]*>\s*CHAPTER\s+[IVX]+\.?</H[12]>(.*?)"
                     r"(?:<H3[^>]*>\s*Footnotes\s*</H3>|</BODY>)", raw,
                     re.S | re.I)
    seg = body.group(1) if body else raw
    if "<H3" in seg:                      # heading miss -> still cut notes
        seg = re.split(r"<H3[^>]*>\s*Footnotes\s*</H3>", seg, 1,
                       flags=re.I)[0]
    clauses: list[str] = []
    speakers = 0
    for attrs, inner in re.findall(r"<P([^>]*)>(.*?)</P>", seg,
                                   re.I | re.S):
        inner = re.sub(r'<A\s+HREF="[^"]*#fn_[^"]*"[^>]*>.*?</A>', "", inner,
                       flags=re.I | re.S)   # note markers incl. cross-page
        text = html.unescape(re.sub(r"<[^>]+>", "", inner))
        text = text.replace("\xa0", " ")
        text = re.sub(r"\s+", " ", text).strip()
        if not text or re.fullmatch(r"p\. \d+", text):
            continue
        if re.match(r"^\d{2,3}:\d+\b", text):
            continue                      # stray footnote entry
        if "center" in attrs.lower() and re.search(r"said\s*:?\s*$", text):
            speakers += 1          # editorial speaker heading, not verse prose
            continue
        parts = [p.strip() for p in re.split(r"(?<=[.;:!?])\s+", text)]
        buf = ""
        for p in parts:
            buf = f"{buf} {p}".strip() if buf else p
            if len(buf) >= 48:     # merge sub-clause slivers forward
                clauses.append(buf)
                buf = ""
        if buf:
            if clauses and len(buf) < 30:
                clauses[-1] = f"{clauses[-1]} {buf}"
            else:
                clauses.append(buf)
    return clauses, speakers


def align(clauses, verse_keys, ch):
    """Monotone DP: assign each clause to a verse; every verse >=1 clause."""
    m, n = len(clauses), len(verse_keys)
    C = [en_tokens(c) for c in clauses]
    V = verse_keys

    def score(i, j):
        hits = min(len(C[i] & V[j]), 4)
        return 5.0 * hits - 3.0 * abs(i / m - j / n)

    INF = float("inf")
    # dp[i][j]: best cost using first i clauses over first j verses.
    dp = [[INF] * (n + 1) for _ in range(m + 1)]
    bt = [[0] * (n + 1) for _ in range(m + 1)]  # 1 diag 2 up(empty verse) 3 left(extra)
    dp[0][0] = 0.0
    EMPTY_PEN, EXTRA_PEN = 2.0, 1.25
    for j in range(1, n + 1):
        dp[0][j] = dp[0][j - 1] + EMPTY_PEN
        bt[0][j] = 2
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            best, move = INF, 1
            c = dp[i - 1][j - 1] - score(i - 1, j - 1)
            if c < best:
                best, move = c, 1
            c = dp[i][j - 1] + EMPTY_PEN
            if c < best:
                best, move = c, 2
            if dp[i - 1][j] < INF:
                c = dp[i - 1][j] + EXTRA_PEN - score(i - 1, j - 1)
                if c < best:
                    best, move = c, 3
            dp[i][j], bt[i][j] = best, move
    groups: list[list[int]] = [[] for _ in range(n)]
    i, j = m, n
    while i > 0 or j > 0:
        mv = bt[i][j]
        if mv == 1:
            groups[j - 1].insert(0, i - 1)
            i, j = i - 1, j - 1
        elif mv == 2:
            j -= 1
        else:
            groups[j - 1].insert(0, i - 1)
            i -= 1
    # fill any verse left empty from the nearest non-empty neighbour
    dup = 0
    for j in range(n):
        if groups[j]:
            continue
        for back in range(j - 1, -1, -1):
            if len(groups[back]) > 1:
                groups[j].append(groups[back].pop())
                dup += 1
                break
        else:
            for fwd in range(j + 1, n):
                if len(groups[fwd]) > 1:
                    groups[j].append(groups[fwd].pop(0))
                    dup += 1
                    break
            else:
                src = groups[j - 1][-1] if j else groups[j + 1][0]
                groups[j].append(src)
                dup += 1
    return groups, dup


def main() -> None:
    verses, counts = sanskrit_verses()
    units, dup_total, spk_total = [], 0, 0
    for ch in range(1, 19):
        n = counts.get(ch) or FALLBACK_COUNTS[ch]
        keys = [verses[(ch, v)] for v in range(1, n + 1)]
        clauses, spk = load_chapter(ch)
        spk_total += spk
        if not keys:                       # no GRETIL cache: even split
            keys = [set()] * n
            step = len(clauses) / n
            groups = [[i] for i in
                      sorted({min(int(k * step), len(clauses) - 1)
                              for k in range(n)})]
            while len(groups) < n:
                groups.append([groups[-1][0]])
        else:
            if len(clauses) < n:           # guarantee >=1 clause per verse
                clauses = clauses * 0 or clauses
                while len(clauses) < n:
                    clauses.append("")
            groups, dup = align(clauses, keys, ch)
            dup_total += dup
        for v in range(n):
            text = " ".join(clauses[i] for i in groups[v]).strip()
            text = re.sub(r"\s+([;:,.!?])", r"\1", text)
            units.append({"ref": f"{ch}.{v + 1}", "text": text})
        print(f"[trans-telang] ch{ch:02d}: {n} verses, "
              f"{len(clauses)} clauses, {spk} speaker heads")
    out = {
        "workId": "bhagavadgita",
        "translator": "K. T. Telang",
        "year": 1882,
        "license": "Public domain (SBE 8)",
        "alignment": "loose",
        "units": units,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    u247 = next(u["text"] for u in units if u["ref"] == "2.47")
    u1866 = next(u["text"] for u in units if u["ref"] == "18.66")
    print(f"[trans-telang] {len(units)} units "
          f"(dup fills={dup_total}, speakers dropped={spk_total}) -> {OUT}")
    print(f"[check] 2.47 duty/work: "
          f"{any(w in u247.lower() for w in ('duty', 'work', 'action', 'business'))}")
    print(f"[check] 18.66 come-to-me: {'come to me' in u1866.lower()}")


if __name__ == "__main__":
    main()
