#!/usr/bin/env bash
# Sync webdemo.wasm from the sibling moonbit-samsaadhanii build output into
# this site's public/wasm/. Prints sizes + SHA-256 of both sides so the copy
# can be eyeballed against public/wasm/LICENSE.
#
# Usage:
#   scripts/fetch-wasm.sh [SRC_DIR]     # default: ../moonbit-samsaadhanii/web/dist
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SRC_DIR="${1:-$ROOT/../moonbit-samsaadhanii/web/dist}"
DEST_DIR="$ROOT/public/wasm"
SRC_FILE="$SRC_DIR/webdemo.wasm"

if [ ! -f "$SRC_FILE" ]; then
  echo "error: $SRC_FILE not found." >&2
  echo "build it first in the sibling repo:" >&2
  echo "  cd $ROOT/../moonbit-samsaadhanii && moon build --release --target wasm-gc src/webdemo && cp _build/wasm-gc/release/build/src/webdemo/webdemo.wasm web/dist/" >&2
  exit 1
fi

mkdir -p "$DEST_DIR"

# cp (not rsync -a): keep mtime fresh on every sync; perms are irrelevant for
# a file that only gets served verbatim by Vite from public/.
cp -f "$SRC_FILE" "$DEST_DIR/webdemo.wasm"

# sha256sum on Linux, shasum -a 256 on macOS.
sha256() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  else shasum -a 256 "$1" | cut -d' ' -f1
  fi
}

SRC_SHA="$(sha256 "$SRC_FILE")"
DST_SHA="$(sha256 "$DEST_DIR/webdemo.wasm")"
SRC_SZ="$(wc -c < "$SRC_FILE" | tr -d ' ')"
DST_SZ="$(wc -c < "$DEST_DIR/webdemo.wasm" | tr -d ' ')"

echo "src : $SRC_FILE"
echo "      $SRC_SZ B  sha256=$SRC_SHA"
echo "dest: $DEST_DIR/webdemo.wasm"
echo "      $DST_SZ B  sha256=$DST_SHA"

if [ "$SRC_SHA" != "$DST_SHA" ]; then
  echo "error: checksum mismatch after copy" >&2
  exit 2
fi

echo "ok: artifact synced. Update the fingerprint in public/wasm/LICENSE if it changed."
