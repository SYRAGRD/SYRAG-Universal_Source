#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
APPDIR="$ROOT_DIR/AppDir"
SYRAG_RD_LOGO_SVG="$ROOT_DIR/assets/SYRAGRD2.svg"
SYRAG_LOGO_REPO_PNG="$ROOT_DIR/assets/syrag.png"
SYRAG_LOGO_LEGACY_PNG="$ROOT_DIR/../../syrag.png"
PAYLOAD_DIR="$APPDIR/usr/share/codescan"

mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$PAYLOAD_DIR"

cp -r "$ROOT_DIR/src" "$PAYLOAD_DIR/"
cp -r "$ROOT_DIR/config" "$PAYLOAD_DIR/"
cp "$ROOT_DIR/requirements.txt" "$PAYLOAD_DIR/requirements.txt"

cat > "$APPDIR/AppRun" << 'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/codescan" "$@"
EOF
chmod +x "$APPDIR/AppRun"

cat > "$APPDIR/usr/bin/codescan" << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
HERE="$(dirname "$(readlink -f "$0")")"
PAYLOAD="$HERE/../share/codescan"
export PYTHONPATH="$PAYLOAD/src:${PYTHONPATH:-}"

is_cli_mode="false"
for arg in "$@"; do
	if [[ "$arg" == "--cli" ]]; then
		is_cli_mode="true"
		break
	fi
done

if [[ "$is_cli_mode" == "true" ]]; then
	exec python3 "$PAYLOAD/src/main.py" "$@"
fi

RUNTIME_DIR="$HOME/.codescan_runtime"
RUNTIME_VENV="$RUNTIME_DIR/venv"
RUNTIME_PY="$RUNTIME_VENV/bin/python"

mkdir -p "$RUNTIME_DIR"

if [[ ! -x "$RUNTIME_PY" ]]; then
	python3 -m venv "$RUNTIME_VENV"
	"$RUNTIME_VENV/bin/pip" install -q --upgrade pip
	"$RUNTIME_VENV/bin/pip" install -q -r "$PAYLOAD/requirements.txt"
fi

if ! "$RUNTIME_PY" -c "import PyQt5, requests" >/dev/null 2>&1; then
	"$RUNTIME_VENV/bin/pip" install -q -r "$PAYLOAD/requirements.txt"
fi

exec "$RUNTIME_PY" "$PAYLOAD/src/main.py" "$@"
EOF
chmod +x "$APPDIR/usr/bin/codescan"

cat > "$APPDIR/usr/share/applications/codescan.desktop" << 'EOF'
[Desktop Entry]
Name=SYRAG™ universal source 1.1 (Didactic Only)
Exec=codescan
Icon=codescan
Type=Application
Categories=Development;
Comment=Stimulate LLM usage beyond open source toward universal programming languages. Didactic use only.
EOF

cp "$APPDIR/usr/share/applications/codescan.desktop" "$APPDIR/codescan.desktop"

if [[ -f "$SYRAG_RD_LOGO_SVG" ]]; then
	cp "$SYRAG_RD_LOGO_SVG" "$APPDIR/usr/share/icons/hicolor/256x256/apps/codescan.svg"
	cp "$SYRAG_RD_LOGO_SVG" "$APPDIR/codescan.svg"
elif [[ -f "$SYRAG_LOGO_REPO_PNG" ]]; then
	cp "$SYRAG_LOGO_REPO_PNG" "$APPDIR/usr/share/icons/hicolor/256x256/apps/codescan.png"
	cp "$SYRAG_LOGO_REPO_PNG" "$APPDIR/codescan.png"
elif [[ -f "$SYRAG_LOGO_LEGACY_PNG" ]]; then
	cp "$SYRAG_LOGO_LEGACY_PNG" "$APPDIR/usr/share/icons/hicolor/256x256/apps/codescan.png"
	cp "$SYRAG_LOGO_LEGACY_PNG" "$APPDIR/codescan.png"
else
	cat > "$APPDIR/codescan.svg" << 'EOF'
<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <rect width="256" height="256" rx="32" fill="#0f172a"/>
  <path d="M68 88h120v20H68zm0 40h120v20H68zm0 40h80v20H68z" fill="#22d3ee"/>
  <circle cx="180" cy="178" r="20" fill="#22d3ee"/>
</svg>
EOF
	cp "$APPDIR/codescan.svg" "$APPDIR/usr/share/icons/hicolor/256x256/apps/codescan.svg"
fi

echo "AppDir prepared at: $APPDIR"
echo "Next: run appimagetool AppDir" 
