#!/usr/bin/env python3
"""Build six Buddhist Sanskrit works from GRETIL UTF-8 IAST e-texts.

Sources (.cache-corpus/buddh-*/, fetched on demand via curl --retry):
  buddh-carita/sa_azvaghoSa-buddhacarita-alt.htm
                              Aśvaghoṣa, Buddhacarita cantos 1-14 (Skt.
                              complete), E.H. Johnston ed. 1935 (DSBC input;
                              verse <p> blocks with inline "Bc_C.V //" refs)
  buddh-lalitav/sa_lalitavistara.htm
                              Lalitavistara, P.L. Vaidya ed. 1958; prose <p>
                              + verse <p> ("// Lal_P.V //") under
                              "START Parivarta N" headers
  buddh-sukh/sa_sukhAvatIvyUha.htm       Larger Sukhāvatīvyūha (Fujita input)
  buddh-sukh/sa_smaller-sukhAvatIvyUha.htm  Smaller Sukhāvatīvyūha (Fujita)
  buddh-pp/sa_prajJApAramitAhRdayasUtra.htm  Heart Sūtra (Prajñāpāramitāhṛdaya)
  buddh-pp/sa_vajracchedikA-prajJApAramitA.htm  Diamond Sūtra (Vaidya 1961)

Unit schema mirrors build_epics.py / build_bhg_text.py:
{"id","author","title","kind","alignment","units":[{"ref","words"}]} with
Devanagari display tokens via sanscript.transliterate(IAST->DEVA). All six
mix verse and prose -> kind is "prose". Refs are chapter.sutta where the
edition marks them (Bc canto.verse; LV parivarta.seq), else sequential
integers (both Sukhāvatīvyūhas, Heart, Diamond); daṇḍa-split ≤60 words,
continuations getting letter suffixes ("2.3b", ...).

Tokenizing differs from build_epics.py in ONE deliberate way: hyphens are
DELETED (joined), not treated as word separators — Buddhist editions use
hyphens for compound-internal word division ("tad-buddhakṣetraṃ",
"mahā-mantra") and page-break hyphenation, so the surface form has no break.

Diamond Sūtra page markers (<span class="bold">Vaidya NN</span> /
"Vajr, Vaidya NN") are dropped; other bold spans carry real text mid-word
("samya<b>ksaṃ</b>buddho") and are kept inline. Inline "PNN" page markers in
the Larger Sukhāvatīvyūha vanish under the lone-consonant filter of
tokenize() (digit strip leaves "P").

Output: public/data/texts/buddhist/<work>-partNN.json, each part ≤8MB.
Catalog: fragment public/data/catalog-fragments/buddhist.json ONLY — a
collector merges fragments into catalog.json later (avoids merge races).
"""
import html
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "pipeline"))
from sanscript import transliterate, IAST, DEVA  # noqa: E402

CACHE_CARITA = os.path.join(HERE, ".cache-corpus", "buddh-carita")
CACHE_LALITAV = os.path.join(HERE, ".cache-corpus", "buddh-lalitav")
CACHE_SUKH = os.path.join(HERE, ".cache-corpus", "buddh-sukh")
CACHE_PP = os.path.join(HERE, ".cache-corpus", "buddh-pp")
OUT_DIR = os.path.join(HERE, "public", "data", "texts", "buddhist")
FRAG_DIR = os.path.join(HERE, "public", "data", "catalog-fragments")

GRETIL = "https://gretil.sub.uni-goettingen.de/gretil"
CORPUSTEI = GRETIL + "/corpustei/transformations/html"

CARITA_SRC = os.path.join(CACHE_CARITA, "sa_azvaghoSa-buddhacarita-alt.htm")
CARITA_URL = CORPUSTEI + "/sa_azvaghoSa-buddhacarita-alt.htm"
LALITAV_SRC = os.path.join(CACHE_LALITAV, "sa_lalitavistara.htm")
LALITAV_URL = CORPUSTEI + "/sa_lalitavistara.htm"
SUKH_BIG_SRC = os.path.join(CACHE_SUKH, "sa_sukhAvatIvyUha.htm")
SUKH_BIG_URL = CORPUSTEI + "/sa_sukhAvatIvyUha.htm"
SUKH_SMALL_SRC = os.path.join(CACHE_SUKH, "sa_smaller-sukhAvatIvyUha.htm")
SUKH_SMALL_URL = CORPUSTEI + "/sa_smaller-sukhAvatIvyUha.htm"
HEART_SRC = os.path.join(CACHE_PP, "sa_prajJApAramitAhRdayasUtra.htm")
HEART_URL = CORPUSTEI + "/sa_prajJApAramitAhRdayasUtra.htm"
DIAMOND_SRC = os.path.join(CACHE_PP, "sa_vajracchedikA-prajJApAramitA.htm")
DIAMOND_URL = CORPUSTEI + "/sa_vajracchedikA-prajJApAramitA.htm"

MAX_WORDS = 60  # prose unit ceiling (matches Unit docstring in src/api.ts)
MAX_PART_BYTES = 8 * 1024 * 1024  # per-part output cap

LICENSE = "GRETIL attribution"


def ensure(src: str, url: str) -> None:
    """Fetch missing cache files with curl (GRETIL TLS is flaky: retry hard)."""
    if os.path.exists(src) and os.path.getsize(src) > 0:
        return
    os.makedirs(os.path.dirname(src), exist_ok=True)
    cmd = ["curl", "-sS", "--retry", "5", "--retry-all-errors",
           "--retry-delay", "2", "-o", src, url]
    subprocess.run(cmd, check=True)


# --- tokenization (conventions shared with build_epics.py) ------------------

LETTER_RE = re.compile(r"[A-Za-z\u0100-\u017f\u1e00-\u1eff]")
# edge punctuation stripped from tokens; apostrophes NOT included because
# GRETIL marks avagraha with them and sanscript maps ' -> ऽ (Devanagari).
EDGE_STRIP = "|‖/\\()[]{}.,;:?!*<>«»“”„–—-_@"


def tokenize(seg: str):
    """Whitespace tokens minus punctuation/digits and GRETIL critical-
    apparatus markers (( ) [ ] ? * _ mark variants/lacunae/doubtful akṣaras
    -> parens/brackets deleted, content KEPT — matches build_epics.py).
    Hyphens are deleted rather than spaced: they mark compound-internal
    division / page-break hyphenation (see module docstring).
    Returns (words, bounds): bounds[i] True when word i ends a daṇḍa."""
    # edition page markers ("P--O.93:J.196" in the smaller Sukhāvatīvyūha)
    # must go BEFORE hyphen deletion or they fuse into pseudo-words
    seg = re.sub(r"\bP--[A-Za-z][A-Za-z.:\d]*", " ", seg)
    seg = seg.replace("-", "")  # join compound halves & broken lines
    words: list[str] = []
    bounds: list[bool] = []
    for tok in seg.split():
        core = tok.strip(EDGE_STRIP)
        core = re.sub(r"\d+", "", core)      # editorial footnote digits
        core = re.sub(r"[.;/()?*\[\]_\u00fc\u00b0\u00a7:@]", "", core)
        if not LETTER_RE.search(core):
            if ("|" in tok or "/" in tok) and words:
                bounds[-1] = True  # daṇḍa after previous word
            continue
        # a lone consonant letter can't be a pada (residual apparatus/page
        # marker like "P39" -> "P"); lone vowels are kept
        if len(core) == 1 and core.lower() not in "aāiīuūṛṝḷḹeo":
            continue
        words.append(core)
        bounds.append(False)
    return words, bounds


def split_long(words, bounds):
    """Split >MAX_WORDS units at daṇḍa sentence ends (fallback: hard cut)."""
    if not words:
        return []
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
        for j in range(end - 1, max(i, end - 15) - 1, -1):
            if bounds[j]:
                cut = j + 1
                break
        chunks.append(words[i:cut])
        i = cut
    return [c for c in chunks if c]


def paras(src: str) -> list[str]:
    """<p>-paragraph texts of a corpustei html transformation body."""
    s = open(src, encoding="utf-8", errors="replace").read()
    body = s[s.find("<h2>Text</h2>"):]
    # drop edition page-marker spans (they wrap sigilla only); other spans
    # (e.g. Diamond "ksaṃ" mid-word bold) keep their inner text
    body = re.sub(r'<span class="bold">\s*(?:Vajr,\s*)?Vaidya\s*\d+\s*</span>',
                  " ", body)
    out = []
    for p in re.findall(r"<p(?:\s[^>]*)?>(.*?)</p>", body, re.S):
        txt = html.unescape(re.sub(r"<br\s*/?>", "\n", p))
        txt = re.sub(r"<[^>]+>", " ", txt)
        if txt.strip():
            out.append(txt)
    return out


def words_of(seg: str) -> tuple[list[str], list[bool]]:
    return tokenize(seg)


# --- extraction --------------------------------------------------------------

BC_REF = re.compile(r"Bc_(\d+)\.(\d+)\s*//")


def carita_units() -> list[tuple[str, list[str]]]:
    """Buddhacarita cantos 1-14, ref C.V from inline 'Bc_C.V //' marks."""
    ensure(CARITA_SRC, CARITA_URL)
    units = []
    for p in paras(CARITA_SRC):
        m = BC_REF.search(p)
        if not m:
            continue  # "CANTO n" headers, colophons without refs
        txt = BC_REF.sub(" ", p)
        words, _ = words_of(txt)
        if not words:
            continue
        units.append((f"{m.group(1)}.{m.group(2)}", words))
    print(f"[buddhist] buddhacarita: {len(units)} tagged verses")
    return units


LAL_PARIVARTA = re.compile(r"START Parivarta (\d+)", re.I)
LAL_VERSE = re.compile(r"Lal_(\d+)\.(\d+)\s*//")


def lalitav_units() -> list[tuple[str, list[str]]]:
    """Lalitavistara, ref Parivarta.Seq (Seq counts source paragraphs within
    the parivarta; edition's internal Lal_P.V verse marks are folded into
    the sequence). Paragraphs before START Parivarta 1 (title block + the
    oṃ namo daśadiga… homage) are kept as front matter with refs 0.N."""
    ensure(LALITAV_SRC, LALITAV_URL)
    order: list[str] = []
    cur: dict[str, list[str]] = {}
    cur_par = 0
    seq = 0
    front_seq = 0
    for p in paras(LALITAV_SRC):
        pm = LAL_PARIVARTA.search(p)
        if pm:
            cur_par = int(pm.group(1))
            seq = 0
            continue
        words, _ = words_of(p)
        if not words:
            continue
        if cur_par:
            seq += 1
            ref = f"{cur_par}.{seq}"
        else:
            front_seq += 1
            ref = f"0.{front_seq}"
        if ref not in cur:
            cur[ref] = []
            order.append(ref)
        cur[ref].extend(words)
    out = [(ref, cur[ref]) for ref in order]
    n_par = len({int(r.split(".")[0]) for r in order if not r.startswith("0.")})
    n_front = len([r for r in order if r.startswith("0.")])
    print(f"[buddhist] lalitavistara: {len(out)} paragraph groups "
          f"({n_front} front-matter) across {n_par} parivartas")
    return out


def sequential_units(src: str, url: str,
                     label: str) -> list[tuple[str, list[str]]]:
    """Works whose editions give no internal refs: one sequential integer
    per ≤60-word daṇḍa chunk."""
    ensure(src, url)
    units = []
    for p in paras(src):
        words, bounds = words_of(p)
        if not words:
            continue  # page-marker / title-only paragraphs
        for chunk in split_long(words, bounds):
            units.append((str(len(units) + 1), chunk))
    print(f"[buddhist] {label}: {len(units)} sequential units")
    return units


def sukh_big_units() -> list[tuple[str, list[str]]]:
    return sequential_units(SUKH_BIG_SRC, SUKH_BIG_URL,
                            "sukhavativyuha (larger)")


def sukh_small_units() -> list[tuple[str, list[str]]]:
    return sequential_units(SUKH_SMALL_SRC, SUKH_SMALL_URL,
                            "sukhavativyuha (smaller)")


def heart_units() -> list[tuple[str, list[str]]]:
    return sequential_units(HEART_SRC, HEART_URL, "heart sutra")


def diamond_units() -> list[tuple[str, list[str]]]:
    return sequential_units(DIAMOND_SRC, DIAMOND_URL, "diamond sutra")


# --- packaging ---------------------------------------------------------------

LETTERS = "bcdefghijklmnopqrstuvwxyz"


def suffix_refs(units: list[dict]) -> None:
    """Split continuations get b/c/d… so deep-links stay unique."""
    seen_seq: dict[str, int] = {}
    for u in units:
        base = u["ref"]
        n = seen_seq.get(base, 0)
        if n:
            u["ref"] = (f"{base}{LETTERS[n - 1]}" if n <= len(LETTERS)
                        else f"{base}z{n}")
        seen_seq[base] = n + 1


def build_work(work_id: str, title: str, author: str,
               raw: list[tuple[str, list[str]]]) -> dict:
    units: list[dict] = []
    for ref, words in raw:
        for chunk in split_long(words, [False] * len(words)):
            units.append({"ref": ref,
                          "words": [transliterate(w, IAST, DEVA)
                                    for w in chunk]})
    suffix_refs(units)
    return {"id": work_id, "author": author, "title": title,
            "kind": "prose",  # verse+prose mixed -> prose (per corpus contract)
            "alignment": "surface-form", "units": units}


def unit_bytes(u: dict) -> int:
    return len(json.dumps(u, ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8"))


def write_parts(work: dict) -> list[str]:
    """≤MAX_PART_BYTES parts, never mixing works; returns relative paths."""
    for f in os.listdir(OUT_DIR):
        if f.startswith(work["id"] + "-part"):
            os.remove(os.path.join(OUT_DIR, f))
    rel_files = []
    part: list[dict] = []
    size = 200  # JSON envelope overhead headroom
    n = 0

    def flush():
        nonlocal part, size, n
        if not part:
            return
        n += 1
        name = f"{work['id']}-part{n:02d}.json"
        doc = dict(work, units=part)
        path = os.path.join(OUT_DIR, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"))
        actual = os.path.getsize(path)
        assert actual <= MAX_PART_BYTES, f"{name} {actual} > cap"
        rel_files.append(f"texts/buddhist/{name}")
        print(f"[buddhist] {name}: {len(part)} units, {actual / 1e6:.2f} MB")
        part, size = [], 200

    for u in work["units"]:
        ub = unit_bytes(u)
        if part and size + ub > MAX_PART_BYTES:
            flush()
        part.append(u)
        size += ub + 1
    flush()
    return rel_files


# --- verification helpers ----------------------------------------------------

AVAGRAHA_RE = re.compile("['\u2019\u02bc]")


def joined_iast(u: dict) -> str:
    """Lowercase IAST of a unit, avagraha marks removed (namo 'mitābhāya ->
    namo mitābhāya) so stem-substring checks are stable across round-trips."""
    return AVAGRAHA_RE.sub("", " ".join(
        transliterate(w, DEVA, IAST) for w in u["words"])).lower()


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(FRAG_DIR, exist_ok=True)
    failures: list[str] = []

    works_spec = [
        ("buddhacarita", "Buddhacarita", "Aśvaghoṣa", carita_units(),
         "E.H. Johnston 1935 (DSBC input via GRETIL)",
         "asvaghosa"),
        ("lalitavistara", "Lalitavistara", "Anonymous (trad.)",
         lalitav_units(), "P.L. Vaidya 1958, Mithila Institute", "anonymous"),
        ("sukhavativyuha", "Sukhāvatīvyūha (larger)", "Anonymous (trad.)",
         sukh_big_units(), "Yoshimichi Fujita input via GRETIL", "anonymous"),
        ("sukhavativyuha-smaller", "Sukhāvatīvyūha (smaller)",
         "Anonymous (trad.)", sukh_small_units(),
         "Yoshimichi Fujita input via GRETIL", "anonymous"),
        ("heart-sutra", "Prajñāpāramitāhṛdaya (Heart Sūtra)",
         "Anonymous (trad.)", heart_units(), "GRETIL e-text (n.n.)",
         "anonymous"),
        ("diamond-sutra", "Vajracchedikā Prajñāpāramitā (Diamond Sūtra)",
         "Anonymous (trad.)", diamond_units(),
         "P.L. Vaidya 1961, Mahāyānasūtrasaṃgraha I, Mithila Institute",
         "anonymous"),
    ]

    built = {}
    catalog_by_author: dict[str, list] = {}
    totals = {}
    for work_id, title, author, raw, edition, author_key in works_spec:
        w = build_work(work_id, title, author, raw)
        files = write_parts(w)
        n_tok = sum(len(u["words"]) for u in w["units"])
        totals[work_id] = (len(w["units"]), n_tok, len(files))
        built[work_id] = w
        catalog_by_author.setdefault(author_key, []).append({
            "id": work_id,
            "title": title,
            "urn": f"urn:sanskrit:{work_id}",
            "kind": w["kind"],
            "license": LICENSE,
            "files": files,
            "translation": None,
            "unitCount": len(w["units"]),
            "edition": edition,
        })

    # --- verification --------------------------------------------------------
    # 1. Buddhacarita structure: cantos 1..14 present
    bc_cantos = sorted({int(u["ref"].split(".")[0])
                        for u in built["buddhacarita"]["units"]})
    if bc_cantos != list(range(1, 15)):
        failures.append(f"buddhacarita cantos {bc_cantos} != 1..14")

    # 2. Buddhacarita 1.1 arya-vrtta pattern: this recension's opening āryā
    #    is "aikṣvāka ikṣvāku-samaprabhāvaḥ … śuddhodano nāma babhūva rājā"
    #    (the e-text itself lacks whitespace after -prabhāvaḥ; kept verbatim).
    bc11 = next((u for u in built["buddhacarita"]["units"]
                 if u["ref"] == "1.1"), None)
    ok_bc = False
    if bc11:
        j = joined_iast(bc11)
        ok_bc = ("aikṣvāka" in j and "śuddhodano" in j
                 and "babhūva rājā" in j and "viśuddha" in j)
        print("[buddhist] bc 1.1:", " ".join(bc11["words"][:10]))
    else:
        failures.append("buddhacarita ref 1.1 missing")
    if bc11 and not ok_bc:
        failures.append("buddhacarita 1.1 lacks aryā opening tokens "
                        "(aikṣvāka…śuddhodano…babhūva rājā)")

    # 3. Sukhāvatīvyūhas: Amitābha/Amitāyus + Sukhāvatī semantics (avagraha-
    #    stripped stems, since the texts salute "namo 'mitābhāya" etc.)
    big1 = next((u for u in built["sukhavativyuha"]["units"]
                 if u["ref"] == "1"), None)
    if big1:
        j = joined_iast(big1)
        if not ("mitābhāya" in j or "mitāyu" in j or "amita" in j) \
                or "sukhāvatī" not in j:
            failures.append("larger sukhāvatīvyūha opening lacks "
                            "Amitābha/Sukhāvatī semantics")
        else:
            print("[buddhist] sukh big 1.1:", " ".join(big1["words"][:8]))
    else:
        failures.append("larger sukhāvatīvyūha ref 1 missing")
    small_all = AVAGRAHA_RE.sub("", " ".join(
        " ".join(transliterate(w, DEVA, IAST) for w in u["words"])
        for u in built["sukhavativyuha-smaller"]["units"])).lower()
    if "evaṃ mayā śrutaṃ" not in small_all or "sukhāvatī" not in small_all:
        failures.append("smaller sukhāvatīvyūha lacks evaṃ mayā śrutaṃ/"
                        "sukhāvatī")
    if "mitāyur" not in small_all and "mitābha" not in small_all \
            and "mitāyu" not in small_all:
        failures.append("smaller sukhāvatīvyūha lacks Amitābha/Amitāyus")

    # 4. Lalitavistara: parivartas 1..27 (front matter = refs 0.N); the work
    #    opens "oṃ namo daśadiganantāparyantalokadhātu-…-buddhebhyo".
    lv_units = built["lalitavistara"]["units"]
    lv_parivartas = sorted({int(u["ref"].split(".")[0])
                            for u in lv_units if not u["ref"].startswith("0.")})
    if lv_parivartas != list(range(1, 28)):
        failures.append(f"lalitavistara parivartas {lv_parivartas} != 1..27")
    lv_open = " ".join(joined_iast(u) for u in lv_units)
    if "sarvabuddhabodhisattvāryaśrāvakapratyekabuddhebhyo" not in lv_open \
            or "namo" not in lv_open:
        failures.append("lalitavistara lacks namo sarvabuddha-bodhisattvārya"
                        "śrāvakapratyekabuddhebhyo opening")
    if lv_units[0]["ref"] != "0.1":
        failures.append(f"lalitavistara first unit ref {lv_units[0]['ref']} "
                        "!= 0.1 (front matter dropped?)")

    # 5. Heart/Diamond signature phrases
    heart_all = " ".join(joined_iast(u)
                         for u in built["heart-sutra"]["units"])
    if "gate gate pāragate pārasaṃgate bodhi svāhā" not in \
            re.sub(r"\s+", " ", heart_all):
        failures.append("heart sutra lacks gate gate mantra")
    if "śūnyatā" not in heart_all:
        failures.append("heart sutra lacks śūnyatā")
    dia_all = " ".join(joined_iast(u)
                       for u in built["diamond-sutra"]["units"])
    if "evaṃ mayā śrutam" not in dia_all or "vajracchedikā" not in dia_all:
        failures.append("diamond sutra lacks evaṃ mayā śrutam/vajracchedikā")

    # 6. token hygiene: no ascii residue, no empty tokens anywhere
    bad_tok = 0
    for w in built.values():
        for u in w["units"]:
            for tok in u["words"]:
                if not tok or any(ord(c) < 0x0900 or ord(c) > 0x097F
                                  for c in tok):
                    bad_tok += 1
    if bad_tok:
        failures.append(f"{bad_tok} non-Devanagari/empty tokens leaked")

    # JSON validity re-read
    for f in sorted(os.listdir(OUT_DIR)):
        with open(os.path.join(OUT_DIR, f), encoding="utf-8") as fh:
            json.load(fh)

    frag = {"authors": [
        {"name": "Aśvaghoṣa", "key": "asvaghosa",
         "works": catalog_by_author["asvaghosa"]},
        {"name": "Anonymous", "key": "anonymous",
         "works": catalog_by_author["anonymous"]},
    ]}
    tmp = os.path.join(FRAG_DIR, "buddhist.json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(frag, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(FRAG_DIR, "buddhist.json"))

    for ln in failures:
        print(f"[buddhist] FAILURE: {ln}")
    for work_id in ("buddhacarita", "lalitavistara", "sukhavativyuha",
                    "sukhavativyuha-smaller", "heart-sutra", "diamond-sutra"):
        nu, ntok, nparts = totals[work_id]
        print(f"[buddhist] {work_id:24s} {nu:6d} units {ntok:7d} tokens "
              f"{nparts} part(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
