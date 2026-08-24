#!/usr/bin/env python3
"""Build Sanskrit morphology shards from the Samsaadhanii Bhagavadgītā
e-reader analysis data (GPL v2, Univ. of Hyderabad — build-time use in this
open-source project). Emits public/data/morph/{a-z}.json keyed by
slp1_key(sandhied Devanagari surface form) -> [{l, p, f}].

POS mapping (coarse, reader-facing):
  अव्य            -> indecl
  पुं/स्त्री/नपुं   -> noun (with case/number/gender in f when present)
  verb endings    -> verb (tense/mood/person in f)
  anything else   -> part (participle/other)

Shard keys are SLP1 lowercase via pipeline.sanscript.slp1_key.

Coverage tiers (audit fix):
  1. exact key from DCS analysis rows (sandhied_word AND word AND
     morph_in_context head; ";"/","-separated variants each get their own
     sanitized key) — the FULL analysis key set, not a subset;
  2. unresolved BhG token -> stem trimmed by 1-2 final chars matching an
     existing shard key; analyses cloned under the token's own key with an
     "(inferred)" suffix in f so the UI can badge them;
  3. still unresolved -> longest prefix (>=3 chars) attested as a Monier-
     Williams headword (.cache-dcs/mw.txt <k1>), synthesized entry marked
     p:"stem", f:"(inferred)";
  4. index-only last resort: longest proper shard-key prefix >= 4 chars.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "pipeline"))
from sanscript import slp1_key, transliterate, SLP1, DEVA  # noqa: E402

SRC = os.path.join(HERE, ".cache-corpus", "analysis.json")
MW = os.path.join(HERE, ".cache-dcs", "mw.txt")
OUT_DIR = os.path.join(HERE, "public", "data", "morph")

VALID_KEY = re.compile(r"[a-z~]+")


def parse_analysis(morph: str):
    """'भूयः{अव्य}/भूयस्{नपुं}{1;एक}' -> list of (lemma_deva, pos, f)

    Paths carry ANY number of {...} tag groups (the old single-group regex
    silently dropped every noun/verb row); split on braces instead.
    """
    out = []
    for path in morph.split("/"):
        path = path.strip()
        if not path or "{" in path and "}" not in path:
            continue
        pieces = re.split(r"[{}]", path)
        form = pieces[0].strip()
        tags = [t.strip() for t in pieces[1:] if t.strip()]
        if not form:
            continue
        if not tags:
            out.append((form, "", ""))
            continue
        pos_raw = tags[0]
        rest = tags[1:]
        if pos_raw == "अव्य":
            pos, f = "indecl", ";".join(rest)
        elif pos_raw in ("पुं", "स्त्री", "नपुं"):
            pos, f = "noun", ";".join([pos_raw] + rest)
        elif any(k in pos_raw for k in ("प्रथम", "मध्यम", "उत्तम")):
            pos, f = "verb", ";".join([pos_raw] + rest)
        else:
            pos, f = "part", ";".join(tags)
        out.append((form, pos, f))
    return out


def form_keys(form: str):
    """Sanitized slp1 shard keys for one surface-form field.

    ';' (and ',') separate variant spellings inside a field in the DCS dump;
    each variant becomes its own key so no key ever contains ';'.
    Wrapping punctuation is stripped; hyphenated compounds contribute each
    member as its own key as well.
    """
    keys = []
    for variant in re.split(r"[;,]", form or ""):
        variant = variant.strip().strip("()\u00ab\u00bb\"'“”")
        candidates = [variant]
        if "-" in variant:
            candidates.extend(variant.split("-"))
        for cand in candidates:
            cand = cand.strip()
            if cand and VALID_KEY.fullmatch(slp1_key(cand) or ""):
                k = slp1_key(cand)
                if k not in keys:
                    keys.append(k)
    return keys


def row_keys(row):
    """Every attested surface key for one analysis row (tier-1 sources)."""
    keys = []
    for field in ("sandhied_word", "word"):
        keys.extend(form_keys(row.get(field) or ""))
    mic = re.match(r"\s*([^{}]+?)\s*\{", row.get("morph_in_context") or "")
    if mic:
        keys.extend(form_keys(mic.group(1)))
    return list(dict.fromkeys(keys))


def load_bhg_tokens():
    """Unique BhG surface tokens (Devanagari): reader units + e-reader text."""
    slokas = json.load(open(os.path.join(HERE, ".cache-corpus", "sloka.json"),
                            encoding="utf-8"))
    tokens = set()
    for row in slokas:
        for part in ((row.get("spart1") or "") + " " +
                     (row.get("spart2") or "")).split():
            tok = part.strip("\u0964\u09651\u0965.,;:!?\u201c\u201d()-")
            if tok:
                tokens.add(tok)
    bhg = json.load(open(os.path.join(OUT_DIR, "..", "texts", "tlg9000",
                                      "bhagavadgita-part01.json"),
                         encoding="utf-8"))
    for u in bhg["units"]:
        tokens.update(u["words"])
    occurrences = [w for u in bhg["units"] for w in u["words"]]
    return tokens, occurrences


def load_mw_keys():
    """SLP1 headword keys attested in the Cologne MW dump (<k1> fields)."""
    keys = set()
    for line in open(MW, encoding="utf-8"):
        if line.startswith("<L>"):
            m = re.search(r"<k1>([^<]*)", line)
            if m:
                k = m.group(1).strip().lower()
                if VALID_KEY.fullmatch(k):
                    keys.add(k)
    return keys


def mark_inferred(entry):
    e = dict(entry)
    e["f"] = (e["f"] + ";" if e.get("f") else "") + "(inferred)"
    return e


def add_fallback_tier(shards, mw_keys):
    """Tiers 2+3: clone/synthesize parses for unresolved BhG token keys."""
    tokens, _ = load_bhg_tokens()

    def bucket_for(key):
        return shards.setdefault(key[0] if VALID_KEY.fullmatch(key[0]) else "x",
                                 {})

    def has(key):
        b = shards.get(key[:1])
        return b is not None and key in b

    injected = trimmed = mwstem = 0
    for tok in sorted(tokens):
        k = slp1_key(tok)
        if not VALID_KEY.fullmatch(k) or has(k):
            continue
        stem = None
        # tier 2: drop 1-2 final chars -> existing shard stem
        for cut in (1, 2):
            cand = k[:-cut]
            if len(cand) >= 3 and has(cand):
                stem, entries, tier = cand, bucket_for(cand)[cand], "trim"
                break
        # tier 3: MW-attested stem (longest prefix >= 3)
        if stem is None:
            for cut in range(len(k) - 1, 2, -1):
                cand = k[:cut]
                if cand in mw_keys:
                    stem, tier = cand, "mw"
                    break
            if stem:
                entries = [{"l": transliterate(stem, SLP1, DEVA),
                            "p": "stem", "f": ""}]
        if stem is None:
            continue
        clones = [mark_inferred(e) for e in entries]
        slot = bucket_for(k)
        if k not in slot:
            injected += 1
        slot[k] = clones
        if tier == "trim":
            trimmed += 1
        else:
            mwstem += 1
    return injected, trimmed, mwstem


def emit_surface_index():
    """Map BhG surface tokens (Devanagari) to shard keys.

    Lookup order per token:
      1. exact slp1 key present in morph shards (covers fallback-tier keys,
         which carry "(inferred)" markers inside the entries themselves)
      2. longest proper-prefix of the key present in shards (>=4 chars),
         i.e. stem-match last resort
    """
    tokens, _ = load_bhg_tokens()
    morph_keys = set()
    for f in os.listdir(OUT_DIR):
        if f.endswith(".json") and not f.startswith("_"):
            morph_keys |= set(json.load(open(os.path.join(OUT_DIR, f),
                                             encoding="utf-8")))
    index: dict[str, str] = {}
    exact = stems = 0
    for tok in sorted(tokens):
        k = slp1_key(tok)
        if not VALID_KEY.fullmatch(k or ""):
            continue
        if k in morph_keys:
            index[tok] = k
            exact += 1
            continue
        # stem-trim fallback (longest prefix >= 4)
        for cut in range(len(k) - 1, 3, -1):
            if k[:cut] in morph_keys:
                index[tok] = k[:cut]
                stems += 1
                break
    with open(os.path.join(OUT_DIR, "_surface_index.json"), "w",
              encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"[morph] surface index: {len(index)} tokens "
          f"(exact={exact}, stem-fallback={stems})")


def coverage_report(shard_keys_pre, occurrences, post_keys):
    """Occurrence-weighted resolution over reader display tokens."""
    n = len(occurrences)
    if not n:
        return

    def valid(w):
        return w and VALID_KEY.fullmatch(slp1_key(w) or "")

    raw = sum(1 for w in occurrences
              if valid(w) and slp1_key(w) in shard_keys_pre)

    def resolved_final(w):
        if not valid(w):
            return False
        k = slp1_key(w)
        if k in post_keys:
            return True
        return any(k[:cut] in post_keys for cut in range(len(k) - 1, 3, -1))

    final = sum(1 for w in occurrences if resolved_final(w))
    print(f"[coverage] raw exact {raw}/{n} = {100 * raw / n:.1f}% | "
          f"with fallback {final}/{n} = {100 * final / n:.1f}%")


def main() -> None:
    rows = json.load(open(SRC, encoding="utf-8"))
    shards: dict[str, dict[str, list]] = {}
    n_analyzed = 0
    for row in rows:
        analyses = parse_analysis(row.get("morph_analysis") or "")
        if not analyses:
            continue
        keys = row_keys(row)
        if not keys:
            continue  # e-reader meta rows ("0", "-", "(0)")
        n_analyzed += 1
        for key in keys:
            bucket = shards.setdefault(key[0], {})
            slot = bucket.setdefault(key, [])
            for lemma_deva, pos, f in analyses:
                entry = {
                    "l": transliterate(lemma_deva, DEVA, DEVA),  # deva display
                    "p": pos,
                    "f": f,
                }
                if entry not in slot:
                    slot.append(entry)

    pre_keys = set()
    for bucket in shards.values():
        pre_keys |= set(bucket)
    n_pre = len(pre_keys)

    tokens, occurrences = load_bhg_tokens()
    mw_keys = load_mw_keys()
    injected, trimmed, mwstem = add_fallback_tier(shards, mw_keys)

    post_keys = set()
    for bucket in shards.values():
        post_keys |= set(bucket)

    os.makedirs(OUT_DIR, exist_ok=True)
    stale = [f for f in os.listdir(OUT_DIR)
             if f.endswith(".json") and not f.startswith("_")]
    for f in stale:
        os.remove(os.path.join(OUT_DIR, f))
    total = 0
    for letter, bucket in sorted(shards.items()):
        if not re.fullmatch(r"[a-z]", letter):
            continue
        with open(os.path.join(OUT_DIR, f"{letter}.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(bucket, fh, ensure_ascii=False, separators=(",", ":"))
        total += len(bucket)
    print(f"[morph] {total} keyed forms "
          f"(analysis={n_pre}, +fallback-injected={injected} "
          f"[trim={trimmed}, mw-stem={mwstem}]), "
          f"{n_analyzed} analyzed rows consumed")
    semi = sum(1 for k in post_keys if ";" in k)
    if semi:
        print(f"[morph] WARNING: {semi} keys still contain ';'")
    coverage_report(pre_keys, occurrences, post_keys)
    emit_surface_index()


if __name__ == "__main__":
    main()
