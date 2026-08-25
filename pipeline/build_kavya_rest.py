#!/usr/bin/env python3
"""Build the kavya/katha remainder wave from GRETIL corpustei TEI XML +
sa.wikisource + Project Gutenberg PD translations:

  gitagovinda        Jayadeva, GRETIL corpustei TEI (264 lg, 12 prabandhas)
                     EN: Edwin Arnold, The Indian Song of Songs (1875) - canto-level
  satakatraya        Bhartrhari, GRETIL corpustei TEI (Brzezinski; BharSt_c.v markers)
  vetalapancavimsati Somadeva, Kathasaritsagara Sasankavati-lambaka via sa.wikisource
                     (tales 00-25 subpages, Devanagari -> tokenized directly)
                     EN: Arthur W. Ryder, Twenty-Two Goblins (1917) - tale-level
  kumarasambhava     Kalidasa, GRETIL corpustei TEI (Podzeit; Ks_sarga.verse, 8 sargas)
                     EN: Ralph T. H. Griffith, Birth of the War-God (1879) - positional

Text schema mirrors texts/kavya/meghaduta.json: {"id","author","title","kind",
"alignment","units":[{"ref","words":[Devanagari tokens]}]}. Translations follow
trans/meghaduta.json: {"workId","translator","year","license","alignment",
"units":[{"ref","text"}],"source","notes"}.

Catalog: read-modify-write APPEND into public/data/catalog.json (existing
Kālidāsa group for Kumarasambhava; new Jayadeva / Bhartṛhari / Somadeva groups
at END). Run one subcommand per commit: gg|sataka|vetala|kumara.
"""
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "pipeline"))
from sanscript import transliterate, IAST, DEVA  # noqa: E402

CACHE = os.path.join(HERE, ".cache-corpus", "kavya-rest")
OUT_KAVYA = os.path.join(HERE, "public", "data", "texts", "kavya")
OUT_TRANS = os.path.join(HERE, "public", "data", "trans")
CATALOG = os.path.join(HERE, "public", "data", "catalog.json")

STRIP = ".,;:!?\u201c\u201d\u201e\u201f\u00ab\u00bb()[]{}<>|/*\u2014\u2013-\u2026*\u203a\u2039"
LETTER = re.compile(r"[A-Za-z\u00C0-\u024F\u1E00-\u1EFF\u0300-\u036f']")
DEV_LETTER = re.compile(r"[\u0915-\u0939\u093D-\u094F\u0950-\u0957\u0960-\u0963]")
DEV_STRIP = STRIP + "\u0964\u0965\u0966-\u096F0123456789.\u00b7|"


def tokenize(text):
    """IAST whitespace tokenizer (same rules as build_kavya.tokenize)."""
    out = []
    for w in text.split():
        w = w.strip(STRIP).strip()
        if w and LETTER.search(w):
            out.append(w)
    return out


def tokenize_dev(text):
    """Devanagari tokenizer: strip dandas/punct/digits from token edges."""
    out = []
    for w in text.split():
        w = w.strip(DEV_STRIP).strip()
        if w and DEV_LETTER.search(w):
            out.append(w)
    return out


class Refs:
    def __init__(self):
        self.seen = {}

    def uniq(self, base):
        n = self.seen.get(base, 0) + 1
        self.seen[base] = n
        return base if n == 1 else f"{base}.{n}"


def read_tei(fname):
    with open(os.path.join(CACHE, fname), encoding="utf-8") as fh:
        s = fh.read()
    s = s[s.find("<body>"):s.find("</body>")]
    s = re.sub(r"<note\b.*?</note>", " ", s, flags=re.S)
    s = re.sub(r"</?(?:pb|head|fw)\b[^>]*>", " ", s)
    return s


EV = re.compile(r"<div\b([^>]*)>"
                r"|<lg\b([^>]*)>(.*?)</lg>"
                r"|<p\b([^>]*)>(.*?)</p>", re.S)


def events(src):
    for m in EV.finditer(src):
        if m.group(1) is not None:
            yield "div", dict(re.findall(r'([\w:-]+)="([^"]*)"', m.group(1))), None
        elif m.group(2) is not None:
            attrs = dict(re.findall(r'([\w:-]+)="([^"]*)"', m.group(2)))
            yield "lg", attrs, m.group(3)
        else:
            attrs = dict(re.findall(r'([\w:-]+)="([^"]*)"', m.group(4)))
            yield "p", attrs, m.group(5)


def flatten(fragment):
    t = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(t))


def emit(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)
    with open(path, encoding="utf-8") as fh:
        json.load(fh)
    print(f"[rest] wrote {os.path.relpath(path, HERE)} "
          f"({len(obj['units'])} units)")


# --- Sanskrit text builders --------------------------------------------------

def build_lg_xml(work_id, author, title, src, id_re, spot=None):
    refs, units = Refs(), []
    for kind, attrs, inner in events(src):
        if kind != "lg":
            continue
        m = re.fullmatch(id_re, attrs.get("xml:id", ""))
        if not m:
            continue
        words = [transliterate(w, IAST, DEVA) for w in tokenize(flatten(inner))]
        if words:
            units.append({"ref": f"{int(m.group(1))}.{int(m.group(2))}",
                          "words": words})
    out = {"id": work_id, "author": author, "title": title,
           "kind": "verse", "alignment": "surface-form", "units": units}
    if spot:
        joined = " ".join(w for u in units for w in u["words"])
        assert any(all(t in joined for t in ts) for ts in spot), \
            f"spot-check failed for {work_id}"
    return out


def build_gg_text():
    src = read_tei("sa_jayadeva-gItagovinda.xml")
    return build_lg_xml(
        "gitagovinda", "Jayadeva", "Gītagovinda", src,
        r"GG_(\d+)\.(\d+)",
        spot=[["मेघैः", "मेदुरम्"], ["जगदीश", "जय"]])


def build_ks_text():
    src = read_tei("sa_kAlidAsa-kumArasaMbhava.xml")
    return build_lg_xml(
        "kumarasambhava", "Kālidāsa", "Kumārasambhava", src,
        r"Ks_(\d+)\.(\d+)",
        spot=[["तथा", "समक्षम्", "दहता", "मनोभवम्"]])


def build_st_text():
    """BharSt_c.v markers inline; some verses open inside a <p> before their
    nested <lg>. Section headings (niti-/srngara-/vairagya-satakam) precede
    the first lg of each sataka and are dropped."""
    src = read_tei("sa_bhatRhari-zatakatraya.xml")
    marker_re = re.compile(r"\s*(?:\|\||\|)\s*BharSt_\d+\.\d+\s*(?:\|\||\|)\s*")
    ref_re = re.compile(r"BharSt_(\d+)\.(\d+)")
    head_re = re.compile(
        r"^\s*(?:nīti|śṛṅgāra|vairāgya)-śatakam(?:\s+bhartṛhareḥ)?\s*$")
    refs, units = Refs(), []

    def verse(text):
        m = ref_re.search(text)
        if not m:
            return None
        words = [transliterate(w, IAST, DEVA)
                 for w in tokenize(marker_re.sub(" ", text))]
        return (refs.uniq(f"{m.group(1)}.{m.group(2)}"), words) if words else None

    for kind, attrs, inner in events(src):
        if kind == "lg":
            v = verse(flatten(inner))
            if v:
                units.append(v)
        elif kind == "p":
            frag = ""
            m = re.match(r"^\s*([^<]{1,200}?)(?=<lg|\Z)", inner, re.S)
            if m and "<lg" in inner:
                frag, rest = m.group(1), inner[m.end():]
            else:
                rest = inner
            lead = flatten(frag)
            if head_re.fullmatch(lead):
                lead = ""
            v = verse((lead + " " + flatten(rest)).strip())
            if v:
                units.append(v)
    assert len(units) >= 315, f"satakatraya too small: {len(units)}"
    j = " ".join(w for _, ws in units for w in ws)
    assert "बोद्धारो" in j or "बोध्धारो" in j, "sataka 1.2 spot check failed"
    return {"id": "satakatraya", "author": "Bhartṛhari", "title": "Śatakatraya",
            "kind": "verse", "alignment": "surface-form",
            "units": [{"ref": r, "words": ws} for r, ws in units]}


VETALA_JUNK = ("[http", "[[वर्ग", "{|", "|}", "|<br")


def vetala_page(n):
    with open(os.path.join(CACHE, "vetala", f"vp{n:02d}.json"),
              encoding="utf-8") as fh:
        wt = json.load(fh)["parse"]["wikitext"]["*"]
    b = re.sub(r"\{\{header[^}]*\}\}", "", wt, flags=re.S)
    b = b.split("##[[")[0]
    b = b.split("\n==")[0]
    lines = []
    for ln in b.split("\n"):
        s = ln.strip()
        if not s or s in VETALA_JUNK or s == "|":
            continue
        if s.startswith(VETALA_JUNK):
            continue
        if re.search(r"\u1e6dippa\u1e47\u012b|tulan\u012bya", s):
            continue                                   # wikisource commentary
        if re.search(r"सन्धियुक्त पाठः", s):
            continue                                   # recension label
        if re.match(r"^शशाङ्कवतीलम्बक", s) or re.match(r"^द्वादशस्तरङ्ग", s):
            continue                                   # tarañga title lines
        if len(s) < 48 and s.startswith("(") and s.endswith(")") and \
                ("वेताल" in s or "स्तरङ्ग" in s):
            continue                                   # "(pañcamo vetālaḥ)"
        if s.startswith("iti mahākavi"):
            continue                                   # KSS colophon line
        lines.append(s.replace("<br>", "\n").replace("<br/>", "\n"))
    t = re.sub(r"<[^>]+>", "", "\n".join(lines))
    return t.replace("\u0964\u0964", "\u00a7").replace("॥", "\u00a7").replace(
        "||", "\u00a7")


def build_vp_text():
    refs, units = Refs(), []
    per_tale = {}
    for n in range(26):
        seq = 0
        raw = vetala_page(n)
        for ch in raw.split("\u00a7"):
            ch = ch.strip(" \n.\u00b7|\u0966-\u096f0123456789")
            ws = tokenize_dev(ch)
            if len(ws) < 3:
                continue
            seq += 1
            units.append({"ref": refs.uniq(f"{n}.{seq}"), "words": ws})
        per_tale[n] = seq
    assert sum(per_tale.values()) > 600, f"vetala too small: {per_tale}"
    j = " ".join(u["ref"] for u in units)
    print(f"[rest] vetala per-tale counts: {per_tale}")
    return {"id": "vetalapancavimsati",
            "author": "Somadeva",
            "title": "Vetālapañcaviṃśatikā (Śaśāṅkavatīlambaka, KSS 12)",
            "kind": "mixed", "alignment": "surface-form", "units": units}


# --- English translation builders -------------------------------------------

ORD = dict(zip(["First", "Second", "Third", "Fourth", "Fifth", "Sixth",
                "Seventh", "Eighth", "Ninth", "Tenth", "Eleventh"],
               range(1, 12)))


def _read_pg(fname):
    with open(os.path.join(CACHE, fname), encoding="utf-8") as fh:
        return fh.read().replace("\r", "")


def build_gg_trans():
    s = _read_pg("pg25965.txt")
    seg = s[s.find("THE INDIAN SONG OF SONGS.", 4000):
            s.find("THE END OF THE INDIAN SONG OF SONGS")]
    marks = [(m.start(), ORD[m.group(1).title()])
             for m in re.finditer(r"_SARGA THE (\w+)\._", seg)]

    def clean(t):
        t = re.sub(r"\[Footnote \d+:[^\]]*\]", " ", t, flags=re.S)
        keep = []
        for ln in t.split("\n"):
            st = ln.strip()
            if not st:
                keep.append("")
                continue
            if "Govinda entitled" in st:
                continue                       # closing attribution lines
            if st.isupper():
                continue                       # sarga headings + subtitles
            keep.append(st)
        t = "\n".join(keep)
        return re.sub(r"\n{3,}", "\n\n", t).strip()

    intro_end = seg.find("END OF INTRODUCTION.")
    hymn = clean(seg[intro_end + len("END OF INTRODUCTION."):marks[0][0]])
    units = []
    for i, (pos, num) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(seg)
        txt = clean(seg[pos:end])
        if num == 1:
            txt = (hymn + "\n\n" + txt).strip()
        units.append({"ref": str(num), "text": txt})
    total = sum(len(u["text"].split()) for u in units)
    print(f"[rest] arnold GG: 11 sarga units, {total} words")
    return {
        "workId": "gitagovinda", "translator": "Sir Edwin Arnold",
        "year": 1875, "license": "Public domain", "alignment": "canto",
        "units": units,
        "source": {"site": "Project Gutenberg ebook 25965 (Indian Poetry, "
                           "Trübner 1875 ed.)",
                   "title": "The Indian Song of Songs, from the Gîta-Govinda "
                            "of Jayadeva, trans. Edwin Arnold, London 1875"},
        "notes": [
            "Free metrical paraphrase, NOT a literal verse rendering: Arnold "
            "merges, expands and skips refrains throughout.",
            "Units are canto-level (refs = prabandha numbers 1-11); the "
            "daśāvatāra Hymn to Vishnu is folded into unit 1.",
            "Arnold's edition ends at the union scene; GG prabandha 12 has no "
            "English coverage here.",
            "Introduction and closing attribution couplets are Arnold's own "
            "and omitted."],
    }


def build_ks_trans():
    s = _read_pg("pg31968.txt")
    start = s.find("Canto First.")
    end = s.find("TRANSCRIBER'S NOTES")
    seg = s[start:end]
    parts = re.split(r"\n(?:Canto (\w+)\.)\n", seg)
    names = list(ORD)[:len(parts) // 2]
    units = []
    for ci, name in enumerate(names, 1):
        body = parts[ci * 2]
        body = re.sub(r'^\s*_+[^_\n]+_+\s*', '', body)      # subtitle italics
        stanzas = [b for b in re.split(r"\n\s*\n", body) if b.strip()]
        for si, st in enumerate(stanzas, 1):
            txt = "\n".join(ln.strip() for ln in st.strip().split("\n"))
            txt = txt.strip('"')
            if txt:
                units.append({"ref": f"{ci}.{si}", "text": txt})
    got = {}
    for u in units:
        got[u["ref"].split(".")[0]] = got.get(u["ref"].split(".")[0], 0) + 1
    print(f"[rest] griffith KuS stanza/canto: {got} vs GRETIL "
          f"{dict(zip(range(1, 8), [60, 63, 76, 46, 86, 95]))}")
    return {
        "workId": "kumarasambhava", "translator": "Ralph T. H. Griffith",
        "year": 1879, "license": "Public domain", "alignment": "loose",
        "units": units,
        "source": {"site": "Project Gutenberg ebook 31968",
                   "title": "The Birth of the War-God: A Poem by Kálidása, "
                            "trans. R.T.H. Griffith, 2nd ed., Trübner 1879"},
        "notes": [
            "Metrical verse rendering of cantos 1-7 only; Griffith's edition "
            "does not cover sarga 8.",
            "Griffith's stanzas are remapped positionally onto the GRETIL "
            "(Podzeit) sarga.v verse order within each canto; stanza counts "
            "differ slightly per canto, so tail verses may lack English.",
            "Griffith followed Stenzler's edition; minor verse-order/reading "
            "divergences from Podzeit are expected."],
    }


# Ryder tale -> our KSS tale number (content-matched; see report).
RYDER_MAP = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7, 8: 8, 9: 9,
             10: 11, 11: 12, 12: 13, 13: 14, 15: 16, 16: 17, 17: 24,
             18: 18, 19: 19, 20: 22, 21: 23}
RYDER_CONF = {2: "probable", 5: "probable", 9: "probable", 16: "probable",
              17: "probable", 19: "probable"}
NUMW = ["FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "SIXTH", "SEVENTH",
        "EIGHTH", "NINTH", "TENTH", "ELEVENTH", "TWELFTH", "THIRTEENTH",
        "FOURTEENTH", "FIFTEENTH", "SIXTEENTH", "SEVENTEENTH", "EIGHTEENTH",
        "NINETEENTH", "TWENTIETH", "TWENTY-FIRST", "TWENTY-SECOND"]


def build_vp_trans():
    s = _read_pg("pg52309.txt")
    seg = s[s.find("*** START OF THE PROJECT GUTENBERG EBOOK TWENTY-TWO"):
            s.find("*** END OF THE PROJECT GUTENBERG EBOOK TWENTY-TWO")]
    heads = [m.start() for m in
             re.finditer(r"^(" + "|".join(NUMW) + r") GOBLIN$", seg, re.M)]
    heads.append(seg.find("*** END OF THE PROJECT GUTENBERG"))
    tales = {}
    for i in range(len(NUMW)):
        blk = seg[heads[i]:heads[i + 1]]
        ln = blk.split("\n")
        body = [x for x in ln[1:] if x.strip() and not x.strip().startswith("_")]
        txt = re.sub(r"\s+", " ", " ".join(body)).strip()
        tales[i + 1] = txt
    units = []
    mapping = {}
    for ryder_no, our_no in sorted(RYDER_MAP.items()):
        units.append({"ref": str(our_no), "text": tales[ryder_no]})
        mapping[ryder_no] = our_no
    print(f"[rest] ryder mapped {len(units)}/22 tales -> KSS tales "
          f"{sorted(mapping.values())}; unmapped Ryder: "
          f"{sorted(set(RYDER_MAP) | set(range(1, 23)) - set(RYDER_MAP))}")
    return {
        "workId": "vetalapancavimsati", "translator": "Arthur W. Ryder",
        "year": 1917, "license": "Public domain", "alignment": "loose",
        "units": units,
        "source": {"site": "Project Gutenberg ebook 52309",
                   "title": "Twenty-Two Goblins, trans. Arthur W. Ryder, "
                            "University of California Press 1917"},
        "notes": [
            "Prose retelling of the Vetāla cycle; refs are OUR Kathāsaritsāgara "
            "tale numbers, matched by content, not position.",
            "Ryder follows the Śivadāsa prose recension (22 tales); this text "
            "is Somadeva's KSS Śaśāṅkavatīlambaka metrical version (25 tales + "
            "frame), so several tales have no English counterpart.",
            "High-confidence matches: Ryder 1→1, 3→3, 4→4, 6→6, 8→8, 10→11, "
            "11→12, 12→13, 13→14, 15→16, 18→18, 20→22, 21→23; probable: 2→2, "
            "5→5, 9→9, 16→17, 17→24, 19→19.",
            "Ryder 14 and 22 left unmapped; KSS tales 10, 15, 20, 21, 25 and "
            "the frame tale 00 remain Sanskrit-only."],
    }


# --- catalog -----------------------------------------------------------------

def upsert(author_name, key, work):
    with open(CATALOG, encoding="utf-8") as fh:
        cat = json.load(fh)
    grp = next((a for a in cat["authors"] if a.get("key") == key), None)
    if grp is None:
        grp = {"name": author_name, "key": key, "works": []}
        cat["authors"].append(grp)                     # new groups at END
    grp["works"] = [w for w in grp["works"] if w["id"] != work["id"]]
    grp["works"].append(work)
    with open(CATALOG, "w", encoding="utf-8") as fh:
        json.dump(cat, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    with open(CATALOG, encoding="utf-8") as fh:
        json.load(fh)
    print(f"[rest] catalog: {author_name}/{key} <- {work['id']} "
          f"(group works={len(grp['works'])})")


def rel(p):
    return os.path.relpath(p, os.path.join(HERE, "public", "data")).replace(
        os.sep, "/")


# --- drivers -----------------------------------------------------------------

WORKS = {
    "gg": dict(
        text=build_gg_text,
        trans=build_gg_trans,
        catalog=lambda t, tr: upsert(
            "Jayadeva", "jayadeva",
            {"id": "gitagovinda", "title": "Gītagovinda", "titleZh": "牧童歌",
             "urn": "urn:sanskrit:gitagovinda",
             "license": "GRETIL CC BY-NC-SA 4.0 (text)", "kind": "verse",
             "files": [rel(os.path.join(OUT_KAVYA, "gitagovinda.json"))],
             "unitCount": len(t["units"]),
             "edition": "GRETIL corpustei ed. (pausa text, 12 prabandhas, "
                        "264 numbered padas incl. refrain repeats)",
             "translation": {
                 "translator": "Sir Edwin Arnold", "year": 1875,
                 "license": "Public domain",
                 "files": [rel(os.path.join(OUT_TRANS, "gitagovinda.json"))],
                 "alignment": "canto"}})),
    "sataka": dict(
        text=build_st_text, trans=None,
        catalog=lambda t, tr: upsert(
            "Bhartṛhari", "bhartrhari",
            {"id": "satakatraya", "title": "Śatakatraya", "titleZh": "三百咏",
             "urn": "urn:sanskrit:satakatraya",
             "license": "GRETIL CC BY-NC-SA 4.0 (text)", "kind": "verse",
             "files": [rel(os.path.join(OUT_KAVYA, "satakatraya.json"))],
             "unitCount": len(t["units"]),
             "edition": "Brzezinski (GRETIL corpustei): Nīti 109, Śṛṅgāra 104, "
                        "Vairāgya 108 marker instances; repeated verses carry "
                        ".2 suffixes",
             "translation": None})),
    "vetala": dict(
        text=build_vp_text, trans=build_vp_trans,
        catalog=lambda t, tr: upsert(
            "Somadeva", "somadeva",
            {"id": "vetalapancavimsati",
             "title": "Vetālapañcaviṃśatikā (Śaśāṅkavatīlambaka)",
             "titleZh": "僵尸鬼故事二十五则",
             "urn": "urn:sanskrit:vetalapancavimsati",
             "license": "Wikisource CC BY-SA 4.0 (text)", "kind": "mixed",
             "files": [rel(os.path.join(OUT_KAVYA,
                                        "vetalapancavimsati.json"))],
             "unitCount": len(t["units"]),
             "edition": "sa.wikisource वेतालपञ्चविंशतिः = Somadeva, "
                        "Kathāsaritsāgara lambaka 12 (taraṅgas 8-32), frame + "
                        "25 tales; wikisource page header attributes Somadeva",
             "translation": {
                 "translator": "Arthur W. Ryder (Twenty-Two Goblins, parallel "
                               "recension)", "year": 1917,
                 "license": "Public domain",
                 "files": [rel(os.path.join(OUT_TRANS,
                                            "vetalapancavimsati.json"))],
                 "alignment": "loose"}})),
    "kumara": dict(
        text=build_ks_text, trans=build_ks_trans,
        catalog=lambda t, tr: upsert(
            "Kālidāsa", "kalidasa",
            {"id": "kumarasambhava", "title": "Kumārasambhava",
             "titleZh": "鸠摩罗出世", "urn": "urn:sanskrit:kumarasambhava",
             "license": "GRETIL CC BY-NC-SA 4.0 (text)", "kind": "verse",
             "files": [rel(os.path.join(OUT_KAVYA, "kumarasambhava.json"))],
             "unitCount": len(t["units"]),
             "edition": "Podzeit (GRETIL corpustei), 8-sarga pariyāpta "
                        "recension (60+63+76+46+86+95+95+91 verses); the "
                        "17-sarga ādirūpa recension is a separate tradition",
             "translation": {
                 "translator": "Ralph T. H. Griffith", "year": 1879,
                 "license": "Public domain",
                 "files": [rel(os.path.join(OUT_TRANS,
                                            "kumarasambhava.json"))],
                 "alignment": "loose"}})),
}


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    keys = list(WORKS) if which == "all" else [which]
    for k in keys:
        cfg = WORKS[k]
        t = cfg["text"]()
        emit(os.path.join(OUT_KAVYA, f"{t['id']}.json"), t)
        tr = cfg["trans"]() if cfg["trans"] else None
        if tr:
            emit(os.path.join(OUT_TRANS, f"{tr['workId']}.json"), tr)
        cfg["catalog"](t, tr)


if __name__ == "__main__":
    main()
