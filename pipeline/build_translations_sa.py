#!/usr/bin/env python3
"""
build_translations_sa.py — wave-2 English translations for the Sanskrit corpus.

Emits public/data/trans/<workId>.json for:
  epics    : ramayana (Griffith), mahabharata (Ganguli)
  buddhist : buddhacarita (Cowell, SBE49), sukhavativyuha-larger/-smaller (Müller,
             SBE49), vajracchedika (Müller, SBE49), heart (Müller smaller
             Prajñā-pāramitā-hṛidaya, SBE49)
  kavya    : meghaduta (Wilson 1814), hitopadesha (Arnold), pancatantra (Ryder
             1925, US-PD since 2021-01-01 regardless of renewal), arthashastra
             (Shamasastry 1915), manusmriti (Bühler, SBE25)

Sources are cached (gitignored) in .cache-trans-epics/, .cache-trans-buddh/,
.cache-trans-kavya/ — see qa-report/sanskrit-translations-wave2.md for URLs.

All outputs carry alignment:"loose": refs follow each work's canonical
scheme (kanda.sarga / parvan.adhyaya / canto.verse / book.chapter ...) but the
translation is not guaranteed to sit on the identical Sanskrit unit everywhere
(OCR loss, translator omissions, abridgment).

Usage: python3 pipeline/build_translations_sa.py [--only workId1,workId2]
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_EPICS = ROOT / ".cache-trans-epics"
CACHE_BUDDH = ROOT / ".cache-trans-buddh"
CACHE_KAVYA = ROOT / ".cache-trans-kavya"
OUT = ROOT / "public" / "data" / "trans"

ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def romanToInt(s):
    s = s.strip().upper().replace(".", "")
    total, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN.get(ch)
        if v is None:
            return None
        total = total - v if v < prev else total + v
        prev = max(prev, v)
    return total


def readLines(path):
    return Path(path).read_text(encoding="utf-8", errors="replace").splitlines()


def htmlBodyLines(path):
    """sacred-texts page -> cleaned text lines (nav junk removed separately)."""
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    txt = re.sub(r"(?is)<(script|style).*?</\1>", "", raw)
    m = re.search(r"(?is)<BODY.*?</BODY>", txt)
    body = m.group(0) if m else txt
    plain = html.unescape(re.sub(r"<[^>]+>", "\n", body))
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in plain.split("\n")]
    return [l for l in lines if l]


NAV_TOP = {"Sacred Texts", "Hinduism", "Buddhism", "Index", "Previous", "Next",
           "Sacred Texts Index", "Laws of Manu Index"}
NAV_PAT = re.compile(
    r"^(Buy this Book|Next:|« Previous|p\. \d+|\{p\. \d+\}|\d+ sacred-texts|"
    r"Sacred Texts \|.*|Next: .*»?)$", re.I)


def stripSacredTextsJunk(lines):
    """Drop nav headers/footers, {p. N} marks, footnote blocks '[1. ... ]'."""
    out, in_foot = [], False
    started = False
    for ln in lines:
        if not started:
            if ln in NAV_TOP or NAV_PAT.match(ln):
                continue
            started = True
        if ln in NAV_TOP or NAV_PAT.match(ln):
            continue
        if re.fullmatch(r"-{3,}|_{3,}", ln):
            continue
        if ln.startswith("[") and not out == []:
            in_foot = True
        if in_foot:
            if "]" in ln:
                in_foot = False
            continue
        out.append(ln)
    return out


def stripInlineMarks(text):
    text = re.sub(r"\{\d+\}", "", text)          # sacred-texts page marks
    text = re.sub(r"\[\d+\]", "", text)          # footnote refs
    text = re.sub(r"\[\^?\d+\]", "", text)
    text = re.sub(r"\[\.", ".", text)
    return re.sub(r" {2,}", " ", text).strip()


def writeJson(workId, translator, year, licenseStr, units, source=None, notes=None):
    doc = {
        "workId": workId,
        "translator": translator,
        "year": year,
        "license": licenseStr,
        "alignment": "loose",
        "units": [{"ref": u["ref"], "text": u["text"]} for u in units],
    }
    if source:
        doc["source"] = source
    if notes:
        doc["notes"] = notes
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{workId}.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    words = sum(len(u["text"].split()) for u in units)
    print(f"  {workId}.json: {len(units)} units, {words} words "
          f"({path.stat().st_size//1024} KiB)")
    return len(units)


def gutenbergCore(lines):
    """Strip PG boilerplate using *** START/END markers."""
    try:
        s = next(i for i, l in enumerate(lines) if "*** START" in l)
        e = next(i for i, l in enumerate(lines) if "*** END" in l)
        return lines[s + 1:e]
    except StopIteration:
        return lines


# --------------------------------------------------------------------------- #
# Epics                                                                       #
# --------------------------------------------------------------------------- #

BOOK_HEAD = re.compile(r"^BOOK ([IVX]+)\.?(\(\d+\))?$")
CANTO_HEAD = re.compile(r"^Canto ([IVXLC]+)\.\s*(.*)$", re.M)


def build_ramayana():
    lines = gutenbergCore(readLines(CACHE_EPICS / "pg24869.txt"))
    # locate the verse BOOK I heading: the one whose next 120 lines contain a
    # Canto heading (the editor's prose argument has none).
    starts = [(i, m.group(1)) for i, l in enumerate(lines)
              if (m := BOOK_HEAD.match(l))]
    verse_start = None
    for i, bk in starts:
        window = "\n".join(lines[i:i + 120])
        if bk == "I" and CANTO_HEAD.search(window):
            verse_start = i
            break
    if verse_start is None:
        raise RuntimeError("ramayana: verse region not found")

    units, book, canto_no, buf, canto_title = [], None, None, [], ""
    def flush():
        nonlocal buf
        if book and canto_no and buf:
            text = "\n".join(stripInlineMarks(re.sub(r"\(\d{1,4}\)\s*$", "", x))
                             for x in buf if x.strip())
            units.append({"ref": f"{book}.{canto_no}", "text": text})
        buf = []

    for ln in lines[verse_start:]:
        if ln.startswith("Uttarak"):
            break  # prose argument of Book VII — no Griffith verse exists
        if ln.startswith("Thus far the Section"):
            # closing colophon of Book VI; what follows in the PG file is an
            # appendix of Gorresio's Italian and Fauche's French excerpts.
            buf.append(ln)
            flush()
            break
        mb = BOOK_HEAD.match(ln)
        mc = CANTO_HEAD.match(ln.strip())
        if mb:
            flush(); book = romanToInt(mb.group(1)); canto_no = None
            continue
        if mc and book:
            flush(); canto_no = romanToInt(mc.group(1)); continue
        if book and canto_no:
            buf.append(ln)
    flush()

    # sanity
    assert units and units[0]["ref"] == "1.1", units[:1]
    return writeJson(
        "ramayana", "Ralph T. H. Griffith", 1875, "Public domain",
        units,
        source={"site": "Project Gutenberg", "ebook": 24869,
                "title": "The Rámáyan of Válmíki, translated into English verse",
                "url": "https://www.gutenberg.org/ebooks/24869"},
        notes=[
            "Complete verse translation of kandas 1-6; Griffith never rendered "
            "Uttara-kanda (book 7) into verse - his edition gives only a prose "
            "argument, so no 7.x units exist.",
            "ref = <kanda>.<sarga>; sarga = Griffith's canto number (roman in "
            "the source). Verse-number tags '(NNN)' stripped.",
        ])


MB_VOLS = ["pg15474.txt", "pg15475.txt", "pg15476.txt", "pg15477.txt"]
MB_BOOK = re.compile(r"^BOOK (\d+)")
MB_SECT = re.compile(r"^SECTION ([IVXLCDM]+)\.?\s*$")


def build_mahabharata():
    units = []
    for vol in MB_VOLS:
        lines = gutenbergCore(readLines(CACHE_EPICS / vol))
        parvan, sect, style, buf = None, None, None, []

        def flush():
            nonlocal buf
            if parvan and sect and buf:
                text = "\n".join(b for b in buf if b.strip())
                units.append({"ref": f"{parvan}.{sect}", "text": text})
            buf = []

        for ln in lines:
            mbk = MB_BOOK.match(ln)
            ms = MB_SECT.match(ln)
            if mbk:
                flush(); parvan = int(mbk.group(1)); sect = None; style = None
                continue
            if ms:
                flush(); sect = romanToInt(ms.group(1)); style = "SECTION"
                continue
            s = ln.strip()
            if parvan and re.fullmatch(r"\d{1,3}", s):
                # volumes 3-4 mark sections of some parvas with bare numbers
                if style is None:
                    style = "num"
                if style == "num":
                    flush(); sect = int(s)
                    continue
            if parvan and sect is not None:
                buf.append(ln)
        flush()
    assert units and units[0]["ref"] == "1.1", units[:1]
    seen = {u["ref"] for u in units}
    dupes = len(units) - len(seen)
    return writeJson(
        "mahabharata", "Kisari Mohan Ganguli", 1896, "Public domain",
        units,
        source={"site": "Project Gutenberg", "ebooks": [15474, 15475, 15476, 15477],
                "title": "The Mahabharata of Krishna-Dwaipayana Vyasa, "
                         "translated into English prose (1883-1896)"},
        notes=[
            "Complete 18-parvan prose translation, all four PG volumes.",
            f"ref = <parvan>.<section>, section = Ganguli's SECTION numbering "
            f"(roman in source); {dupes} duplicate refs merged by first "
            "occurrence.",
            "Ganguli's section breaks do not always coincide with critical-"
            "edition adhyaya numbers - alignment is best-effort by sequence.",
        ]) if not dupes else _mb_dedupe(units)


def _mb_dedupe(units):
    seen, out = set(), []
    for u in units:
        if u["ref"] in seen:
            continue
        seen.add(u["ref"]); out.append(u)
    return writeJson(
        "mahabharata", "Kisari Mohan Ganguli", 1896, "Public domain", out,
        source={"site": "Project Gutenberg", "ebooks": [15474, 15475, 15476, 15477]},
        notes=["ref = <parvan>.<section>; duplicates on collision resolved by "
               "first occurrence (OCR-free typed text, rare)."])


# --------------------------------------------------------------------------- #
# Buddhist (SBE 49, 1894)                                                     #
# --------------------------------------------------------------------------- #

SBE49 = "https://sacred-texts.com/bud/sbe49/sbe49{n}.htm"


def _verseParagraphs(lines):
    """Group lines into paragraphs; a paragraph starting 'N. ' begins a verse."""
    units, buf = [], []
    def flush():
        nonlocal buf
        if buf:
            text = stripInlineMarks(" ".join(buf))
            if text:
                units.append({"ref": None, "text": text})
            buf = []
    for ln in lines:
        if re.match(r"^\d{1,3}\. ", ln):
            flush()
        buf.append(ln)
    flush()
    return units


def build_buddhacarita():
    units, n_books = [], 0
    for n in range(3, 20):  # sbe4903..sbe4919 = Books I-XVII
        lines = stripSacredTextsJunk(htmlBodyLines(CACHE_BUDDH / f"wb_sbe49{n:02d}.htm"))
        # drop title block up to 'BOOK X.' heading
        try:
            start = next(i for i, l in enumerate(lines)
                         if re.match(r"^BOOK\s+[IVX]+\.?$", l))
        except StopIteration:
            continue
        book = romanToInt(re.search(r"BOOK\s+([IVX]+)", lines[start]).group(1))
        body = lines[start + 1:]
        para_units = _verseParagraphs(body)
        v = 0
        for pu in para_units:
            m = re.match(r"^(\d{1,3})\. ", pu["text"])
            if m:
                v = int(m.group(1))
                pu["text"] = stripInlineMarks(pu["text"][m.end():])
            else:
                v += 1  # continuation / unnumbered -> sequence on
            if len(pu["text"]) < 25:
                continue  # heading fragment noise
            units.append({"ref": f"{book}.{v}", "text": pu["text"]})
        n_books += 1
    assert units[0]["ref"] == "1.1", units[:2]
    # drop footnote fragments and keep the longest text when the source
    # double-prints a verse number
    best = {}
    for u in units:
        t = u["text"]
        if len(t) < 160 and t.rstrip().endswith("]"):
            continue  # leaked exegetical note
        cur = best.get(u["ref"])
        if cur is None or len(t) > len(cur["text"]):
            best[u["ref"]] = u
    units = [best[k] for k in sorted(
        best, key=lambda r: (int(r.split(".")[0]), int(r.split(".")[1])))]
    return writeJson(
        "buddhacarita", "Edward Byles Cowell", 1894,
        "Public domain (SBE 49)",
        units,
        source={"site": "Internet Sacred Text Archive (via Wayback snapshot)",
                "url": SBE49.format(n="03"),
                "title": "The Buddha-karita of Asvaghosha, SBE vol. XLIX"},
        notes=[
            f"Cowell's abridged SBE rendering, Books I-XVII ({n_books} book "
            "pages); omitted verses are ellipses in the source.",
            "ref = <canto>.<verse> (printed verse numbers); loose against "
            "complete Sanskrit editions (Petrach/Eastern text differs).",
        ])


def build_sukhavati_larger():
    lines = stripSacredTextsJunk(htmlBodyLines(CACHE_BUDDH / "wb_sbe4924.htm"))
    start = next(i for i, l in enumerate(lines) if l.startswith("OM. Adoration"))
    paras = []
    buf = []
    for ln in lines[start:]:
        buf.append(ln)
        if len(ln) < 70:  # blank-line proxy: short line ends paragraph
            paras.append(" ".join(buf)); buf = []
    if buf:
        paras.append(" ".join(buf))
    units = [{"ref": str(i + 1), "text": stripInlineMarks(p)}
             for i, p in enumerate(paras) if len(stripInlineMarks(p)) > 30]
    return writeJson(
        "sukhavativyuha-larger", "F. Max Müller", 1894,
        "Public domain (SBE 49)",
        units,
        source={"site": "Internet Sacred Text Archive (via Wayback snapshot)",
                "url": SBE49.format(n="24")},
        notes=["Prose sutra; Müller prints no internal numbering, so refs are "
               "sequential paragraph numbers 1..N (loose)."])


def build_sukhavati_smaller():
    lines = stripSacredTextsJunk(htmlBodyLines(CACHE_BUDDH / "wb_sbe4927.htm"))
    start = next(i for i, l in enumerate(lines) if l.startswith("ADORATION"))
    units = []
    for ln in lines[start:]:
        m = re.match(r"^§?\s*(\d+)\.\s*(.*)$", ln)
        if m:
            units.append({"ref": m.group(1), "text": stripInlineMarks(m.group(2))})
        elif units and not ln.startswith("["):
            units[-1]["text"] = (units[-1]["text"] + " " + stripInlineMarks(ln)).strip()
    units = [u for u in units if len(u["text"]) > 30]
    return writeJson(
        "sukhavativyuha-smaller", "F. Max Müller", 1894,
        "Public domain (SBE 49)",
        units,
        source={"site": "Internet Sacred Text Archive (via Wayback snapshot)",
                "url": SBE49.format(n="27")},
        notes=["refs follow Müller's §-paragraph numbers where printed."])


def build_vajracchedika():
    lines = stripSacredTextsJunk(htmlBodyLines(CACHE_BUDDH / "wb_sbe4929.htm"))
    start = next(i for i, l in enumerate(lines) if l.startswith("ADORATION"))
    units, cur, pre = [], None, []
    for ln in lines[start:]:
        r = romanToInt(ln) if re.fullmatch(r"[IVXLC]+\.?", ln.strip()) else None
        if r and 1 <= r <= 50:
            cur = str(r)
            units.append({"ref": cur, "text": ""})
        elif cur is None:
            pre.append(stripInlineMarks(ln))       # adoration line before §I
        else:
            units[-1]["text"] = (units[-1]["text"] + " " + stripInlineMarks(ln)).strip()
    units = [u for u in units if len(u["text"]) > 20]
    return writeJson(
        "vajracchedika", "F. Max Müller", 1894,
        "Public domain (SBE 49)",
        units,
        source={"site": "Internet Sacred Text Archive (via Wayback snapshot)",
                "url": SBE49.format(n="29")},
        notes=['Müller\'s "Vagrakkhedikâ or Diamond-Cutter"; refs = his '
               "printed roman section numbers, arabic here. Note: Müller's "
               "Sanskrit base differs from Kumârajîva's 32-section Chinese.",
               "Müller's adoration formula precedes section I: "
               + " ".join(pre)[:120]])
    return writeJson(
        "vajracchedika", "F. Max Müller", 1894,
        "Public domain (SBE 49)",
        units,
        source={"site": "Internet Sacred Text Archive (via Wayback snapshot)",
                "url": SBE49.format(n="29")},
        notes=['Müller\'s "Vagrakkhedikâ or Diamond-Cutter"; refs = his '
               "printed roman section numbers, arabic here. Note: Müller's "
               "Sanskrit base differs from Kumârajîva's 32-section Chinese."])


def build_heart():
    lines = stripSacredTextsJunk(htmlBodyLines(CACHE_BUDDH / "wb_sbe4931.htm"))
    start = next(i for i, l in enumerate(lines) if l.startswith("ADORATION") or
                 l.startswith("The venerable Bodhisattva"))
    paras = [stripInlineMarks(l) for l in lines[start:]]
    paras = [p for p in paras if len(p) > 10]
    # merge very short fragments (headings/quotes split by the printer)
    merged = []
    for p in paras:
        if merged and len(p) < 60:
            merged[-1] += " " + p
        else:
            merged.append(p)
    units = [{"ref": str(i + 1), "text": t}
             for i, t in enumerate(merged) if len(t) > 40]
    return writeJson(
        "heart", "F. Max Müller", 1894,
        "Public domain (SBE 49)",
        units,
        source={"site": "Internet Sacred Text Archive (via Wayback snapshot)",
                "url": SBE49.format(n="31")},
        notes=["This is the Smaller Prajñâ-pâramitâ-hridaya (= Heart Sutra); "
               "Müller's Larger Hridaya (sbe4930) also exists in SBE49 but was "
               "not ingested as a separate work.",
               "refs sequential over translated paragraphs (loose)."])


# --------------------------------------------------------------------------- #
# Kavya / Sastra                                                              #
# --------------------------------------------------------------------------- #

def build_meghaduta():
    lines = readLines(CACHE_KAVYA / "wilson_meghaduta.txt")
    # poem body: first page whose running head is 'MEGHA DUTA,' OR 'MEGHA DUTA, OR'
    start = next(i for i, l in enumerate(lines)
                 if l.strip() == "MEGHA DUTA,"
                 and any("CLOUD MESSENGER" in x.upper() for x in lines[i:i + 5]))
    end = next(i for i, l in enumerate(lines)
               if i > start and re.match(r"^\s*ANNOTATIONS\b", l))
    junk = re.compile(
        r"^(MEGHA DUTA.*|.*CLOUD MESSENGER.*|\d+ MEGHA.*|[B-Z] ?\d+|\d+|OR$|"
        r"A ?POEM\.?$|THE$|IN THE SANSCRIT LANGUAGE.*|BY CA[Ll]IDA.?SA.*)$")
    units, buf = [], []

    def flush(tag_line):
        nonlocal buf
        if buf:
            text = "\n".join(stripInlineMarks(x) for x in buf)
            units.append({"ref": str(len(units) + 1),
                          "text": re.sub(r" ?\d+$", "", text).strip()})
        buf = []

    for ln in lines[start:end]:
        s = ln.rstrip()
        if junk.match(s.strip()):
            if buf and not s.strip():
                flush(s)
            continue
        if not s.strip():
            continue
        buf.append(s.strip())
        if re.search(r"\d+$", s):     # Wilson's stanza-end line-count tag
            flush(s)
    flush(None)
    units = [u for u in units if len(u["text"]) > 40]
    assert units[0]["text"].startswith("Where Rama"), units[0]["text"][:40]
    return writeJson(
        "meghaduta", "Horace Hayman Wilson", 1814, "Public domain",
        units,
        source={"site": "archive.org item mghadtaorcloudm00wilsgoog (djVu OCR)",
                "title": "The Mégha Dúta, or Cloud Messenger, trans. H. H. "
                         "Wilson, London 1814"},
        notes=[
            "Verse rendering with Wilson's annotations; OCR of the 1814 scan.",
            "refs are sequential stanza-block numbers assigned here (Wilson's "
            "own marginal tags count lines, not verses) - remap positionally "
            "against the Sanskrit verse order.",
            "Purva- and Uttara-megha are numbered continuously.",
        ])


ARNOLD_BOOKS = ["THE WINNING OF FRIENDS", "THE PARTING OF FRIENDS", "WAR", "PEACE"]
CAPS_LINE = re.compile(r"^[A-Z][A-Za-z ,'\-\u00c0-\u017f]*$")
STORY_CAPS = re.compile(r"^[A-Z][A-Z ,\-']{8,64}$")


def build_hitopadesha():
    lines = readLines(CACHE_KAVYA / "pg13268_arnold_indianpoetry.txt")
    lines = gutenbergCore(lines)
    start = next(i for i, l in enumerate(lines)
                 if l.strip() == ARNOLD_BOOKS[0] and i > 350)
    end = next(i for i, l in enumerate(lines)
               if i > start and l.strip().startswith("NALA AND DAMAYANTI"))
    units, book, label, buf = [], 0, None, []

    def flush():
        nonlocal buf, label
        if book and label is not None and buf:
            units.append({"ref": f"{book}.{label}",
                          "text": "\n".join(stripInlineMarks(x) for x in buf)})
        buf = []

    i = start
    while i < end:
        ln = lines[i].strip()
        if ln in ARNOLD_BOOKS:
            flush(); book += 1; label = None
            i += 1
            continue
        is_story_head = (ln == ln.upper() and STORY_CAPS.match(ln)
                         and not ln.startswith("THE BOOK OF GOOD"))
        if is_story_head:
            # merge wrapped heading lines
            while (i + 1 < end and lines[i + 1].strip()
                   and lines[i + 1].strip() == lines[i + 1].strip().upper()
                   and STORY_CAPS.match(lines[i + 1].strip())
                   and len(lines[i + 1].strip()) < 30):
                ln += " " + lines[i + 1].strip()
                i += 1
            flush()
            label = 0 if label is None else label + 1
            i += 1
            continue
        if book >= 1:
            if label is None:
                label = 0  # book prologue/frame before first story heading
            buf.append(lines[i])
        i += 1
    flush()
    units = [dict(ref=u["ref"],
                  text="\n".join(x for x in u["text"].split("\n") if x.strip()))
             for u in units if len(u["text"].strip()) > 60]
    return writeJson(
        "hitopadesha", "Sir Edwin Arnold", 1861, "Public domain",
        units,
        source={"site": "Project Gutenberg", "ebook": 13268,
                "title": "Indian Poetry: The Book of Good Counsels "
                         "(Hitopadesa), et al."},
        notes=[
            "Arnold condensed rendering; verse epigrams kept inline.",
            "ref = <book>.<story>, book 1-4 in Arnold's order (Winning of "
            "Friends / Parting of Friends / War / Peace); story = sequence "
            "within book, '.0' = book-frame prologue before the first story "
            "heading. Not canonical pañcatantra-style numbering - remap via "
            "story titles.",
        ])


RYDER_BOOK = re.compile(r"^BOOK ([IVX]+)$")


def build_pancatantra():
    lines = readLines(CACHE_KAVYA / "ryder_panchatantra.txt")
    start = next(i for i, l in enumerate(lines)
                 if RYDER_BOOK.match(l.strip())
                 and i > 500
                 and next((x.strip() for x in lines[i + 1:i + 3] if x.strip()), "")
                 .upper().startswith("THE LOSS"))
    units, book, label, buf = [], 0, None, []

    def flush():
        nonlocal buf
        if book and label is not None and buf:
            units.append({"ref": f"{book}.{label}",
                          "text": "\n".join(x for x in buf if x.strip())})
        buf = []

    i = start
    while i < len(lines):
        ln = lines[i]
        m = RYDER_BOOK.match(ln.strip())
        s = ln.strip()
        if m:
            flush(); book = romanToInt(m.group(1)); label = None
            i += 1
            continue
        if (s == s.upper() and STORY_CAPS.match(s) and "BOOK" not in s):
            # merge wrapped second heading line ('...THE BLACK' / 'SNAKE')
            while (i + 1 < len(lines)
                   and (t := lines[i + 1].strip())
                   and t == t.upper() and STORY_CAPS.match(t)
                   and len(t) < 30 and "BOOK" not in t):
                i += 1
            flush()
            label = 0 if label is None else label + 1
            i += 1
            continue
        if book:
            if label is None:
                label = 0  # book prologue before first story heading
            buf.append(ln)
        i += 1
    flush()
    units = [dict(ref=u["ref"],
                  text="\n".join(x for x in u["text"].split("\n") if x.strip()))
             for u in units if len(u["text"].strip()) > 60]
    return writeJson(
        "pancatantra", "Arthur W. Ryder", 1925,
        "Public domain in the USA since 2021-01-01 (published 1925; maximum "
        "95-year term expired whether or not copyright was renewed)",
        units,
        source={"site": "archive.org item the-panchatantra (djVu OCR)",
                "title": "The Panchatantra, trans. Arthur W. Ryder, University "
                         "of Chicago Press, 1925"},
        notes=[
            "Ryder's complete translation of the Tantrakhyayika recension; "
            "his metrical verses are kept inline.",
            "ref = <book>.<story>; story = Ryder's all-caps story headings in "
            "order, '.0' = book prologue. Ryder does not reproduce Sanskrit "
            "kathanaka numbering - remap via story titles/order.",
        ])


ARTHA_CHAP = re.compile(r"^CHAPTER ([IVX]+)\.?")
ARTHA_END = re.compile(r"Thus ends Chapter ([IVXLC]+)[^]]*?in Book ([IVXLC]+)")


def build_arthashastra():
    raw = readLines(CACHE_KAVYA / "shamasastry_arthashastra.txt")
    lines = []
    for ln in raw:
        s = ln.strip()
        if s in ("Kautilya's Arthashastra",) or re.fullmatch(r"\d+", s):
            continue
        if re.match(r"^BOOK [IVX]+\.", s):
            continue              # in-text contents enumeration, not a divider
        lines.append(ln)

    events = []                   # (lineno, kind, data)
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        m = ARTHA_CHAP.match(s)
        if m:
            events.append((i, "chap", romanToInt(m.group(1))))
            i += 1
            continue
        if s.startswith("[Thus ends"):
            block = s
            j = i
            while "]" not in block and j + 1 < len(lines) and j - i < 8:
                j += 1
                block += " " + lines[j].strip()
            me = ARTHA_END.search(block)
            if me:
                events.append((i, "end", romanToInt(me.group(2))))
                i = j + 1
                continue
        i += 1

    cur_book, chap, prev_chap = 1, None, 0
    ev_by_line = {ln: (k, d) for ln, k, d in events}
    out, buf = {}, []
    idx = 0
    while idx < len(lines):
        if idx in ev_by_line:
            kind, data = ev_by_line[idx]
            if kind == "chap":
                if chap is not None and buf:
                    key = f"{cur_book}.{chap}"
                    text = "\n".join(x.strip() for x in buf if x.strip())
                    if len(text) > 80 and (key not in out or len(text) > len(out[key])):
                        out[key] = text
                if data == 1 and prev_chap >= 2:
                    cur_book += 1          # numbering reset -> new book
                elif 1 < data < prev_chap:
                    cur_book += 1          # missed-reset tolerance
                chap, prev_chap = data, data
                buf = []
            else:                   # colophons are unreliable in this OCR
                pass                # (one says 'Book VIII' inside book VII);
                                    # reset detection above is authoritative
            idx += 1
            continue
        buf.append(lines[idx])
        idx += 1
    if chap is not None and buf:
        key = f"{cur_book}.{chap}"
        text = "\n".join(x.strip() for x in buf if x.strip())
        if len(text) > 80 and (key not in out or len(text) > len(out[key])):
            out[key] = text

    units = [{"ref": k, "text": out[k]}
             for k in sorted(out, key=lambda r: tuple(map(int, r.split("."))))]
    return writeJson(
        "arthashastra", "Rudrapatna Shamasastry", 1915, "Public domain",
        units,
        source={"site": "archive.org item Arthasastra_English_Translation",
                "title": "Kautilya's Arthashastra, trans. R. Shamasastry, "
                         "Bangalore, 1915"},
        notes=["ref = <book>.<chapter> per Shamasastry's printed 1915 "
               "numbering; book boundaries recovered from chapter-number "
               "resets (his colophons are unreliable in this transcription - "
               "one says 'Book VIII' mid-book-VII).",
               "His 1915 chapter division of the later books differs slightly "
               "from the critical Kangle edition (e.g. book XI has 6 chapters "
               "here); refs preserve HIS numbering.",
               "The transcription embeds the whole-work contents enumeration "
               "inside Chapter I; BOOK-heading lines inside it were dropped. A "
               "few headings lost to OCR merge neighbouring chapters."])


MANU_VERSE = re.compile(r"^(\d{1,3})\. ")


def build_manusmriti():
    units = []
    for n in range(1, 13):
        lines = stripSacredTextsJunk(htmlBodyLines(CACHE_KAVYA / f"wb_manu{n:02d}.htm"))
        chap_start = next((i for i, l in enumerate(lines)
                           if re.match(r"^CHAPTER", l)), 0)
        v, buf = 0, []

        def flush():
            nonlocal buf
            if buf:
                text = stripInlineMarks(" ".join(buf))
                if len(text) > 20:
                    units.append({"ref": f"{n}.{v}", "text": text})
                buf = []

        for ln in lines[chap_start:]:
            m = MANU_VERSE.match(ln)
            if m:
                flush(); v = int(m.group(1))
                buf.append(ln[m.end():])
            else:
                buf.append(ln)
        flush()
    return writeJson(
        "manusmriti", "Georg Bühler", 1886,
        "Public domain (SBE 25)",
        units,
        source={"site": "Internet Sacred Text Archive (via Wayback snapshots)",
                "url": "https://sacred-texts.com/hin/manu/manu01.htm .. manu12.htm"},
        notes=["Bühler's translation of the Mânava-dharma-çâstra; "
               "ref = <chapter>.<verse> exactly as printed (his verse numbers "
               "follow the Calcutta standard edition).",
               "Bühler's bracketed exegetical footnotes were dropped; inline "
               "Sanskrit glosses retained where they sit inside the verse."])


# --------------------------------------------------------------------------- #

BUILDERS = {
    "ramayana": build_ramayana,
    "mahabharata": build_mahabharata,
    "buddhacarita": build_buddhacarita,
    "sukhavativyuha-larger": build_sukhavati_larger,
    "sukhavativyuha-smaller": build_sukhavati_smaller,
    "vajracchedika": build_vajracchedika,
    "heart": build_heart,
    "meghaduta": build_meghaduta,
    "hitopadesha": build_hitopadesha,
    "pancatantra": build_pancatantra,
    "arthashastra": build_arthashastra,
    "manusmriti": build_manusmriti,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated workIds")
    args = ap.parse_args()
    targets = args.only.split(",") if args.only else list(BUILDERS)
    failed = []
    for wid in targets:
        print(f"building {wid} …")
        try:
            BUILDERS[wid]()
        except Exception as exc:  # noqa: BLE001 — report and continue
            failed.append((wid, repr(exc)))
            print(f"  FAILED {wid}: {exc!r}")
    if failed:
        print("\nFAILURES:")
        for w, e in failed:
            print(f"  {w}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
