#!/bin/bash
# ThomsonLint-KiCad installer
# Sets up: dependencies, kicad-cli (Flatpak), and Claude Code MCP server

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SETTINGS_FILE="$HOME/.claude/settings.json"

echo "=== ThomsonLint-KiCad Installer ==="
echo ""

# 1. Install Python dependencies
echo "[1/3] Installing Python dependencies..."
uv sync --directory "$REPO_DIR"
echo "  Done."
echo ""

# 2. Check kicad-cli
echo "[2/3] Checking kicad-cli..."
if command -v kicad-cli &> /dev/null; then
    echo "  kicad-cli found: $(kicad-cli --version)"
elif flatpak list 2>/dev/null | grep -q org.kicad.KiCad; then
    echo "  KiCad installed via Flatpak but kicad-cli not on PATH."
    echo "  Creating wrapper at /usr/local/bin/kicad-cli (needs sudo)..."
    echo '#!/bin/sh' | sudo tee /usr/local/bin/kicad-cli > /dev/null
    echo 'exec flatpak run --command=kicad-cli org.kicad.KiCad "$@"' | sudo tee -a /usr/local/bin/kicad-cli > /dev/null
    sudo chmod +x /usr/local/bin/kicad-cli
    echo "  Done: kicad-cli $(kicad-cli --version)"
else
    echo "  WARNING: KiCad not found. Install KiCad 8+ and re-run this script."
    echo "  The tool will work without kicad-cli but net analysis will be incomplete."
fi
echo ""

# 3. Add MCP server to Claude Code
echo "[3/3] Configuring Claude Code MCP server..."
if [ ! -f "$SETTINGS_FILE" ]; then
    mkdir -p "$(dirname "$SETTINGS_FILE")"
    echo '{}' > "$SETTINGS_FILE"
fi

# Use python to safely merge into existing settings.json
uv run --directory "$REPO_DIR" python -c "
import json, sys

settings_file = '$SETTINGS_FILE'
repo_dir = '$REPO_DIR'

with open(settings_file) as f:
    settings = json.load(f)

if 'mcpServers' not in settings:
    settings['mcpServers'] = {}

if 'thomsonlint' in settings['mcpServers']:
    print('  MCP server already configured, updating...')

settings['mcpServers']['thomsonlint'] = {
    'command': 'uv',
    'args': ['--directory', repo_dir, 'run', 'thomsonlint', 'serve']
}

with open(settings_file, 'w') as f:
    json.dump(settings, f, indent=2)

print('  Done.')
"
echo ""

echo "=== Installation complete ==="
echo ""
echo "Usage:"
echo "  CLI:    uv run thomsonlint export /path/to/project.kicad_pro --output ./exports/"
echo "  Claude: Open a new Claude Code session and ask:"
echo "          \"Review my KiCad design at /path/to/project.kicad_pro\""
echo ""
