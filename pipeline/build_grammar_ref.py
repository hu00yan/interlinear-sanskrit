#!/usr/bin/env python3
"""Build public/data/grammar/arnold.json from the cached Wikisource scrape.

PROVENANCE NOTE (verified against .cache-corpus/arnold_*.json on 2026-08-24):
the cached "arnold_*" files are NOT a Sanskrit grammar. They hold Wikisource's
copy of *The Bhagavad Gita* ("The Song Celestial", 1885), the English verse
translation by Sir Edwin Arnold — page id 8603, redirect "The Song Celestial".
There are no printed § sections and no sandhi/declension morphology anywhere
in the source. This builder therefore emits that content faithfully under its
true bibliographic identity (type: "translation") rather than fabricating a
grammar. Re-scrape an actual grammar source if grammar sections are needed.

Usage: python3 pipeline/build_grammar_ref.py
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from html import unescape
from pathlib import Path

from bs4 import BeautifulSoup, Tag

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache-corpus"
OUT = ROOT / "public" / "data" / "grammar" / "arnold.json"

NOEXPORT_CLASSES = {"ws-noexport", "noprint", "ws-summary", "mw-editsection",
                    "printfooter", "navbox", "mw-jump-link"}
PD_FALLBACK = (
    "This work was published before January 1, 1931, and is in the public "
    "domain worldwide because the author died at least 100 years ago "
    "(Wikisource Template:PD-old; Sir Edwin Arnold d. 1904)."
)


def load_cache() -> tuple[dict, dict]:
    main = json.loads((CACHE / "arnold_main.json").read_text(encoding="utf-8"))["parse"]
    chapters = json.loads((CACHE / "arnold_chapters.json").read_text(encoding="utf-8"))
    return main, chapters


BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr",
              "table", "ul", "ol", "blockquote", "dd", "dt", "center", "pre"}


def strip_ws_markup(html: str) -> str:
    """Drop styles/scripts and Wikisource chrome; return remaining text.

    Newlines are inserted only after block-level tags so inline markup
    (<i>Sanjaya</i>. etc.) stays glued to its verse line.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["style", "script"]):
        tag.decompose()
    doomed = []
    for tag in soup.find_all(True):
        attrs = getattr(tag, "attrs", None) or {}
        if NOEXPORT_CLASSES & set(attrs.get("class") or []):
            doomed.append(tag)
    for tag in doomed:
        tag.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    markers = []
    for tag in soup.find_all(True):
        if tag.name in BLOCK_TAGS:
            markers.append(tag)
    for tag in markers:
        tag.append("\n")
    return soup.get_text()


def normalize_text(raw: str) -> str:
    """Normalize entities/whitespace; keep printed verse lines, drop nothing."""
    text = unicodedata.normalize("NFC", raw)
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[   ]+", " ", line)  # nbsp & friends -> space
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    # collapse accidental duplicates of blank-line separators
    return "\n".join(lines)


def chapter_title(html: str, number: int) -> str:
    m = re.search(
        r'Chapter\s+\d+\s*\(\s*["\u201c]([^"\u201d]+?)\s*["\u201d]\s*\)',
        unescape(html),
    )
    if m:
        return m.group(1).strip()
    soup = BeautifulSoup(html, "html.parser")
    head = soup.find(class_="mw-headline")
    if head:
        return head.get_text(" ", strip=True)
    return f"Chapter {number}"


def scrape_metadata(main: dict) -> dict:
    """Bibliographic identity + license evidence taken from the scrape itself."""
    page_html = main["text"]["*"]
    title = main["title"]

    soup = BeautifulSoup(page_html, "html.parser")
    year_node = soup.select_one(".wst-header-year-text")
    year = int(year_node.get_text(strip=True)) if year_node else None

    author = translator = None
    for contrib in soup.select(".contributor-text"):
        label = contrib.get_text(" ", strip=True)
        fn = contrib.select_one(".fn")
        name = fn.get_text(strip=True) if fn else None
        if not name:
            continue
        if "translated by" in label:
            translator = name
        elif label.startswith("by") and author is None:
            author = name

    m = re.search(r"public domain worldwide because[^.<]*\.", page_html)
    pd_sentence = unescape(m.group(0)).strip() if m else PD_FALLBACK
    license_evidence = (
        pd_sentence
        + " Evidence in scraped page: Template:PD-old license block; "
        + "Wikisource header 'The Bhagavad Gita (1885) by Vyasa, translated by "
        + "Edwin Arnold'; author Sir Edwin Arnold died 1904."
    )

    return {
        "book": title,
        "alt_title": "The Song Celestial",
        "author": author,
        "translator": translator,
        "year": year,
        "wikisource_page_id": main.get("pageid"),
        "license": license_evidence,
    }


def build() -> dict:
    main, chapters_raw = load_cache()
    meta = scrape_metadata(main)

    chapters = []
    for key in sorted(chapters_raw, key=int):
        number = int(key)
        html = chapters_raw[key]
        body = normalize_text(strip_ws_markup(html))
        if not body:
            raise SystemExit(f"chapter {number}: empty after cleaning — aborting")
        chapters.append({
            "id": f"ch{number:02d}",
            "number": number,
            "title": chapter_title(html, number),
            "sections": [{
                "id": str(number),
                "title": chapter_title(html, number),
                "text": body,
            }],
        })

    return {
        **meta,
        "type": "translation",
        "warning": (
            "NOT a Sanskrit grammar. The cached arnold_* scrape contains only "
            "Edwin Arnold's English translation of the Bhagavad Gita; it has "
            "no § sections and no sandhi/declension content. Section ids are "
            "the printed chapter numbers. Replace with a real grammar scrape "
            "(e.g. Monier-Williams or 'A Sanskrit Manual') for grammar use."
        ),
        "source": {
            "site": "English Wikisource",
            "url": "https://en.wikisource.org/wiki/The_Bhagavad_Gita_(Arnold_translation)",
            "cache_files": ["arnold_main.json", "arnold_chapters.json",
                            "arnold_index.html"],
            "built_by": "pipeline/build_grammar_ref.py",
        },
        "chapters": chapters,
    }


def verify(ref: dict) -> None:
    payload = json.dumps(ref, ensure_ascii=False)
    json.loads(payload)  # round-trip: must be valid JSON
    size = len(payload.encode("utf-8"))
    n_ch = len(ref["chapters"])
    n_sec = sum(len(c["sections"]) for c in ref["chapters"])
    empty = [c["id"] for c in ref["chapters"]
             if not c["sections"][0]["text"].strip()]
    if empty:
        raise SystemExit(f"empty sections: {empty}")
    print(f"OK: valid JSON, {n_ch} chapters, {n_sec} sections, {size} bytes "
          f"(<8MB: {size < 8_000_000})")


def main() -> int:
    ref = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(ref, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    verify(json.loads(OUT.read_text(encoding="utf-8")))
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
