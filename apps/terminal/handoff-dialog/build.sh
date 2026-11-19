#!/bin/sh
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
DEST="$ROOT/../bin"
mkdir -p "$DEST"
cd "$ROOT"
swift build -c release
install -m 755 "$ROOT/.build/release/skeptic-handoff-dialog" "$DEST/skeptic-handoff-dialog"
echo "Built $DEST/skeptic-handoff-dialog"