#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
APPIMAGE_DEFAULT="$ROOT_DIR/SYRAG_universal_source_1.1-x86_64.AppImage"
APPIMAGE="${1:-$APPIMAGE_DEFAULT}"

if [[ ! -f "$APPIMAGE" ]]; then
  echo "❌ AppImage not found: $APPIMAGE"
  exit 1
fi

chmod +x "$APPIMAGE" || true

run_direct() {
  "$APPIMAGE" "$@"
}

run_extract_mode() {
  APPIMAGE_EXTRACT_AND_RUN=1 "$APPIMAGE" "$@"
}

is_noexec_fs() {
  local mount_point
  mount_point="$(df -P "$APPIMAGE" | awk 'NR==2{print $6}')"
  mount | grep " on ${mount_point} " | grep -q noexec
}

if is_noexec_fs; then
  echo "⚠️ Detected noexec filesystem, copying AppImage to /tmp..."
  tmp_app="/tmp/$(basename "$APPIMAGE")"
  cp -f "$APPIMAGE" "$tmp_app"
  chmod +x "$tmp_app"
  APPIMAGE="$tmp_app"
fi

echo "▶ Launch attempt 1: direct execution"
if run_direct "$@"; then
  exit 0
fi

echo "⚠️ Direct launch failed; retrying with APPIMAGE_EXTRACT_AND_RUN=1"
if run_extract_mode "$@"; then
  exit 0
fi

echo "❌ AppImage launch failed in both direct and extract-and-run modes."
echo "   Tip: verify libc compatibility and try running with:"
echo "   APPIMAGE_EXTRACT_AND_RUN=1 $APPIMAGE"
exit 1
