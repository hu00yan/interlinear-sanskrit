#!/usr/bin/env python3
"""Build the Ṛgveda (maṇḍalas 1-10) from GRETIL e-texts, with padapāṭha
alignment — the key feature of this build.

Sources (.cache-corpus/, GRETIL corpustei plain-text transformations):
  - sa_Rgveda-edAufrecht.txt      saṃhitāpāṭha (Aufrecht ed.), refs RV_M,HHH.VV
  - sa_RgvedasaMhitApadapATha.txt padapāṭha (Sansknet), refs rv_M,H.V,
    pada separated by "|", compounds marked with "-", junction/refrain
    markers with "iti", editorial insertions in "[...]".

The padapāṭha is the tradition's own word-by-word analysis (sandhi already
resolved), so its tokens become the authoritative words[] list; the
saṃhitāpāṭha line is kept verbatim in a parallel "samhita" field for
display fidelity.

Pada-token cleanup rules (TITUS/GRETIL padapāṭha encoding):
  - "[...]"            editorial insertion -> dropped          ([svar iti]svaḥ -> svaḥ)
  - "--"               reduplication marker  -> "-"           (dive--dive -> dive-dive)
  - "X iti" / "Xiti"   trailing iti marker   -> X             (vāyo iti -> vāyo;
                        indravāyūiti -> indravāyū) — except the few real
                        words ending in -iti (akṣiti, śvasiti, prāṇiti),
                        which are kept via a denylist.
  - "X itiY" / "XitiY" fused pronunciation + analyzed form: take Y when Y
    equals X under a sandhi-normalised consonant skeleton (visarga ~ s ~ r,
    voiced/unvoiced/aspirated stop classes, nasals), e.g.
    karitikaḥ -> kaḥ, svar itisvaḥ -> svaḥ, śatakrato itiśata-krato ->
    śata-krato, purandhī itipuram-dhī -> puram-dhī. Non-matching pairs are
    left untouched (safe fallback).
  - Internal compound hyphens are KEPT (puraḥ-hitam stays puraḥ-hitam):
    they mark the traditional word-junction inside a pada.

Known data quirk handled honestly: pada file labels two different lines
"rv_9,97.36" and none "rv_9,97.35" (refrain-versification drift vs.
Aufrecht). Duplicates resolve by best textual match against the saṃhitā
line; a saṃhitā verse with no pada counterpart falls back to whitespace
split and is flagged {"needsSplit": true} instead of pretending alignment.

Output:
  public/data/texts/rigveda/mandala-{01..10}.json
    {"workId","kind":"verse","meta":{"padapadha":true},"units":[
       {"ref":"M.H.V","words":[...],"kind":"verse","samhita":"...", ...}]}
  public/data/catalog-fragments/rigveda.json  (fragment only; catalog.json
    merge happens elsewhere, same convention as the other builders')
"""
import json
import os
import re
import sys
from difflib import SequenceMatcher

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(HERE, ".cache-corpus")
OUT_DIR = os.path.join(HERE, "public", "data", "texts", "rigveda")
FRAG = os.path.join(HERE, "public", "data", "catalog-fragments", "rigveda.json")

SAMHITA_SRC = os.path.join(CACHE, "sa_Rgveda-edAufrecht.txt")
PADA_SRC = os.path.join(CACHE, "sa_RgvedasaMhitApadapATha.txt")

AUTHOR_NAME = "trad. Vyāsa / ṛṣis"
LICENSE = "GRETIL attribution"

SAMHITA_REF = re.compile(r"RV_(\d+),(\d+)\.(\d+)\s*$")
# terminator "// rv_M,H.V //"; NOT anchored to EOL — a varga footer
# ("//4//.") may follow, and two verses occasionally share one line
PADA_REF = re.compile(r"//\s*rv_(\d+),(\d+)\.(\d+)\s*//")
ASTAKA_PREFIX = re.compile(r"^\s*-rv_\d+:\d+/\d+-\s*")       # -rv_7:4/18-
HYMN_PREFIX = re.compile(r"^\s*\(\s*rv_\d+,\d+\s*\)\s*")      # (rv_10,191)


def norm_ref(m, prefix):
    """Match object -> canonical 'M.H.V' string."""
    return f"{int(m.group(1))}.{int(m.group(2))}.{int(m.group(3))}"


def parse_samhita(path):
    """ref -> samhitāpāṭha line (display string, ref tag stripped)."""
    verses = {}
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            m = SAMHITA_REF.search(line)
            if not m:
                continue
            ref = norm_ref(m, "RV")
            text = line[: m.start()].rstrip()
            if not text:
                print(f"WARN samhita empty body at line {lineno}", file=sys.stderr)
                continue
            verses[ref] = text
    return verses


# real words that happen to end in "-iti" — never treat their ending as a
# junction marker (RV 1.40.4 dhatte akṣiti śravaḥ; 1.65.9; 10.125.4)
ITI_DENYLIST = {"akṣiti", "śvasiti", "prāṇiti"}

_SANDHI_FOLDS = [
    ("kh", "K"), ("gh", "G"), ("ch", "C"), ("jh", "J"),
    ("ṭh", "T"), ("ḍh", "D"), ("th", "T"), ("dh", "D"),
    ("ph", "P"), ("bh", "P"),
    ("ś", "~"), ("ṣ", "~"), ("ḥ", "~"), ("s", "~"), ("r", "~"),
    ("k", "k"), ("g", "k"), ("c", "c"), ("j", "c"),
    ("ṭ", "t"), ("ḍ", "t"), ("t", "t"), ("d", "t"),
    ("p", "p"), ("b", "p"),
    ("n", "N"), ("m", "N"), ("ṇ", "N"), ("ṃ", "N"),
    ("ñ", "N"), ("ṅ", "N"), ("h", "~"),
]


def _sandhi_key(s):
    """Consonant-skeleton key that equates sandhi alternants
    (kar/kaḥ, pranetar/pra-netaḥ, purandhī/puram-dhī,
    saṃyatī/sam-yatī, ...). Vowels are dropped."""
    s = re.sub(r"[-\s]+", "", s)
    for a, b in _SANDHI_FOLDS:
        s = s.replace(a, b)
    return "".join(ch for ch in s if ch in "kgctpKGCPTDPN~yvlh")


def _sandhi_twin(x, y):
    """True if x and y are the same word modulo sandhi: identical
    skeleton, or one a prefix of the other (doubled junction forms
    like hann/iti/han)."""
    kx, ky = _sandhi_key(x), _sandhi_key(y)
    return bool(kx and ky) and (kx == ky or kx.startswith(ky)
                                or ky.startswith(kx))


def clean_pada_token(tok):
    """Apply the TITUS/GRETIL pada-marker rules to one '|' token."""
    tok = re.sub(r"\[[^\]]*\]", "", tok)   # editorial insertions
    tok = tok.replace("--", "-")            # reduplication marker
    # find every literal 'iti' occurrence and treat it as a junction marker
    # only when the surrounding parts reconcile (see module docstring)
    while True:
        m = re.search(r"iti", tok)
        if not m:
            break
        before, after = tok[: m.start()], tok[m.end():]
        b = before.strip().rstrip("-").strip()
        a = after.strip().lstrip("-").strip()
        if b and a:
            # 'X iti Y': analytical form Y wins when it is X's sandhi twin
            if len(b) >= 2 and len(a) >= 2 and _sandhi_twin(b, a):
                tok = a
                continue
            break                          # unrelated / mid-word: leave as-is
        if not a:                          # trailing marker: X iti | Xiti
            if tok.strip().lower() in ITI_DENYLIST:
                break                      # real word ending in -iti: keep
            tok = b
            continue
        tok = a                            # leading marker (not observed)
        continue
    return tok.strip()


def parse_pada(path):
    """ref -> list of candidate pada-token lists.

    A physical line may hold several verse segments (e.g. rv_10,92.1 and
    rv_10,92.2 share one line) and the terminator may be followed by a
    varga footer ("//4//."), so each line is split at every terminator and
    the text before each terminator belongs to that terminator's ref.
    """
    candidates = {}
    for lineno, line in enumerate(open(path, encoding="utf-8"), 1):
        if "//" not in line or "rv_" not in line:
            continue
        hits = list(PADA_REF.finditer(line))
        for k, m in enumerate(hits):
            start = hits[k - 1].end() if k else 0
            ref = norm_ref(m, "rv")
            body = line[start: m.start()]
            body = ASTAKA_PREFIX.sub("", body)
            body = HYMN_PREFIX.sub("", body)
            toks = []
            for t in body.split("|"):
                t = clean_pada_token(t).strip("/").strip()  # stray '/' typos
                if t:
                    toks.append(t)
            if not toks:
                print(f"WARN pada empty body at line {lineno} ({ref})",
                      file=sys.stderr)
                continue
            candidates.setdefault(ref, []).append(toks)
    return candidates


def _flat(tokens):
    return re.sub(r"[-\s]+", "", " ".join(tokens))


def align(samhita, pada_cands):
    """Resolve pada candidates against the saṃhitā line; emit unit dicts."""
    units, fallbacks = [], []
    for ref, sam_text in samhita.items():
        cands = pada_cands.get(ref)
        unit = {"ref": ref, "kind": "verse", "samhita": sam_text}
        if not cands:
            words = [w for w in sam_text.split() if w not in ("|", "||")]
            unit["words"] = words
            unit["needsSplit"] = True
            fallbacks.append(ref)
        elif len(cands) == 1:
            unit["words"] = cands[0]
        else:
            target = _flat(re.findall(r"\S+", sam_text))
            best = max(cands, key=lambda c: SequenceMatcher(
                None, _flat(c), target).ratio())
            unit["words"] = best
            unit["padaVariant"] = True
        units.append(unit)
    return units, fallbacks


def main():
    samhita = parse_samhita(SAMHITA_SRC)
    pada = parse_pada(PADA_SRC)
    print(f"parsed saṃhitāpāṭha: {len(samhita)} verses; "
          f"padapāṭha: {sum(len(v) for v in pada.values())} lines, "
          f"{len(pada)} unique refs")

    extra = sorted(set(pada) - set(samhita))
    if extra:
        print(f"WARN pada-only refs ignored: {extra}", file=sys.stderr)

    by_mandala = {m: [] for m in range(1, 11)}
    all_fallbacks, variants = [], 0
    for m in range(1, 11):
        mandala_refs = sorted(
            (r for r in samhita if r.startswith(f"{m}.")),
            key=lambda r: tuple(int(x) for x in r.split(".")),
        )
        units, fb = align({r: samhita[r] for r in mandala_refs},
                          {r: pada[r] for r in mandala_refs if r in pada})
        for u in units:
            if not u.get("words"):
                raise AssertionError(f"empty words[] for {u['ref']}")
            if "needsSplit" not in u and not u["words"]:
                raise AssertionError(u["ref"])
        all_fallbacks += fb
        variants += sum(1 for u in units if "padaVariant" in u)
        by_mandala[m] = units

    os.makedirs(OUT_DIR, exist_ok=True)
    works = []
    total = 0
    for m in range(1, 11):
        wid = f"rigveda-mandala{m:02d}"
        path = os.path.join(OUT_DIR, f"mandala-{m:02d}.json")
        doc = {
            "workId": wid,
            "title": f"Ṛgveda Maṇḍala {m}",
            "author": AUTHOR_NAME,
            "kind": "verse",
            "alignment": "pada",
            "meta": {
                "padapadha": True,
                "source": "GRETIL: Aufrecht saṃhitāpāṭha + Sansknet padapāṭha",
                "license": LICENSE,
            },
            "units": by_mandala[m],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        works.append({
            "id": wid,
            "title": f"Ṛgveda Maṇḍala {m}",
            "urn": f"urn:sanskrit:{wid}",
            "kind": "verse",
            "license": LICENSE,
            "files": [f"texts/rigveda/mandala-{m:02d}.json"],
            "translation": None,
            "unitCount": len(by_mandala[m]),
        })
        total += len(by_mandala[m])

    frag = {"author": AUTHOR_NAME, "works": works}
    with open(FRAG, "w", encoding="utf-8") as f:
        json.dump(frag, f, ensure_ascii=False, indent=1)

    # ---- verification summary -------------------------------------------
    covered = total - len(all_fallbacks)
    print("\n=== VERIFICATION ===")
    print("mandala | verses | pada-aligned")
    for m in range(1, 11):
        n = len(by_mandala[m])
        nf = sum(1 for u in by_mandala[m] if "needsSplit" in u)
        print(f"   {m:2d}   | {n:5d}  | {n - nf:5d}")
    print(f"TOTAL    | {total:5d}  | {covered:5d} "
          f"({100 * covered / total:.2f}% pada coverage)")
    canon_lo, canon_hi = 10552, 10622
    ok_total = canon_lo <= total <= canon_hi
    m1_ok = abs(len(by_mandala[1]) - 1910) <= 120  # edition-dependent count
    print(f"total-in-canonical-range[{canon_lo}-{canon_hi}]: {ok_total}; "
          f"mandala1≈1910: {m1_ok} (got {len(by_mandala[1])})")
    r111 = next(u for u in by_mandala[1] if u["ref"] == "1.1.1")
    print(f"RV 1.1.1 pada tokens: {' '.join(r111['words'])}")
    print(f"fallbacks(needsSplit): {len(all_fallbacks)} {all_fallbacks}; "
          f"pada-duplicate resolutions: {variants}")


if __name__ == "__main__":
    main()
