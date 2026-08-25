#!/usr/bin/env python3
"""Ensure catalog.json's "Pali Canon" group carries up-to-date entries for
the six Vinaya books built by build_pali_vinaya.py. Idempotent; updates
unitCount in place when the entry exists.
Usage: update_catalog_vinaya.py <pj|pc|mv|cv|pvr|bi>
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAT = os.path.join(HERE, "public", "data", "catalog.json")

META = {
    "pj": dict(title="Pārājika", titleZh="波罗夷"),
    "pc": dict(title="Pācittiya", titleZh="波逸提"),
    "mv": dict(title="Mahāvagga", titleZh="大品"),
    "cv": dict(title="Cūḷavagga", titleZh="小品"),
    "pvr": dict(title="Parivāra", titleZh="附随"),
    "bi": dict(title="Bhikkhunīvibhaṅga", titleZh="比丘尼分别"),
}


def main() -> None:
    bk = sys.argv[1]
    stem = f"vinaya-{bk}"
    tpath = os.path.join(HERE, "public", "data", "texts", "pali",
                         f"{stem}.json")
    units = len(json.load(open(tpath, encoding="utf-8"))["units"])
    cat = json.load(open(CAT, encoding="utf-8"))
    grp = next(a for a in cat["authors"] if a.get("name") == "Pali Canon")
    wid = f"pali-{stem}"
    m = META[bk]
    entry = next((w for w in grp["works"] if w["id"] == wid), None)
    if entry is None:
        entry = {"id": wid, "title": m["title"], "titleZh": m["titleZh"],
                 "urn": f"urn:pali:{wid}", "lang": "pi", "kind": "prose",
                 "license": "CC0"}
        grp["works"].append(entry)
    entry.update({
        "files": [f"texts/pali/{stem}.json"],
        "unitCount": units,
        "translation": {"translator": "Bhikkhu Brahmali", "year": 2020,
                        "license": "CC0",
                        "files": [f"trans/pali-{stem}-brahmali.json"]},
    })
    # keep the repo's compact single-line catalog format byte-style
    with open(CAT, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(cat, ensure_ascii=False))
    print(f"[catalog] {wid}: unitCount={units}")


if __name__ == "__main__":
    main()
