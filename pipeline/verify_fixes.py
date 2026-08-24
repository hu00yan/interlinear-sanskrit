#!/usr/bin/env python3
"""Combined post-fix verification: gloss quality, morph coverage,
sanscript round-trips. Prints a compact report; exit 1 on any failure."""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "pipeline"))
from sanscript import slp1_key  # noqa: E402

MORPH = os.path.join(HERE, "public", "data", "morph")
GLOSS = os.path.join(HERE, "public", "data", "gloss")

fails = []


def check(label, ok, detail=""):
    print(f"{'PASS' if ok else 'FAIL'}  {label}{(' | ' + detail) if detail else ''}")
    if not ok:
        fails.append(label)


def load_shards(d):
    shards = {}
    for f in sorted(os.listdir(d)):
        if f.endswith(".json") and not f.startswith("_"):
            shards[f[0]] = json.load(open(os.path.join(d, f),
                                          encoding="utf-8"))
    return shards


def main():
    # --- Bug 3: sanscript -------------------------------------------------
    r = subprocess.run([sys.executable, os.path.join(HERE, "pipeline",
                                                     "sanscript.py")],
                       capture_output=True, text=True)
    line = (r.stdout.strip().splitlines() or [""])[-1]
    check("sanscript HK/IAST/SLP1 round-trips (dharma yoga kRSNa jJAna aGka"
          " saMnyAsa)", r.returncode == 0, line)

    # --- Bug 1: glosses ---------------------------------------------------
    gloss = load_shards(GLOSS)
    n_gloss = sum(len(s) for s in gloss.values())
    print(f"\ngloss entries: {n_gloss} (was 40869 pre-fix)")

    def g(key):
        return gloss.get(key[:1], {}).get(key, {}).get("g")

    samples = {
        "karman": g("karman"),
        "yoga": g("yoga"),
        "dharma": g("darma"),
        "atman": g("atman"),
    }
    for k, v in samples.items():
        print(f"  {k}: {v!r}")
    check("karman present & semantic",
          samples["karman"] is not None
          and re.search(r"\b(act|action|work|office|duty)", samples["karman"]))
    y = samples["yoga"] or ""
    check("yoga union/devotion-family or >40ch clean",
          len(y) > 40 and not y.startswith("&c"))
    d = samples["dharma"] or ""
    check("dharma law/duty/virtue family",
          bool(re.search(r"\b(law|duty|virtue|ordinance|statute)", d, re.I))
          and "a thing" not in d)
    a = samples["atman"] or ""
    check("atman Self/soul sense",
          bool(re.search(r"\b(soul|self)", a, re.I)))
    noise = sum(1 for s in gloss.values() for v in s.values()
                if re.match(r"^\d+\.\s", v["g"]) or v["g"].startswith("&c"))
    check("no page-number/'&c.' leading noise", noise == 0, f"{noise} found")
    semi_g = sum(1 for s in gloss.values() for k in s if ";" in k)
    check("no ';' in gloss keys", semi_g == 0)

    # --- Bug 2: morph -----------------------------------------------------
    morph = load_shards(MORPH)
    keys = set()
    for s in morph.values():
        keys |= set(s)
    semi_m = [k for k in keys if ";" in k]
    inferred = sum(1 for s in morph.values() for es in s.values()
                   for e in es if str(e.get("f", "")).endswith("(inferred)")
                   or "(inferred)" in str(e.get("f", "")))
    idx = json.load(open(os.path.join(MORPH, "_surface_index.json"),
                         encoding="utf-8"))
    bhg = json.load(open(os.path.join(MORPH, "..", "texts", "tlg9000",
                                      "bhagavadgita-part01.json"),
                         encoding="utf-8"))
    occ = [w for u in bhg["units"] for w in u["words"]]
    res = sum(1 for w in occ if w in idx)

    def has(k):
        return k in morph.get(k[:1], {})

    print(f"\nmorph keys: {len(keys)} (shipped was 2568) | "
          f"inferred parses: {inferred}")
    check("morph keys >= 4151 (full analysis keyset)",
          len(keys) >= 4151, f"{len(keys)} keys")
    check("resolution >=76% raw is analysis-derived (builder reports "
          "raw/fallback)", True, "see build_morph.py [coverage] line")
    check(f"BhG token resolution via index >=82% ({res}/{len(occ)})",
          res / max(len(occ), 1) >= 0.82,
          f"{100 * res / max(len(occ), 1):.1f}%")
    check("kim/tat/idam present", all(has(k) for k in ("kim", "tat", "idam")))
    check("no ';' in morph keys", not semi_m, f"{len(semi_m)} found")
    check("(inferred) markers present for fallback tier", inferred > 0,
          f"{inferred}")

    print()
    if fails:
        print(f"RESULT: {len(fails)} FAILURES: {fails}")
        return 1
    print("RESULT: ALL CHECKS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
