#!/bin/bash
set -e

echo ""
echo "  🎙  Voxel — Mac Setup"
echo "  ─────────────────────────────"
echo ""

# Check for Homebrew
if ! command -v brew &>/dev/null; then
    echo "❌  Homebrew not found. Install it first:"
    echo '    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    exit 1
fi

# Install portaudio (required by PyAudio)
echo "📦  Installing portaudio..."
brew install portaudio 2>/dev/null || echo "  (already installed)"

# Check for Python 3.11+
if ! command -v python3 &>/dev/null; then
    echo "📦  Installing Python..."
    brew install python@3.13
fi

PYTHON=$(command -v python3)
echo "🐍  Using: $PYTHON ($($PYTHON --version))"

# Create virtual environment
echo "📦  Creating virtual environment..."
$PYTHON -m venv .venv
source .venv/bin/activate

# Install dependencies
echo "📦  Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo ""
echo "✅  Setup complete!"
echo ""
echo "  To run Voxel:"
echo "    cd $(pwd)"
echo "    source .venv/bin/activate"
echo "    python -m src.main"
echo ""
echo "  Default hotkey: Cmd + Shift + Space (hold to record)"
echo ""
echo "  ⚠️  macOS will ask for these permissions (System Settings → Privacy & Security):"
echo "    • Microphone access"
echo "    • Accessibility (for keyboard shortcuts and text pasting)"
echo "    • Input Monitoring (for global hotkeys)"
echo ""
