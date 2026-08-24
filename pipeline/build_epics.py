#!/usr/bin/env python3
"""Build the two great epics from GRETIL UTF-8 IAST e-texts.

Sources (.cache-corpus/, fetched on demand via curl --retry):
  epics-ram/sa_rAmAyaNa.htm   Vālmīki-Rāmāyaṇa, Tokunaga input, Smith rev.
                              (corpustei analytic transformation, all 7 kāṇḍas;
                              verse blocks <p id="R_K.SSS.VVV"> + span.ref)
  epics-mbh/mbh_NN_u.htm      Mahābhārata NN=01..18 parvans (BORI/Tokunaga/
                              Smith; lines "PP,AAA.VVV[pada][*ins]\ttext")

Unit schema mirrors build_bhg_text.py: {"id","author","title","kind",
"alignment","units":[{"ref","words"}]} with Devanagari display tokens via
sanscript.transliterate(IAST->DEVA). Epics mix verse and prose -> kind is
"prose". Refs are chapter-level per source markup: "<kāṇḍa>.<sarga>" /
"<parvan>.<adhyāya>"; each chapter's text is tokenized and cut into ≤60-word
prose chunks at daṇḍa boundaries (build_upanishads.py tokenize/split_long),
continuations getting letter suffixes ("1.1b", "1.1c", ...).

Output: public/data/texts/epics/<work>-partNN.json, each part ≤8MB.
Catalog: fragment public/data/catalog-fragments/epics.json ONLY — a
collector merges fragments into catalog.json later (avoids merge races).
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "pipeline"))
from sanscript import transliterate, IAST, DEVA  # noqa: E402

CACHE_RAM = os.path.join(HERE, ".cache-corpus", "epics-ram")
CACHE_MBH = os.path.join(HERE, ".cache-corpus", "epics-mbh")
OUT_DIR = os.path.join(HERE, "public", "data", "texts", "epics")
FRAG_DIR = os.path.join(HERE, "public", "data", "catalog-fragments")

GRETEL = "https://gretil.sub.uni-goettingen.de/gretil"
RAM_SRC = os.path.join(CACHE_RAM, "sa_rAmAyaNa.htm")
RAM_URL = GRETEL + "/corpustei/transformations/html/sa_rAmAyaNa.htm"
MBH_SRCS = [os.path.join(CACHE_MBH, f"mbh_{nn:02d}_u.htm") for nn in range(1, 19)]
MBH_URL = GRETEL + "/1_sanskr/2_epic/mbh/mbh_{:02d}_u.htm"

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


# --- tokenization (conventions shared with build_upanishads.py) --------------

LETTER_RE = re.compile(r"[A-Za-z\u0100-\u017f\u1e00-\u1eff]")
# edge punctuation stripped from tokens; apostrophes NOT included because
# GRETIL marks avagraha with them and sanscript maps ' -> ऽ (Devanagari).
EDGE_STRIP = "|‖/\\()[]{}.,;:?!*<>«»“”„–—-_"


def tokenize(seg: str):
    """Whitespace tokens minus punctuation/digits and GRETIL critical-
    apparatus markers (( ) [ ] ? * _ ü mark variants/lacunae/doubtful
    akṣaras -> deleted; , - separate readings -> treated as space).
    Returns (words, bounds): bounds[i] True when word i ends a daṇḍa."""
    seg = re.sub(r"[,\u2013\u2014-]", " ", seg)
    words: list[str] = []
    bounds: list[bool] = []
    for tok in seg.split():
        core = tok.strip(EDGE_STRIP)
        core = re.sub(r"\d+", "", core)      # editorial footnote digits
        core = re.sub(r"[.;/()?*\[\]_\u00fc\u00b0\u00a7]", "", core)
        if not LETTER_RE.search(core):
            if ("|" in tok or "/" in tok) and words:
                bounds[-1] = True  # daṇḍa after previous word
            continue
        # a lone consonant letter can't be a pada (residual apparatus mark);
        # lone vowels are kept ("u", "ā" interjections)
        if len(core) == 1 and core.lower() not in "aāiīuūṛṝḷḹeo":
            continue
        words.append(core)
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
        for j in range(end - 1, max(i, end - 15) - 1, -1):
            if bounds[j]:
                cut = j + 1
                break
        chunks.append(words[i:cut])
        i = cut
    return [c for c in chunks if c]


# --- extraction --------------------------------------------------------------

RAM_P = re.compile(
    r'<p id="R_(\d+)\.(\d+)\.(\d+)">(.*?)</p>', re.S)


def ram_chapters() -> list[tuple[str, list[str]]]:
    """All 7 kāṇḍas from the single-file transformation. Refs K.Sarga."""
    ensure(RAM_SRC, RAM_URL)
    s = open(RAM_SRC, encoding="utf-8", errors="replace").read()
    body = s[s.find("<h2>Text</h2>"):]  # drop header/licence preamble
    order: list[str] = []
    cur: dict[str, list[str]] = {}
    for m in RAM_P.finditer(body):
        k, srg = int(m.group(1)), int(m.group(2))
        blk = re.sub(r'<span class="ref">[^<]*</span>', ' ', m.group(4))
        txt = re.sub(r"<[^>]+>", " ", blk)
        words, bounds = tokenize(txt)
        if not words:
            continue
        ref = f"{k}.{srg}"
        if ref not in cur:
            cur[ref] = []
            order.append(ref)
        cur[ref].extend(words)
    out = []
    for ref in order:
        out.append((ref, cur[ref]))
    return out


MBH_LINE = re.compile(
    r"^(\d{1,2}),(\d{1,3})\.(\d{1,3})[A-Za-z]*(?:\*\S+)?[ \t]+(.*)$")


def mbh_chapters() -> list[tuple[str, list[str]]]:
    """All 18 parvans. Refs Parvan.Adhyāya (incl. adhyāya 0 mangala)."""
    order: list[str] = []
    cur: dict[str, list[str]] = {}
    mismatch = 0
    total_lines = 0
    for nn, src in enumerate(MBH_SRCS, start=1):
        ensure(src, MBH_URL.format(nn))
        s = open(src, encoding="utf-8", errors="replace").read()
        txt = re.sub(r"<[^>]+>", "\n", s)
        for ln in txt.splitlines():
            m = MBH_LINE.match(ln.strip())
            if not m:
                continue
            p, a = int(m.group(1)), int(m.group(2))
            if p != nn:
                mismatch += 1
                continue
            # critical-edition insert labels "(9ab)", "(12c)" -> drop
            body_txt = re.sub(r"\([^)]*\d[^)]*\)", " ", m.group(4))
            words, _ = tokenize(body_txt)
            if not words:
                continue
            total_lines += 1
            ref = f"{p}.{a}"
            if ref not in cur:
                cur[ref] = []
                order.append(ref)
            cur[ref].extend(words)
    if mismatch:
        print(f"[epics] WARN {mismatch} lines whose parvan != filename skipped")
    print(f"[epics] mbh: {total_lines} tagged half-verses across "
          f"{len(order)} adhyāyas")
    return [(ref, cur[ref]) for ref in order]


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
        rel_files.append(f"texts/epics/{name}")
        print(f"[epics] {name}: {len(part)} units, {actual / 1e6:.2f} MB")
        part, size = [], 200

    for u in work["units"]:
        ub = unit_bytes(u)
        if part and size + ub > MAX_PART_BYTES:
            flush()
        part.append(u)
        size += ub + 1
    flush()
    return rel_files


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(FRAG_DIR, exist_ok=True)
    failures: list[str] = []

    raw_ram = ram_chapters()
    raw_mbh = mbh_chapters()

    ram = build_work("ramayana", "Rāmāyaṇa", "Vālmīki (trad.)", raw_ram)
    mbh = build_work("mahabharata", "Mahābhārata", "Vyāsa (trad.)", raw_mbh)

    catalog_works = []
    totals = {}
    for work_id, w in (("ramayana", ram), ("mahabharata", mbh)):
        files = write_parts(w)
        n_tok = sum(len(u["words"]) for u in w["units"])
        totals[work_id] = (len(w["units"]), n_tok, len(files))
        catalog_works.append({
            "id": work_id,
            "title": w["title"],
            "urn": f"urn:sanskrit:{work_id}",
            "kind": w["kind"],
            "license": LICENSE,
            "files": files,
            "translation": None,
            "unitCount": len(w["units"]),
        })

    # --- verification --------------------------------------------------------
    ram_kandas = sorted({int(u["ref"].split(".")[0]) for u in ram["units"]})
    mbh_parvans = sorted({int(u["ref"].split(".")[0])
                          for u in mbh["units"]})
    if ram_kandas != list(range(1, 8)):
        failures.append(f"ram kandas {ram_kandas} != 1..7")
    if mbh_parvans != list(range(1, 19)):
        failures.append(f"mbh parvans {mbh_parvans} != 1..18")

    ram11 = next((u for u in ram["units"] if u["ref"] == "1.1"), None)
    ok_ram = False
    if ram11:
        joined = " ".join(transliterate(w, DEVA, IAST)
                          for w in ram11["words"]).lower()
        ok_ram = any(fam in joined for fam in
                     ("tapas", "tapaḥ", "tapasvī", "tapasv"))
    else:
        failures.append("ram ref 1.1 missing")
    if ram11 and not ok_ram:
        failures.append("ram 1.1 lacks tapas/tapasvā family")

    # base + letter-suffixed continuations of adhyāya 1 (exclude e.g. 1.11)
    mbh11_group = [u for u in mbh["units"]
                   if re.fullmatch(r"1\.1[b-z]*", u["ref"])]
    ok_mbh = False
    if mbh11_group:
        for u in mbh11_group:
            joined = " ".join(transliterate(w, DEVA, IAST)
                              for w in u["words"]).lower()
            if "āry" in joined:
                ok_mbh = True
                print(f"[epics] mbh āry- family found in ref {u['ref']}")
                break
        print("[epics] mbh 1.1 opens:",
              " ".join(mbh11_group[0]["words"][:8]))
    else:
        failures.append("mbh ref 1.1 missing")

    # JSON validity re-read
    for f in os.listdir(OUT_DIR):
        with open(os.path.join(OUT_DIR, f), encoding="utf-8") as fh:
            json.load(fh)

    frag = {"author": "Vālmīki / Vyāsa", "works": catalog_works}
    tmp = os.path.join(FRAG_DIR, "epics.json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(frag, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(FRAG_DIR, "epics.json"))

    for ln in failures:
        print(f"[epics] FAILURE: {ln}")
    print(f"[epics] ramayana   {totals['ramayana'][0]:6d} units "
          f"{totals['ramayana'][1]:8d} tokens {totals['ramayana'][2]} part(s) "
          f"kandas={ram_kandas} tapas1.1={'OK' if ok_ram else 'FAIL'}")
    print(f"[epics] mahabharat {totals['mahabharata'][0]:6d} units "
          f"{totals['mahabharata'][1]:8d} tokens "
          f"{totals['mahabharata'][2]} part(s) "
          f"parvans={len(mbh_parvans)} ary1.1={'OK' if ok_mbh else 'WARN'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
