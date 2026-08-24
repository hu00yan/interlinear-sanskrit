#!/usr/bin/env python3
"""Sanskrit transliteration facade + canonical shard keys (SLP1 lowercase).

CANONICAL INTERNAL KEY = SLP1 lowercase (slp1_key): the DCS dump and the
Cologne Monier-Williams dumps are SLP1-native, so morph/gloss/search shard
keys are slp1_key(token) for zero-conversion alignment. Reader display is
Devanagari primary.

Schemes (tables from indic-transliteration, MIT; build-time dep):
  DEVA  Devanagari (display)
  IAST  standard IAST
  SLP1  indic-transliteration's slp1 (DCS-native; verify vs DCS in step 2)
  HK    user-canonical Harvard-Kyoto flavor, DERIVED deterministically from
        SLP1: vocalic r/l become RRi/RRI/LRi/LRI (independent) or Ri/RI/LRi/LRI
        (matra position), retroflex s becomes Sh. E.g.:
          BagavadgItA -> bhagavadgItA-style reading key stays; saMskftam ->
          saMskRitam; fziH -> RRiShiH; SAstra -> zAstra; kArzNi -> kArShNi.
Lossless round-trips: vocalic r/rr/l/l, anusvara, visarga, candrabindu,
avagraha; Vedic accent marks pass through unchanged.

Self-test:  python3 pipeline/sanscript.py
"""
import re
import sys

from indic_transliteration import sanscript as _s

DEVA = _s.DEVANAGARI
IAST = _s.IAST
SLP1 = _s.SLP1
HK = "HK"  # derived flavor (sentinel; not an indic scheme)

# --- user-canonical HK flavor: deterministic SLP1 <-> HK transform ---------
# Aspirates become digraphs (bha=bh), retroflex s becomes Sh, siva-sibilant
# z, guttural nasal G, palatal nasal J, retroflex nasal N; vocalic r/l are
# RRi/RRI/LRi/LRI independent and Ri/RI/LRi/LRI in matra position.
#
# Conversion is a position-by-position LONGEST-MATCH tokenization in both
# directions. (The earlier str.replace chain was lossy: after dh->D it later
# rewrote bare D->q, so dharma round-tripped to डर्म, and G->N fed the later
# N->R rule, so aGka came back as अण्क.)
_FWD = {
    "K": "kh", "G": "gh", "C": "ch", "J": "jh",
    "W": "Th", "Q": "Dh", "T": "th", "D": "dh", "P": "ph", "B": "bh",
    "w": "T", "q": "D",          # retroflex stops keep their HK capitals
    "N": "G", "Y": "J", "R": "N",  # nasals: SLP1 capitals -> HK guttural/palatal
    "S": "z", "z": "Sh",         # siva-sibilant z, retroflex s Sh
}
_INIT = {"f": "RRi", "F": "RRI", "x": "LRi", "X": "LRI"}
_MED = {"f": "Ri", "F": "RI", "x": "LRi", "X": "LRI"}

# HK -> SLP1, grouped by token length for longest-match lookup. Every forward
# product has exactly one inverse here, so the mapping is bijective.
_INV_BY_LEN: dict[int, dict[str, str]] = {3: {}, 2: {}, 1: {}}
for _hk, _slp in [
    ("RRi", "f"), ("RRI", "F"), ("LRi", "x"), ("LRI", "X"),
    ("kh", "K"), ("gh", "G"), ("ch", "C"), ("jh", "J"),
    ("Th", "W"), ("Dh", "Q"), ("th", "T"), ("dh", "D"),
    ("ph", "P"), ("bh", "B"), ("Sh", "z"),
    ("Ri", "f"), ("RI", "F"),
    ("T", "w"), ("D", "q"), ("G", "N"), ("J", "Y"), ("N", "R"),
    ("z", "S"),
]:
    _INV_BY_LEN[len(_hk)][_hk] = _slp


def _word_slp1_to_hk(w: str) -> str:
    out = []
    i = 0
    first = True
    while i < len(w):
        ch = w[i]
        if first and ch in _INIT:
            out.append(_INIT[ch])
            i += 1
            continue
        if ch in _MED:
            out.append(_MED[ch])
            i += 1
            continue
        if ch in _FWD:
            out.append(_FWD[ch])
        else:
            out.append(ch)
        i += 1
        first = False
    return "".join(out)


def _slp1_to_hk(s: str) -> str:
    return " ".join(_word_slp1_to_hk(w) for w in s.split(" "))


def _hk_word_to_slp1(w: str) -> str:
    out = []
    i = 0
    while i < len(w):
        for n in (3, 2, 1):
            tok = w[i:i + n]
            if n in _INV_BY_LEN and tok in _INV_BY_LEN[n]:
                out.append(_INV_BY_LEN[n][tok])
                i += n
                break
        else:
            out.append(w[i])
            i += 1
    return "".join(out)


def _hk_to_slp1(s: str) -> str:
    return " ".join(_hk_word_to_slp1(w) for w in s.split(" "))


def transliterate(text: str, frm: str, to: str) -> str:
    """frm/to: DEVA | IAST | SLP1 | HK. Unknown chars pass through unchanged
    (incl. Vedic accent marks), keeping round-trips lossless."""
    if frm == to:
        return text
    # normalize HK through SLP1 pivot
    if frm == "HK":
        return transliterate(_hk_to_slp1(text), SLP1, to)
    if to == "HK":
        return _slp1_to_hk(transliterate(text, frm, SLP1))
    return _s.transliterate(text, frm, to)


def slp1_key(text: str) -> str:
    """Canonical shard key: SLP1 lowercase of Devanagari/IAST/HK/SLP1 input."""
    if any("\u0900" <= c <= "\u097f" for c in text):
        return _s.transliterate(text, DEVA, SLP1).lower()
    if any(c in text for c in "\u0101\u012b\u016b\u1e5b\u1e5d\u1e37\u1e39"
                               "\u1e45\u00f1\u1e6d\u1e0d\u1e47\u015b\u1e63"
                               "\u1e43\u1e25"):
        return _s.transliterate(text, IAST, SLP1).lower()
    return _hk_to_slp1(text).lower()  # assume HK-shaped ascii


# ---------------------------------------------------------------------------
# (devanagari, iast, user-HK, slp1)
_SELFTEST = [
    ("\u092d\u0917\u0935\u0926\u094d\u0917\u0940\u0924\u093e",
     "bhagavadg\u012bt\u0101", "bhagavadgItA", "BagavadgItA"),
    ("\u0938\u0902\u0938\u094d\u0915\u0943\u0924\u092e\u094d",
     "sa\u1e43sk\u1e5btam", "saMskRitam", "saMskftam"),
    ("\u090b\u0937\u093f\u0903",
     "\u1e5b\u1e63i\u1e25", "RRiShiH", "fziH"),
    ("\u0936\u093e\u0938\u094d\u0924\u094d\u0930",
     "\u015b\u0101stra", "zAstra", "SAstra"),
    ("\u0928\u094d\u092f\u093e\u092f",
     "ny\u0101ya", "nyAya", "nyAya"),
    ("\u0915\u093e\u0930\u094d\u0937\u094d\u0923\u093f",
     "k\u0101r\u1e63\u1e47i", "kArShNi", "kArzRi"),
]

# Audit regression set: aspirated finals, j~n, guttural nasal, anusvara.
# (iast, devanagari) — each must round-trip EXACTLY through every
# DEVA -> X -> Y -> Z -> DEVA chain over {IAST, HK, SLP1}.
_ROUNDTRIP = [
    ("dharma", "\u0927\u0930\u094d\u092e"),                  # dharma (was डर्म)
    ("yoga", "\u092f\u094b\u0917"),                          # yoga
    ("k\u1e5b\u1e63\u1e47a",
     "\u0915\u0943\u0937\u094d\u0923"),                      # kRSNa
    ("j\u00f1\u0101na", "\u091c\u094d\u091e\u093e\u0928"),   # jJAna
    ("a\u1e45ka", "\u0905\u0919\u094d\u0915"),               # aGka   (was अण्क)
    ("sa\u1e43ny\u0101sa",
     "\u0938\u0902\u0928\u094d\u092f\u093e\u0938"),          # saMnyAsa
]


def _selftest() -> int:
    fails = 0
    schemes = {"IAST": IAST, "HK": HK, "SLP1": SLP1}
    for deva, iast, hk, slp1 in _SELFTEST:
        checks = (
            ("IAST", transliterate(deva, DEVA, IAST), iast),
            ("HK", transliterate(deva, DEVA, HK), hk),
            ("SLP1", transliterate(deva, DEVA, SLP1), slp1),
        )
        for label, got, want in checks:
            if got != want:
                print(f"FAIL deva->{label}: {deva} got={got!r} want={want!r}")
                fails += 1
        for label in ("IAST", "HK", "SLP1"):
            back = transliterate(
                transliterate(deva, DEVA, schemes[label]),
                schemes[label], DEVA)
            if back != deva:
                print(f"FAIL roundtrip via {label}: {deva} -> {back!r}")
                fails += 1
    # audit regressions: exact round-trip through every scheme order
    import itertools
    for iast, deva in _ROUNDTRIP:
        if transliterate(deva, DEVA, IAST) != iast:
            print(f"FAIL deva->IAST: {deva} "
                  f"got={transliterate(deva, DEVA, IAST)!r} want={iast!r}")
            fails += 1
        for order in itertools.permutations(("IAST", "HK", "SLP1")):
            cur, prev = deva, DEVA
            for name in order:
                sch = schemes[name]
                cur = transliterate(cur, prev, sch)
                prev = sch
            back = transliterate(cur, prev, DEVA)
            if back != deva:
                print(f"FAIL chain DEVA->{'->'.join(order)}->DEVA: "
                      f"{deva!r} came back {back!r}")
                fails += 1
    specials = [
        ("\u0938\u0902", "anusvara"),
        ("\u0930\u093e\u092e\u0903", "visarga"),
        ("\u0924\u0947\u095d", "avagraha"),
        ("\u0905\u0951", "udatta accent"),
        ("\u0921\u0901", "candrabindu"),
        ("\u0932\u0943", "vocalic l cluster"),
        ("\u0915\u094d\u0937", "kSa cluster"),
    ]
    for s0, note in specials:
        for sch_name, sch in (("IAST", IAST), ("HK", HK), ("SLP1", SLP1)):
            rt = transliterate(transliterate(s0, DEVA, sch), sch, DEVA)
            if rt != s0:
                print(f"FAIL {note} roundtrip via {sch_name}: "
                      f"{s0!r} -> {rt!r}")
                fails += 1
    keys = {
        slp1_key("\u092d\u0917\u0935\u0926\u094d\u0917\u0940\u0924\u093e"),
        slp1_key("bhagavadg\u012bt\u0101"),
        slp1_key("BagavadgItA"),
    }
    if len(keys) != 1:
        print(f"FAIL slp1_key cross-script: {keys}")
        fails += 1
    else:
        print(f"canonical key sample: {next(iter(keys))!r}")
    print("sanscript self-test: " +
          ("ALL PASS" if fails == 0 else f"{fails} FAILURES"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(_selftest())
