#!/usr/bin/env python3
"""SUPERSEDED — kept as a stub for pipeline compatibility.

The MW-stem fallback this script provided now lives inside
build_morph.py's coverage tiers (final-char trim x1-2 on shard stems,
then longest Monier-Williams <k1> prefix), with parses honestly marked
f:"(inferred)" instead of the old p:"stem"/"mw-prefix" labeling.

Running this script is a no-op; rerun build_morph.py to regenerate.
"""
import sys


def main() -> None:
    print("[expand] superseded by build_morph.py fallback tier — "
          "rerun pipeline/build_morph.py instead; nothing to do.")
    return


if __name__ == "__main__":
    main()
    sys.exit(0)
