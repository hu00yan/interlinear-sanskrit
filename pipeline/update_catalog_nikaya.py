#!/usr/bin/env python3
"""Ensure catalog.json's "Pali Canon" group carries up-to-date entries for
the nikāya works built by build_pali_nikaya.py. Idempotent; updates
unitCount in place when the entry exists.
Usage: update_catalog_nikaya.py <workId> <title> <titleZh> <stem> <count>
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAT = os.path.join(HERE, "public", "data", "catalog.json")


def main() -> None:
    wid, title, tzh, stem, count = sys.argv[1], sys.argv[2], sys.argv[3], \
        sys.argv[4], int(sys.argv[5])
    cat = json.load(open(CAT, encoding="utf-8"))
    grp = next(a for a in cat["authors"] if a.get("name") == "Pali Canon")
    entry = next((w for w in grp["works"] if w["id"] == wid), None)
    if entry is None:
        entry = {"id": wid, "title": title, "titleZh": tzh,
                 "urn": f"urn:pali:{wid}", "lang": "pi", "kind": "prose",
                 "license": "CC0"}
        grp["works"].append(entry)
    entry.update({
        "files": [f"texts/pali/{stem}.json"],
        "unitCount": count,
        "translation": {"translator": "Bhikkhu Sujato", "year": 2018,
                        "license": "CC0",
                        "files": [f"trans/pali-{stem}-sujato.json"]},
    })
    with open(CAT, "w", encoding="utf-8") as fh:
        json.dump(cat, fh, ensure_ascii=False, indent=1)
    print(f"[catalog] {wid}: unitCount={count}")


if __name__ == "__main__":
    main()
