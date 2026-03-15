#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${LYRONA_REPO_URL:-git+https://github.com/milord-x/lyrona.git}"
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$SCRIPT_DIR/pyproject.toml" ]]; then
  SOURCE="$SCRIPT_DIR"
else
  SOURCE="$REPO_URL"
fi

if command -v uv >/dev/null 2>&1; then
  uv tool install --force --reinstall --from "$SOURCE" lyrona
elif command -v pipx >/dev/null 2>&1; then
  pipx install --force "$SOURCE"
elif command -v python3 >/dev/null 2>&1; then
  python3 -m pip install --user --upgrade "$SOURCE"
else
  echo "ERROR: install uv, pipx, or python3 first." >&2
  exit 1
fi

echo
echo "Lyrona installed."
echo "Run: lyrona --help"
echo "If the command is not found, add ~/.local/bin to PATH."
