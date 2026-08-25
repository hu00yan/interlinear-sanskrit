#!/usr/bin/env python3
"""Extend public/data/morph shards with DCS v2 CoNLL-U analyses.

Round 1: 11 works, ~1.59M tokens, .cache-dcs/dcs-conllu/<Work>/*.conllu.
Round 2 (this): +22 matched works (~1.9M more tokens) from a sibling cache
.cache-dcs-ext/<Work>/*.conllu (outside the repo; .cache-dcs/ is read-only;
location overridable via DCS_EXTRA_SRC env var — see NEW_WORKS below and
qa-report/morph-dcs2.md for the match table + exclusions). GPL-style DCS
data — build-time use. MERGES INTO the existing BhG-built shards
(pipeline/build_morph.py output) without disturbing their entries: shared
keys keep existing parses FIRST, deduped DCS parses appended; new keys are
added wholesale. Idempotent: rerun against its own output is a no-op.

Shard contract (unchanged — see src/api.ts loadMorph):
  public/data/morph/{a-z}.json     slp1_key(surface form) -> [{l,p,f}]
  public/data/morph/_surface_index.json  display token -> shard key

Key derivation: slp1_key() of the sandhied CoNLL-U FORM plus the MISC
Unsandhied variant (and hyphen-separated members of either) — same tiering
as build_morph.form_keys. Keys must match [a-z~]+.

Tag normalization onto the EXISTING reader-facing vocabulary
(build_morph.py conventions; Samsaadhanii-style Devanagari tags):
  UPOS -> p: NOUN/ADJ/NUM->noun | VERB/AUX Fin->verb, Part/Gdv/Inf->part,
          Conv->indecl | PRON/DET->part (BhG precedent: pronouns landed in
          "part") | ADV/PART/CONJ/SCONJ/ADP/INTJ->indecl | else->part
  feats -> f: Case->1..7/sambodhana digit style, Gender->puM/strI/napuM,
          Number->eka/dvi/bahu, Person->uttama/madhyama/prathama,
          Tense*Mood->lAra (laT/laG/lft/liT/luG/lfG/lot/vidhilfG),
          Voice->parasmaipada/atmanepada; unmapped extras kept VERBATIM
          (bare value, e.g. Cpd, Gdv) rather than dropped.

Also rebuilds _surface_index.json corpus-wide: every Sanskrit catalog work's
display tokens (exact shard-key hit, else longest resolving prefix >=4 —
same stem-fallback rule as build_morph.emit_surface_index).

Surface slices (frontend lazy lookup, src/api.ts surfaceKey/loadMorph) —
SAME token->key shape as the monolith, split two ways:
  _surface/<letter>.json         corpus-wide bucket per Devanagari initial
                                 (SLICE_NAME below); universal fallback +
                                 scope-less callers (lexicon box)
  _surface/by-work/<id>.json     one catalog work's tokens; the small
                                 primary slice fetched by the reader
TODO(next release): stop writing _surface_index.json (kept one release as
rollback/fallback cache) and delete it from public/data/morph/.

Validation: per-work occurrence-weighted resolution % over the site's own
text tokens (simulating loadMorph exactly) + a spot-check dump.

Run:  python3 pipeline/build_morph_dcs.py
"""
import glob
import json
import os
import re
import sys
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "pipeline"))
from sanscript import slp1_key, transliterate, IAST, DEVA  # noqa: E402

SRC_DIR = os.path.join(HERE, ".cache-dcs", "dcs-conllu")
# Round-2 cache: sibling of the repo root (kept out of the repo tree because
# .cache-dcs/ is read-only by convention). Override with DCS_EXTRA_SRC.
EXTRA_SRC = os.environ.get(
    "DCS_EXTRA_SRC",
    os.path.join(os.path.dirname(HERE), ".cache-dcs-ext"))
MORPH_DIR = os.path.join(HERE, "public", "data", "morph")
CATALOG = os.path.join(HERE, "public", "data", "catalog.json")

# Catalog<->DCS matches added in round 2 (values = DCS work dir names under
# EXTRA_SRC). Every entry passed the validation gate: page-sample resolution
# >=85% of site tokens resolving through the merged shards AND a material
# resolution gain over round-1 spill-over (else recension mismatch ->
# excluded; see qa-report/morph-dcs2.md for the excluded list + reasons).
NEW_WORKS = [
    # Upaniṣads
    "Kaṭhopaniṣad", "Muṇḍakopaniṣad", "Aitareyopaniṣad",
    "Taittirīyopaniṣad", "Bṛhadāraṇyakopaniṣad", "Chāndogyopaniṣad",
    "Śvetāśvataropaniṣad", "Kauṣītakyupaniṣad",
    # Kāvya / fable / stotra
    "Ṛtusaṃhāra", "Kumārasaṃbhava", "Caurapañcaśikā", "Gītagovinda",
    "Śatakatraya",
    # Purāṇa
    "Bhāgavatapurāṇa",
    # Darśana
    "Sāṃkhyakārikā", "Yogasūtra", "Nyāyasūtra",
    # Buddhist sūtras
    "Saddharmapuṇḍarīkasūtra", "Aṣṭasāhasrikā", "Laṅkāvatārasūtra",
    # Veda
    "Ṛgveda",
]

VALID_KEY = re.compile(r"[a-z~]+")
PUNCT_RE = re.compile(r"^[\u0964\u09650-9.,;:!?\u201c\u201d'\"()\-\s]+$")

# --- UD -> existing-tag vocabulary ------------------------------------------
CASE = {"Nom": "1", "Acc": "2", "Ins": "3", "Dat": "4", "Abl": "5",
        "Gen": "6", "Loc": "7", "Voc": "\u0938\u092e\u094d\u092c\u094b\u0927\u0928"}
GENDER = {"Masc": "\u092a\u0941\u0902", "Fem": "\u0938\u094d\u0930\u0940",
          "Neut": "\u0928\u092a\u0941\u0902"}
NUMBER = {"Sing": "\u090f\u0915", "Dual": "\u0926\u094d\u0935\u093f",
          "Plur": "\u092c\u0939\u0941"}
PERSON = {"1": "\u0909\u0924\u094d\u0924\u092e",
          "2": "\u092e\u0927\u094d\u092f\u092e",
          "3": "\u092a\u094d\u0930\u0925\u092e"}
VOICE = {"Act": "\u092a\u0930\u0938\u094d\u092e\u0948\u092a\u0926",
         "Mid": "\u0906\u0924\u094d\u092e\u0928\u0947\u092a\u0926",
         "Pass": "\u0906\u0924\u094d\u092e\u0928\u0947\u092a\u0926"}
LAKARA = {  # (Tense, Mood) -> lAra
    ("Pres", "Ind"): "\u0932\u091f\u094d",
    ("Impf", "Ind"): "\u0932\u0919\u094d",
    ("Fut", "Ind"): "\u0932\u0943\u091f\u094d",
    ("Fut", ""): "\u0932\u0943\u091f\u094d",
    ("Cond", ""): "\u0932\u0943\u0919\u094d",
    ("Perf", ""): "\u0932\u093f\u091f\u094d",
    ("Aor", ""): "\u0932\u0941\u0919\u094d",
    ("Imp", "Imp"): "\u0932\u094b\u091f\u094d",
    ("Pres", "Subj"): "\u0935\u093f\u0927\u093f\u0932\u093f\u0919\u094d",
    ("Pres", "Opt"): "\u0935\u093f\u0927\u093f\u0932\u093f\u0919\u094d",
    ("", "Subj"): "\u0935\u093f\u0927\u093f\u0932\u093f\u0919\u094d",
    ("", "Opt"): "\u0935\u093f\u0927\u093f\u0932\u093f\u0919\u094d",
}
INDECL_UPOS = {"ADV", "PART", "CONJ", "SCONJ", "ADP", "INTJ"}


def map_pos(upos: str, feats: dict) -> str:
    vf = feats.get("VerbForm", "")
    if upos in ("NOUN", "ADJ", "NUM"):
        return "noun"
    if upos in ("VERB", "AUX"):
        # UD omits VerbForm on finite verbs (default = Fin)
        return "verb" if vf in ("Fin", "") else (
            "indecl" if vf == "Conv" else "part")
    if upos in ("PRON", "DET"):
        return "part"
    if upos in INDECL_UPOS:
        return "indecl"
    return "part"


def _is_finite(upos: str, feats: dict) -> bool:
    return upos in ("VERB", "AUX") and \
        feats.get("VerbForm", "") in ("Fin", "")


def map_feats(upos: str, feats: dict) -> str:
    """UD feats -> ';'-joined Samsaadhanii-style tags, extras verbatim."""
    tags = []
    if _is_finite(upos, feats):
        lak = LAKARA.get((feats.get("Tense", ""), feats.get("Mood", "")))
        if lak:
            tags.append(lak)
        if "Person" in feats:
            tags.append(PERSON.get(feats["Person"], feats["Person"]))
        if "Number" in feats:
            tags.append(NUMBER.get(feats["Number"], feats["Number"]))
        if "Voice" in feats:
            tags.append(VOICE.get(feats["Voice"], feats["Voice"]))
        extras = [v for k, v in feats.items()
                  if k not in ("VerbForm", "Tense", "Mood", "Person",
                               "Number", "Voice")]
    elif upos in ("VERB", "AUX") and feats.get("VerbForm") == "Part":
        # participle: lAra/pada context then nominal inflection
        if "Tense" in feats:
            lak = LAKARA.get((feats["Tense"], feats.get("Mood", ""))) \
                or LAKARA.get((feats["Tense"], ""))
            if lak:
                tags.append(lak)
        if "Voice" in feats:
            tags.append(VOICE.get(feats["Voice"], feats["Voice"]))
        if "Gender" in feats:
            tags.append(GENDER.get(feats["Gender"], feats["Gender"]))
        if "Case" in feats:
            tags.append(CASE.get(feats["Case"], feats["Case"]))
        if "Number" in feats:
            tags.append(NUMBER.get(feats["Number"], feats["Number"]))
        extras = [v for k, v in feats.items()
                  if k not in ("VerbForm", "Tense", "Mood", "Voice",
                               "Gender", "Case", "Number")]
    else:
        # nominal / indeclinable: gender;case-digit;number (build_morph order)
        if "Gender" in feats:
            tags.append(GENDER.get(feats["Gender"], feats["Gender"]))
        if "Case" in feats:
            tags.append(CASE.get(feats["Case"], feats["Case"]))
        if "Number" in feats:
            tags.append(NUMBER.get(feats["Number"], feats["Number"]))
        extras = [v for k, v in feats.items()
                  if k not in ("Gender", "Case", "Number")]
    return ";".join(tags + [e for e in extras if e])


def _canonical_keys(text: str):
    """All valid shard-key spellings for one surface form.

    slp1_key() takes different normalization paths for Devanagari vs roman
    input: Devanagari वै -> 've' (ai->E->e after casefold) but ASCII 'vai'
    stays 'vai' (HK path leaves the digraph), likewise au->o vs 'au'. DCS
    source forms are roman while most site display tokens are Devanagari,
    so every ai/au word would otherwise split into two non-meeting key
    flavors. Derive BOTH flavors (raw + via the other script) so shards
    carry aliases and either lookup flavor resolves. Same-word aliases
    only; no new collisions are introduced.
    """
    out = []

    def add(k):
        if k and VALID_KEY.fullmatch(k) and k not in out:
            out.append(k)

    add(slp1_key(text))
    try:
        if any("\u0900" <= c <= "\u097f" for c in text):
            add(slp1_key(transliterate(text, DEVA, IAST)))
        else:
            add(slp1_key(transliterate(text, IAST, DEVA)))
    except Exception:
        pass
    return out


def form_keys(form: str):
    """slp1 shard keys for one surface-form field (sandhied + variants).

    Hyphenated compounds contribute each member too; invalid keys skipped.
    """
    keys = []
    for cand in [form] + (form.split("-") if "-" in form else []):
        cand = cand.strip()
        if not cand:
            continue
        for k in _canonical_keys(cand):
            if k not in keys:
                keys.append(k)
    return keys


def parse_feats(field: str) -> dict:
    out = {}
    if field and field != "_":
        for kv in field.split("|"):
            kv = kv.strip()
            if "=" in kv:
                k, v = kv.split("=", 1)
                if k and v:
                    out[k] = v
            elif kv and kv != "_":
                out[kv] = ""  # keyless feat: keep verbatim
    return out


def conllu_analyses(path: str):
    """Yield (form_keys, entry_dict) per real token line."""
    for line in open(path, encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        c = line.rstrip("\n").split("\t")
        if len(c) < 6 or "-" in c[0] or "." in c[0]:
            continue  # range row (sandhi pre-split) / empty-node row
        form, lemma, upos, feats_f, misc = c[1], c[2], c[3], c[5], c[9] \
            if len(c) > 9 else ""
        if upos in ("PUNCT", "SYM"):
            continue
        feats = parse_feats(feats_f)
        pos = map_pos(upos, feats)
        f = map_feats(upos, feats)
        unsand = ""
        m = re.search(r"(?:^|\|)Unsandhied=([^|]*)", misc or "")
        if m:
            unsand = m.group(1)
        keys = form_keys(form)
        for k in form_keys(unsand):
            if k not in keys:
                keys.append(k)
        if not keys or not lemma or lemma == "_":
            # still yield keys with a bare entry so the surface index can
            # resolve the form even without a usable lemma
            if not keys:
                continue
            yield keys, None
            continue
        dev = transliterate(lemma, IAST, DEVA)
        yield keys, {"l": dev, "p": pos, "f": f}


def load_existing():
    shards = {}
    for fp in sorted(glob.glob(os.path.join(MORPH_DIR, "[a-z].json"))):
        letter = os.path.basename(fp)[0]
        shards[letter] = json.load(open(fp, encoding="utf-8"),
                                   object_pairs_hook=OrderedDict)
    n = sum(len(b) for b in shards.values())
    print(f"[dcs-morph] existing shards: {n} keys "
          f"across {len(shards)} letters")
    return shards


def merge(shards):
    """Union DCS analyses into shards.

    Returns (n_new_keys, per_work_stats, key_origin) where per_work_stats
    maps work-dir -> [tokens_seen, keys_added] and key_origin maps each
    newly-created shard key -> the work dir that first contributed it
    (used for per-work spot checks).
    """
    roots = [(SRC_DIR, "*")]
    for w in NEW_WORKS:
        if not os.path.isdir(os.path.join(EXTRA_SRC, w)):
            raise SystemExit(
                f"[dcs-morph] missing round-2 cache dir: "
                f"{os.path.join(EXTRA_SRC, w)} (run the downloader; "
                f"or set DCS_EXTRA_SRC)")
        roots.append((EXTRA_SRC, w))
    files = []
    for root, pat in roots:
        files += sorted(glob.glob(os.path.join(root, pat, "*.conllu")))
    assert len(files) > 2500, f"dcs-conllu missing? found {len(files)}"
    seen_pairs = set()  # (key, entry-tuple) already in shards OR added by us
    for bucket in shards.values():
        for k, entries in bucket.items():
            for e in entries:
                seen_pairs.add((k, e.get("l"), e.get("p"), e.get("f")))
    n_new_keys = n_dup = n_tok = 0
    per_work = {}
    key_origin = {}
    r1_dirs = {os.path.basename(d)
               for d in glob.glob(os.path.join(SRC_DIR, "*"))}
    for fp in files:
        work = os.path.basename(os.path.dirname(fp))
        st = per_work.setdefault(work, [0, 0])
        for keys, entry in conllu_analyses(fp):
            n_tok += 1
            st[0] += 1
            if entry is None:
                continue
            etup = (entry["l"], entry["p"], entry["f"])
            fresh = False
            for k in keys:
                bucket = shards.setdefault(k[0], OrderedDict())
                slot = bucket.get(k)
                if slot is None:
                    bucket[k] = [entry]
                    n_new_keys += 1
                    st[1] += 1
                    key_origin.setdefault(k, work)
                    fresh = True
                elif (k,) + etup not in seen_pairs:
                    slot.append(entry)
                    fresh = True
                seen_pairs.add((k,) + etup)
            if not fresh:
                n_dup += 1
    print(f"[dcs-morph] tokens={n_tok} new_keys={n_new_keys} "
          f"dup_entries_skipped={n_dup}")
    for work in sorted(per_work):
        if work not in r1_dirs:
            toks, added = per_work[work]
            print(f"  [r2] {work}  tokens={toks} new_keys={added}")
    return n_new_keys, per_work, key_origin


def emit_shards(shards):
    total = 0
    for letter, bucket in sorted(shards.items()):
        if not re.fullmatch(r"[a-z]", letter):
            continue
        with open(os.path.join(MORPH_DIR, f"{letter}.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(bucket, fh, ensure_ascii=False, separators=(",", ":"))
        total += len(bucket)
    mb = sum(os.path.getsize(p) for p in
             glob.glob(os.path.join(MORPH_DIR, "[a-z].json"))) / 2**20
    print(f"[dcs-morph] emitted {total} keys, {mb:.1f} MB total")


# --- corpus-wide surface index ----------------------------------------------

def sa_work_files():
    cat = json.load(open(CATALOG, encoding="utf-8"))
    for a in cat["authors"]:
        if a.get("lang", "sa") == "pi":
            continue
        for w in a["works"]:
            if w.get("lang", a.get("lang", "sa")) == "pi":
                continue  # Pali works skip the Devanagari morph pipeline
            for rel in w["files"]:
                yield w["id"], os.path.join(MORPH_DIR, "..", rel)


def collect_tokens():
    toks_by_work = {}
    for wid, fp in sa_work_files():
        part = json.load(open(fp, encoding="utf-8"))
        s = set(toks_by_work.setdefault(wid, set()))
        for u in part["units"]:
            s.update(u["words"])
        toks_by_work[wid] = s
    return toks_by_work


def emit_surface_index(shards):
    keys = set()
    for bucket in shards.values():
        keys |= set(bucket)
    toks_by_work = collect_tokens()
    all_toks = set()
    for s in toks_by_work.values():
        all_toks |= s
    index = {}
    exact = stems = 0
    for tok in sorted(all_toks):
        if PUNCT_RE.match(tok):
            continue
        variants = _canonical_keys(tok)
        members = None
        hit_key = None
        for k in variants:
            if k in keys:
                hit_key = k
                break
        if hit_key is None and "-" in tok:
            # hyphenated display token: first member with a resolving key
            got = []
            for mem in tok.split("-"):
                mk = _canonical_keys(mem.strip())
                got.extend(k for k in mk if k in keys)
            if got:
                hit_key = got[0]
        if hit_key is not None:
            index[tok] = hit_key
            exact += 1
            continue
        # stem fallback: longest resolving prefix >=4, primary flavor first
        for k in variants:
            for cut in range(len(k) - 1, 3, -1):
                if k[:cut] in keys:
                    index[tok] = k[:cut]
                    stems += 1
                    break
            if tok in index:
                break
    with open(os.path.join(MORPH_DIR, "_surface_index.json"), "w",
              encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, separators=(",", ":"))
    mb = os.path.getsize(os.path.join(
        MORPH_DIR, "_surface_index.json")) / 2**20
    print(f"[surface-index] {len(index)} tokens (exact={exact}, "
          f"stem={stems}) {mb:.1f} MB")
    return toks_by_work, index


# --- surface slices ----------------------------------------------------------
# Client-side mirror of this table lives in src/api.ts (DEV_SLICE) — keep the
# two EXACTLY in sync. Bucketing rule on both sides: scan the display token
# left-to-right and use the FIRST character that maps. Tokens with no mapped
# char are Latin/digit-initial; the frontend only consults slices for
# Devanagari forms (/[\u0900-\u097f]/), so they are unreachable here anyway.
SLICE_NAME = {
    "\u0905": "a", "\u0906": "aa", "\u0907": "i", "\u0908": "ii",
    "\u0909": "u", "\u090a": "uu", "\u090b": "r", "\u0960": "r",
    "\u090c": "l", "\u0961": "l",
    "\u090f": "e", "\u0910": "ai", "\u0913": "o", "\u0914": "au",
    "\u0950": "om",  # om-initial tokens
    "\u093d": "z",   # avagraha-initial tokens (elision marks)
    # consonants (nukta precomposites fold into their base letter bucket)
    "\u0915": "k", "\u0958": "k",
    "\u0916": "kh", "\u0959": "kh",
    "\u0917": "g", "\u095a": "g",
    "\u0918": "gh",
    "\u0919": "ng",
    "\u091a": "ch",
    "\u091b": "chh",
    "\u091c": "j", "\u095b": "j",
    "\u091d": "jh",
    "\u091e": "ny",
    "\u091f": "t", "\u0924": "t",
    "\u0920": "th", "\u0925": "th",
    "\u0921": "d", "\u0926": "d", "\u095c": "d",
    "\u0922": "dh", "\u0927": "dh", "\u095d": "dh",
    "\u0923": "n", "\u0928": "n",
    "\u092a": "p",
    "\u092b": "ph", "\u095e": "ph",
    "\u092c": "b",
    "\u092d": "bh",
    "\u092e": "m",
    "\u092f": "y", "\u095f": "y",
    "\u0930": "r",
    "\u0932": "l", "\u0933": "l",
    "\u0935": "v",
    "\u0936": "sh",
    "\u0937": "shh",
    "\u0938": "s",
    "\u0939": "h",
}


def initial_slice(tok):
    """Slice name for a display token: first mapped char, else None."""
    for ch in tok:
        name = SLICE_NAME.get(ch)
        if name:
            return name
    return None


def _write_json(path: str, obj) -> int:
    blob = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(blob)
    return len(blob.encode("utf-8"))


def emit_surface_slices(index, toks_by_work):
    """Split the surface index into lazy per-letter + per-work slices."""
    letters = {}
    skipped = 0
    for tok, key in index.items():
        name = initial_slice(tok)
        if name is None:
            skipped += 1
            continue
        letters.setdefault(name, {})[tok] = key

    by_work = {}
    for wid, toks in toks_by_work.items():
        sub = {t: index[t] for t in toks if t in index}
        if sub:
            by_work[wid] = sub

    outdir = os.path.join(MORPH_DIR, "_surface")
    workdir = os.path.join(outdir, "by-work")
    os.makedirs(workdir, exist_ok=True)

    expected = set()
    total_bytes = 0
    for name, bucket in sorted(letters.items()):
        total_bytes += _write_json(os.path.join(outdir, f"{name}.json"), bucket)
        expected.add(os.path.join(outdir, f"{name}.json"))
    for wid, bucket in sorted(by_work.items()):
        fp = os.path.join(workdir, f"{wid}.json")
        total_bytes += _write_json(fp, bucket)
        expected.add(fp)

    # prune stale slices (renamed works / dropped buckets from older runs)
    removed = 0
    for fp in glob.glob(os.path.join(outdir, "**", "*.json"), recursive=True):
        if fp not in expected:
            os.remove(fp)
            removed += 1

    print(f"[surface-slices] {len(letters)} letter files "
          f"({sum(len(b) for b in letters.values())} keys), "
          f"{len(by_work)} per-work files "
          f"({sum(len(b) for b in by_work.values())} keys), "
          f"{total_bytes / 2**20:.1f} MB raw, "
          f"{skipped} tokens skipped (non-Devanagari initial), "
          f"{removed} stale pruned")


# --- validation --------------------------------------------------------------

WORK_OF_SITE_ID = {
    "buddhacarita": "Buddhacarita", "mahabharata": "Mah\u0101bh\u0101rata",
    "ramayana": "R\u0101m\u0101ya\u1e47a", "kiratarjuniya":
        "Kir\u0101t\u0101rjun\u012bya", "meghaduta": "Meghad\u016bta",
    "arthasastra": "Artha\u015b\u0101stra", "manusmrti": "Manusm\u1e5bti",
    "kamasutra": "K\u0101mas\u016btra", "hitopadesa": "Hitopade\u015ba",
    "tantrakhyayika": "Tantr\u0101khy\u0101yik\u0101",
    # round-2 matches
    "katha-upanishad": "Ka\u1e6dhopani\u1e63ad",
    "mundakopanishad": "Mu\u1e47\u1e0dakopani\u1e63ad",
    "aitareya-upanishad": "Aitareyopani\u1e63ad",
    "taittiriya-upanishad": "Taittir\u012byopani\u1e63ad",
    "brihadaranyaka-upanishad": "B\u1e5bhad\u0101ra\u1e47yakopani\u1e63ad",
    "chandogya-upanishad": "Ch\u0101ndogyopani\u1e63ad",
    "svetasvatara-upanishad": "\u015avet\u0101\u015bvataropani\u1e63ad",
    "kausitaki-upanishad": "Kau\u1e63\u012btakyupani\u1e63ad",
    "rtusamhara": "\u1e5atusa\u1e43h\u0101ra",
    "kumarasambhava": "Kum\u0101rasa\u1e43bhava",
    "caurapancasika": "Caurapa\u00f1ca\u015bik\u0101",
    "gitagovinda": "G\u012btagovinda", "satakatraya": "\u015aatakatraya",
    "bhagavata-01": "Bh\u0101gavatapur\u0101\u1e47a",
    "sankhya-karika": "S\u0101\u1e43khyak\u0101rik\u0101",
    "yoga-sutra": "Yogas\u016btra", "nyaya-sutra": "Ny\u0101yas\u016btra",
    "saddharmapundarika": "Saddharmapu\u1e47\u1e0dar\u012bkas\u016btra",
    "astasahasrika": "A\u1e63\u1e6das\u0101hasrik\u0101",
    "lankavatara": "La\u1e45k\u0101vat\u0101ras\u016btra",
    "rigveda-mandala01": "\u1e5agveda",
}

# Round-1 (pre-round-2) occurrence-weighted resolution % — spill-over only.
# validate() prints the delta so the report can show per-work gain.
ROUND1_PCT = {
    "bhagavadgita": 95.8, "katha-upanishad": 91.1,
    "prasna-upanishad": 91.2, "mundaka-upanishad": 83.6,
    "aitareya-upanishad": 88.7, "taittiriya-upanishad": 86.4,
    "brihadaranyaka-upanishad": 87.8, "chandogya-upanishad": 87.6,
    "kenopanishad": 82.1, "svetasvatara-upanishad": 58.6,
    "kausitaki-upanishad": 50.0, "maitri-upanishad": 39.2,
    "rigveda-mandala01": 85.4, "raghuvamsa": 88.8,
    "abhijnanasakuntala": 91.9, "rtusamhara": 93.4,
    "kumarasambhava": 62.4, "sisupalavadha": 87.3,
    "caurapancasika": 91.5, "pancatantra": 93.6,
    "saddharmapundarika": 87.8, "astasahasrika": 66.9,
    "lankavatara": 58.1, "bhagavata-01": 61.4, "bhagavata-05": 68.3,
    "bhagavata-10": 73.9, "gitagovinda": 59.5, "satakatraya": 66.3,
    "vetalapancavimsati": 73.1, "sankhya-karika": 32.4,
    "yoga-sutra": 24.5, "nyaya-sutra": 23.1, "brahma-sutra": 40.2,
}


def validate(toks_by_work, index, shards):
    print("\n[dcs-morph] per-work resolution (site tokens -> index -> shard):")
    lines = []
    for wid in sorted(toks_by_work):
        toks = toks_by_work[wid]
        occ = Counter()
        for wid2, fp in sa_work_files():
            if wid2 != wid:
                continue
            part = json.load(open(fp, encoding="utf-8"))
            for u in part["units"]:
                occ.update(u["words"])
        word_occ = sum(n for t, n in occ.items() if not PUNCT_RE.match(t))
        hit = sum(n for t, n in occ.items()
                  if not PUNCT_RE.match(t) and t in index)
        pct = 100 * hit / word_occ if word_occ else 0.0
        dcs = WORK_OF_SITE_ID.get(wid, "-")
        base = ROUND1_PCT.get(wid)
        delta = f" (+{pct - base:.1f})" if base is not None and pct >= base \
            else (f" ({pct - base:+.1f})" if base is not None else "")
        lines.append(f"{wid}|{dcs}|{pct:.1f}%|{hit}/{word_occ}")
        flag = "" if pct >= 90 or base is None else "  <-- round-2 match"
        print(f"  {wid:26s} (DCS: {dcs:24s}) {pct:6.2f}%{delta:8s} "
              f"({hit}/{word_occ} word occurrences){flag}")
    return lines


def spot_check_new(index, key_origin, toks_by_work, shards, per_work=3):
    """Eye-check sample: most frequent site tokens resolving ONLY because a
    given round-2 work contributed their shard key."""
    print("\n[spot-check r2] per-new-work samples (token -> key -> entries):")
    for work in NEW_WORKS:
        keys_w = {k for k, w in key_origin.items() if w == work}
        if not keys_w:
            print(f"  {work}: no new-key hits on site tokens")
            continue
        shown = 0
        best = []
        for wid, toks in toks_by_work.items():
            for t in toks:
                k = index.get(t)
                if k in keys_w:
                    best.append(t)
        shown = 0
        for tok in sorted(set(best)):
            k = index[tok]
            entries = shards.get(k[0], {}).get(k)
            if not entries:
                continue
            print(f"  [{work}] {tok} -> {k} -> {entries[:1]}")
            shown += 1
            if shown >= per_work:
                break


def spot_check(index, shards, n=15):
    print("\n[spot-check] sample resolved analyses:")
    shown = 0
    for tok in sorted(index):
        k = index[tok]
        bucket = shards.get(k[0], {})
        entries = bucket.get(k)
        if not entries:
            continue
        print(f"  {tok} -> {k} -> {entries[:2]}")
        shown += 1
        if shown >= n:
            break


def main() -> None:
    shards = load_existing()
    before = {l: set(b) for l, b in shards.items()}
    n_new, per_work, key_origin = merge(shards)
    emit_shards(shards)
    toks_by_work, index = emit_surface_index(shards)
    emit_surface_slices(index, toks_by_work)
    lines = validate(toks_by_work, index, shards)
    with open(os.path.join(HERE, "qa-report", "morph-dcs2-resolution.csv"),
              "w", encoding="utf-8") as fh:
        fh.write("work|dcs_dir|pct|hits\n")
        fh.write("\n".join(lines) + "\n")
    spot_check(index, shards)
    spot_check_new(index, key_origin, toks_by_work, shards)

    # idempotence probe: rerunning merge must add nothing
    probe = {l: dict(b) for l, b in shards.items()}
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        merge(probe)
    out = buf.getvalue()
    m = re.search(r"new_keys=(\d+)", out)
    assert m and m.group(1) == "0", "NOT idempotent: second pass adds keys!"
    print("\n[idempotence] second-pass new_keys=0 OK")


if __name__ == "__main__":
    main()
