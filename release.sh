#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

APPIMAGE_NAME="SYRAG_universal_source_1.1-x86_64.AppImage"
APPIMAGE_TOOL_LOCAL="$ROOT_DIR/appimagetool.AppImage"
APPIMAGE_TOOL_URL="https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage"

printf "[1/5] Building AppDir...\n"
chmod +x "$ROOT_DIR/build_appimage.sh"
"$ROOT_DIR/build_appimage.sh"

printf "[2/5] Ensuring appimagetool...\n"
if command -v appimagetool >/dev/null 2>&1; then
  APPIMAGE_TOOL_BIN="appimagetool"
else
  if [[ ! -x "$APPIMAGE_TOOL_LOCAL" ]]; then
    wget -q -O "$APPIMAGE_TOOL_LOCAL" "$APPIMAGE_TOOL_URL"
    chmod +x "$APPIMAGE_TOOL_LOCAL"
  fi
  APPIMAGE_TOOL_BIN="$APPIMAGE_TOOL_LOCAL"
fi

printf "[3/5] Building AppImage...\n"
if [[ "$APPIMAGE_TOOL_BIN" == *.AppImage ]]; then
  APPIMAGE_EXTRACT_AND_RUN=1 ARCH=x86_64 "$APPIMAGE_TOOL_BIN" "$ROOT_DIR/AppDir" "$ROOT_DIR/$APPIMAGE_NAME"
else
  ARCH=x86_64 "$APPIMAGE_TOOL_BIN" "$ROOT_DIR/AppDir" "$ROOT_DIR/$APPIMAGE_NAME"
fi

printf "[4/5] Generating checksum...\n"
sha256sum "$ROOT_DIR/$APPIMAGE_NAME" > "$ROOT_DIR/$APPIMAGE_NAME.sha256"

printf "[5/5] Smoke test (--cli)...\n"
APPIMAGE_EXTRACT_AND_RUN=1 "$ROOT_DIR/$APPIMAGE_NAME" --cli | head -40

printf "\nRelease artifacts ready:\n"
ls -lh "$ROOT_DIR/$APPIMAGE_NAME" "$ROOT_DIR/$APPIMAGE_NAME.sha256"
