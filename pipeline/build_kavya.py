#!/usr/bin/env python3
"""Build classical kāvya + śāstra works from GRETIL corpustei TEI XML (IAST,
UTF-8). Emits public/data/texts/kavya/*.json and public/data/texts/shastra/*.json
mirroring the Bhagavadgītā schema (see build_bhg_text.py): Devanagari display
tokens keyed for surface-form alignment; refs from source markup.

Sources cached under .cache-corpus/kavya-kavya/ and .cache-corpus/kavya-shastra/.
Prose (sūtra, kathā, drama speech) is split into daṇḍa units of <=60 words.

Catalog: emits public/data/catalog-fragments/kavya-shastra.json (authors with
work arrays, same shape as public/data/catalog.json entries).
"""
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "pipeline"))
from sanscript import transliterate, IAST, DEVA  # noqa: E402

CACHE_KAVYA = os.path.join(HERE, ".cache-corpus", "kavya-kavya")
CACHE_SHASTRA = os.path.join(HERE, ".cache-corpus", "kavya-shastra")
OUT_KAVYA = os.path.join(HERE, "public", "data", "texts", "kavya")
OUT_SHASTRA = os.path.join(HERE, "public", "data", "texts", "shastra")
FRAGMENT = os.path.join(HERE, "public", "data", "catalog-fragments",
                        "kavya-shastra.json")

LICENSE = "GRETIL CC BY-NC-SA 4.0 (text)"

MAX_WORDS = 60
STRIP = ".,;:!?\u201c\u201d\u201e\u201f\u00ab\u00bb()[]{}<>|/*\u2014\u2013-…*›‹"
LETTER = re.compile(r"[A-Za-z\u00C0-\u024F\u1E00-\u1EFF\u0300-\u036f']")
# div open | lg block | p block (body-level scanning)
EV = re.compile(r"<div\b([^>]*)>"
                r"|<lg\b([^>]*)>(.*?)</lg>"
                r"|<p\b([^>]*)>(.*?)</p>", re.S)


# --- generic helpers --------------------------------------------------------

def read_source(fname, shastra=False):
    base = CACHE_SHASTRA if shastra else CACHE_KAVYA
    with open(os.path.join(base, fname), encoding="utf-8") as fh:
        s = fh.read()
    b = s.find("<body>")
    e = s.find("</body>")
    s = s[b:e if e > 0 else len(s)]
    s = re.sub(r"<note\b.*?</note>", " ", s, flags=re.S)   # analysis dupes
    s = re.sub(r"</?(?:pb|head|fw)\b[^>]*>", " ", s)       # editorial furniture
    return s


def events(src):
    """Yield ("div", attrs, None) / ("lg", attrs, inner) / ("p", attrs, inner)."""
    for m in EV.finditer(src):
        if m.group(1) is not None:
            yield "div", dict(re.findall(r'([\w:-]+)="([^"]*)"', m.group(1))), None
        elif m.group(2) is not None:
            attrs = dict(re.findall(r'([\w:-]+)="([^"]*)"', m.group(2)))
            yield "lg", attrs, m.group(3)
        else:
            attrs = dict(re.findall(r'([\w:-]+)="([^"]*)"', m.group(4)))
            yield "p", attrs, m.group(5)


def flatten(fragment, pre=None):
    """XML fragment -> plain text (tags to spaces, entities resolved)."""
    t = re.sub(r"<[^>]+>", " ", fragment)
    t = html.unescape(t)
    t = re.sub(r"\s+", " ", t)
    return pre(t) if pre else t


def tokenize(text):
    out = []
    for w in text.split():
        w = w.strip(STRIP).strip()
        if w and LETTER.search(w):
            out.append(w)
    return out


def dantha_units(text, dot_enders=False, max_words=MAX_WORDS):
    """Split prose into daṇḍa-delimited chunks of <= max_words tokens."""
    pat = r"\|\||\||//|/|!|\?|—|–|--|·|;"
    if dot_enders:
        pat += r"|(?<=\.)\s"
    parts = [p for p in re.split(pat, text)]
    units: list = []
    buf: list[str] = []
    for part in parts:
        ws = tokenize(part)
        if not ws:
            continue
        if len(buf) + len(ws) > max_words and buf:
            units.append(buf)
            buf = []
        if len(ws) > max_words:                     # hard-split oversized run
            for i in range(0, len(ws), max_words):
                units.append(ws[i:i + max_words])
            continue
        buf.extend(ws)
        if len(buf) >= max_words:
            units.append(buf)
            buf = []
    if buf:
        units.append(buf)
    return units


class Refs:
    """Per-work ref uniquifier."""

    def __init__(self):
        self.seen: dict[str, int] = {}

    def uniq(self, base):
        n = self.seen.get(base, 0) + 1
        self.seen[base] = n
        return base if n == 1 else f"{base}.{n}"


# --- pre-cleaners -----------------------------------------------------------

def _pre_artha(t):
    t = t.replace("^", " ")                       # decomposed external sandhi
    t = re.sub(r"(?<=[A-Za-z\u00C0-\u024F])\.(?=[A-Za-z\u00C0-\u024F])", " ", t)
    return t                                      # compound-member periods


def _pre_kama(t):
    t = re.sub(r"\(\(\d+\)\)", " ", t)            # footnote anchors
    t = re.sub(r"\[\s*\d+\s*\]", " ", t)          # variant lemmata
    t = re.sub(r"(?<=[A-Za-z\u00C0-\u024F]):(?=[A-Za-z\u00C0-\u024F])", "", t)
    return t


def _plain(t):
    return t.replace("[", " ").replace("]", " ")


# --- work builders ----------------------------------------------------------

def _lg_units(attrs, inner, ref_re, fmt, refs, pre=None):
    m = re.search(ref_re, attrs.get("xml:id", ""))
    out = []
    if m:
        words = tokenize(flatten(inner, pre))
        if words:
            out.append((refs.uniq(fmt(m)), words))
    return out


def build_lgid(work, src):
    """Verses carrying their ref in <lg xml:id>: Meghadūta, Raghuvaṃśa,
    Ṛtusaṃhāra, Kirātārjunīya, Caurapañcāśikā, Manusmṛti (+ Śākuntala verse
    pass used by build_sakuntala)."""
    refs, units = Refs(), []
    for kind, attrs, inner in events(src):
        if kind == "lg":
            units += _lg_units(attrs, inner, work["ref_re"], work["fmt"], refs)
    return units


def build_marker(work, src):
    """Verses with ref embedded in text (// MSpv_c.v //, // Hit_c.v //,
    ||Panc_c.v||) + prose <p> tracked under the current chapter."""
    refs, units, prose_no = Refs(), [], {}
    marker_re = re.compile(work["ref_re"])
    for kind, attrs, inner in events(src):
        if kind == "lg":
            text = flatten(inner)
            m = marker_re.search(text)
            if not m:
                continue
            words = tokenize(marker_re.sub(" ", text))
            if words:
                units.append((refs.uniq(work["fmt"](m)), words))
                prose_no.setdefault(m.group(1), 0)
        elif kind == "p":
            text = flatten(inner)
            words = tokenize(text)
            if not words:
                continue
            if len(words) < 4 and not re.search(r"[|/!?.]", text):
                continue                          # section heading, not prose
            ahead = marker_re.search(text)
            ch = ahead.group(1) if ahead else next(iter(prose_no), "0")
            prose_no[ch] = prose_no.get(ch, 0) + 1
            for ws in dantha_units(text, dot_enders=work.get("dot")):
                units.append((refs.uniq(f"{ch}.p{prose_no[ch]}"), ws))
    return units


def build_sakuntala(work, src):
    """7 aṅkas; verse <lg xml:id='KSak_a.v'> + speech prose <p xml:id='KSak_X'>."""
    refs, units, act = Refs(), [], "1"
    for kind, attrs, inner in events(src):
        if kind == "div":
            if attrs.get("n"):
                act = attrs["n"]
        elif kind == "lg":
            units += _lg_units(attrs, inner, r"KSak_(\d+)\.(\d+)",
                               lambda m: f"{int(m.group(1))}.{int(m.group(2))}",
                               refs)
        elif kind == "p":
            pid = attrs.get("xml:id", "")
            base = pid.split("KSak_", 1)[-1]
            if not base or not pid.startswith("KSak_"):
                continue
            text = flatten(inner)
            if not tokenize(text):
                continue
            if len(tokenize(text)) < 4 and not re.search(r"[|/!?.]", text):
                continue                          # bare speaker cue
            subs = dantha_units(text)
            units.append((refs.uniq(base), subs[0]))
            for i, ws in enumerate(subs[1:], 2):
                units.append((refs.uniq(f"{base}.{i}"), ws))
    return units


def build_arthashastra(work, src):
    """Sūtra paragraphs keyed by inline KAZ_bb.cc.ss[a-b]/ markers."""
    refs, units = Refs(), []
    marker_re = re.compile(r"KAZ(\d{1,2})\.(\d{1,2})\.(\d{1,2})([a-z]{0,2})/")
    for kind, attrs, inner in events(src):
        if kind != "p":
            continue
        text = flatten(inner, _pre_artha)
        hits = list(marker_re.finditer(text))
        if not hits:
            continue                              # edition front matter
        for i, m in enumerate(hits):
            seg = text[m.end():hits[i + 1].start() if i + 1 < len(hits) else len(text)]
            ref = (f"{int(m.group(1))}.{int(m.group(2))}."
                   f"{int(m.group(3))}{m.group(4)}")
            for j, ws in enumerate(dantha_units(seg)):
                units.append((refs.uniq(ref if j == 0 else f"{ref}.{j + 1}"), ws))
    return units


def build_kamasutra(work, src):
    """Numbered sūtras b.c.s inside <p>; edition headers carry no refs.
    A trailing French apparatus <p> (Yaśodhara notes / glossary) is cut off."""
    refs, units = Refs(), []
    ref_re = re.compile(r"(?<![\w.])(\d+\.\d+\.\d+)([a-z]{0,2})?(?![\w.-])")
    french = re.compile(r"\b(?:selon|cf\.|infra|supra|renvoyant|mentionne"
                        r"|référence|glossaire|snr\.)\b")
    for kind, attrs, inner in events(src):
        if kind != "p":
            continue
        text = flatten(inner, _pre_kama)
        if len(french.findall(text)) >= 2:
            break                                 # apparatus block reached
        hits = list(ref_re.finditer(text))
        if not hits:
            continue
        for i, m in enumerate(hits):
            seg = text[m.end():hits[i + 1].start() if i + 1 < len(hits) else len(text)]
            base = m.group(1) + (m.group(2) or "")
            for j, ws in enumerate(dantha_units(seg, dot_enders=True)):
                units.append((refs.uniq(base if j == 0 else f"{base}.{j + 1}"),
                              ws))
    return units


def build_tantrakhyayika(work, src):
    """Story sections '[c,s : …]' head each prose block; verses flow inline."""
    refs, units = Refs(), []
    sec_re = re.compile(r"^\[\s*(\d+)\s*,\s*(\d+)")
    cur, buf = None, []

    def flush():
        if cur and buf:
            for i, ws in enumerate(dantha_units(" ".join(buf))):
                units.append((refs.uniq(f"{cur[0]}.{cur[1]}.{i + 1}"), ws))

    for kind, attrs, inner in events(src):
        if kind == "p":
            raw = flatten(inner).strip()          # brackets intact for header
            m = sec_re.match(raw)
            if m and len(raw) < 80:
                flush()
                cur, buf = (m.group(1), m.group(2)), []
                continue
            if raw:
                buf.append(_plain(raw))
        elif kind == "lg":
            buf.append(_plain(flatten(inner)))
    flush()
    return units


# --- work registry ----------------------------------------------------------

WORKS = [
    dict(id="meghaduta", src="sa_kAlidAsa-meghadUta-acc-vallabhadeva.xml",
         shastra=False, parser=build_lgid, kind="verse",
         author="Kālidāsa", key="kalidasa", title="Meghadūta",
         edition="Vallabhadeva recension (Hultzsch 1911)",
         ref_re=r"KMdV_(\d+)", fmt=lambda m: str(int(m.group(1)))),
    dict(id="raghuvamsa", src="sa_kAlidAsa-raghuvaMza.xml",
         shastra=False, parser=build_lgid, kind="verse",
         author="Kālidāsa", key="kalidasa", title="Raghuvaṃśa",
         ref_re=r"Ragh_(\d+)\.(\d+)",
         fmt=lambda m: f"{int(m.group(1))}.{int(m.group(2))}"),
    dict(id="abhijnanasakuntala", src="sa_kAlidAsa-abhijJAnazakuntala.xml",
         shastra=False, parser=build_sakuntala, kind="mixed",
         author="Kālidāsa", key="kalidasa", title="Abhijñānaśākuntala",
         ref_re=None, fmt=None),
    dict(id="rtusamhara", src="sa_kAlidAsa-RtusaMhAra.xml",
         shastra=False, parser=build_lgid, kind="verse",
         author="Kālidāsa", key="kalidasa", title="Ṛtusaṃhāra",
         ref_re=r"KalRs_(\d+)\.(\d+)",
         fmt=lambda m: f"{int(m.group(1))}.{int(m.group(2))}"),
    dict(id="kiratarjuniya", src="sa_bhAravi-kirAtArjunIya.xml",
         shastra=False, parser=build_lgid, kind="verse",
         author="Bhāravi", key="bharavi", title="Kirātārjunīya",
         ref_re=r"BhKir_(\d+)\.(\d+)",
         fmt=lambda m: f"{int(m.group(1))}.{int(m.group(2))}"),
    dict(id="sisupalavadha", src="sa_mAgha-zizupAlavadha.xml",
         shastra=False, parser=build_marker, kind="verse",
         author="Māgha", key="magha", title="Śiśupālavadha",
         ref_re=r"MSpv_(\d+)\.(\d+)",
         fmt=lambda m: f"{int(m.group(1))}.{int(m.group(2))}"),
    dict(id="caurapancasika", src="sa_bilhaNa-caurapaJcAzikA.xml",
         shastra=False, parser=build_lgid, kind="verse",
         author="Bilhaṇa", key="bilhana", title="Caurapañcāśikā",
         ref_re=r"BiCaup_(\d+)", fmt=lambda m: str(int(m.group(1)))),
    dict(id="arthasastra", src="sa_kauTilya-arthazAstra.xml",
         shastra=True, parser=build_arthashastra, kind="prose",
         author="Kauṭilya", key="kautilya", title="Arthaśāstra",
         ref_re=None, fmt=None),
    dict(id="manusmrti", src="sa_manusmRti.xml",
         shastra=True, parser=build_lgid, kind="verse",
         author="Manu (trad.)", key="manu",
         title="Mānavadharmaśāstra (Manusmṛti)",
         ref_re=r"Manu_(\d+)\.(\d+)",
         fmt=lambda m: f"{int(m.group(1))}.{int(m.group(2))}"),
    dict(id="hitopadesa", src="sa_nArAyaNa-hitopadeza.xml",
         shastra=True, parser=build_marker, kind="mixed",
         author="Nārāyaṇa Paṇḍita", key="narayana-pandita", title="Hitopadeśa",
         ref_re=r"Hit_(\d+)\.(\d+)",
         fmt=lambda m: f"{int(m.group(1))}.{int(m.group(2))}"),
    dict(id="tantrakhyayika", src="sa_tantrAkhyAyika-1-2.xml",
         shastra=True, parser=build_tantrakhyayika, kind="prose",
         author="Anonymous", key="anonymous",
         title="Tantrākhyāyikā (Pañcatantra, ch. 1–2)",
         ref_re=None, fmt=None),
    dict(id="pancatantra", src="sa_viSNuzarman-paJcatantra.xml",
         shastra=True, parser=build_marker, kind="mixed",
         author="Viṣṇuśarman (trad.)", key="vishnusharman",
         title="Pañcatantra",
         ref_re=r"Panc_(\d+)\.(\d+)",
         fmt=lambda m: f"{int(m.group(1))}.{int(m.group(2))}"),
    dict(id="kamasutra", src="sa_vAtsyAyana-kAmasUtra.xml",
         shastra=True, parser=build_kamasutra, kind="prose",
         author="Vātsyāyana", key="vatsyayana", title="Kāmasūtra",
         ref_re=None, fmt=None),
]


# --- driver -----------------------------------------------------------------

def build(work):
    src = read_source(work["src"], shastra=work["shastra"])
    units = work["parser"](work, src)
    out = {"id": work["id"], "author": work["author"], "title": work["title"],
           "kind": work["kind"], "alignment": "surface-form",
           "units": [{"ref": ref, "words": [transliterate(w, IAST, DEVA)
                                           for w in words]}
                     for ref, words in units]}
    out_dir = OUT_SHASTRA if work["shastra"] else OUT_KAVYA
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{work['id']}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    with open(path, encoding="utf-8") as fh:      # validity check
        json.load(fh)
    return path, len(units)


def catalog_fragment(built):
    authors: dict[str, dict] = {}
    for work in WORKS:
        path, count = built[work["id"]]
        rel = os.path.relpath(path, os.path.join(HERE, "public", "data"))
        a = authors.setdefault(work["key"], {"name": work["author"],
                                             "key": work["key"], "works": []})
        entry = {"id": work["id"], "title": work["title"],
                 "urn": f"urn:sanskrit:{work['id']}", "license": LICENSE,
                 "files": [rel.replace(os.sep, "/")], "unitCount": count}
        if work.get("edition"):
            entry["edition"] = work["edition"]
        a["works"].append(entry)
    frag = {"authors": list(authors.values())}
    os.makedirs(os.path.dirname(FRAGMENT), exist_ok=True)
    with open(FRAGMENT, "w", encoding="utf-8") as fh:
        json.dump(frag, fh, ensure_ascii=False, indent=1)
    with open(FRAGMENT, encoding="utf-8") as fh:
        json.load(fh)
    return FRAGMENT


def main() -> None:
    built = {}
    for work in WORKS:
        path, count = build(work)
        built[work["id"]] = (path, count)
        print(f"[kavya] {work['id']:22s} {count:5d} units -> "
              f"{os.path.relpath(path, HERE)}")
    frag = catalog_fragment(built)

    # spot checks
    meg = json.load(open(os.path.join(OUT_KAVYA, "meghaduta.json"),
                         encoding="utf-8"))
    with open(os.path.join(CACHE_KAVYA,
                           "sa_kAlidAsa-meghadUta-acc-vallabhadeva.xml"),
              encoding="utf-8") as fh:
        raw = fh.read()
    ok_meg = raw.find("kaś cit kāntāvirahaguruṇā") > 0 and \
        meg["units"][0]["ref"] == "1"
    manu = {u["ref"]: u for u in json.load(
        open(os.path.join(OUT_SHASTRA, "manusmrti.json"),
             encoding="utf-8"))["units"]}
    ok_manu = "1.1" in manu and manu["1.1"]["words"][:2] == \
        ["मनुम्", "एकाग्रम्"]
    print(f"[kavya] meghaduta opening 'kaś cit kāntā-': {ok_meg}; "
          f"manusmrti 1.1: {ok_manu}; fragment -> {os.path.relpath(frag, HERE)}")


if __name__ == "__main__":
    main()
