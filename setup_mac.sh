#!/bin/bash
# Voxel - macOS Setup
# Run: chmod +x setup_mac.sh && ./setup_mac.sh

set -e

echo ""
echo "  ========================================"
echo "    🎙  Voxel - Voice Dictation"
echo "  ========================================"
echo ""

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo "  Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "  Installing Python..."
    brew install python
fi

# Install portaudio (required by PyAudio on macOS)
echo "  [1/3] Installing system dependencies..."
brew install portaudio 2>/dev/null || true

# Install Python dependencies
echo "  [2/3] Installing Python packages..."
pip3 install groq pyaudio pynput pyautogui pyperclip pystray Pillow customtkinter --quiet

# Generate assets if missing
if [ ! -f "src/assets/icon_idle.png" ] || [ ! -s "src/assets/icon_idle.png" ]; then
    echo "  [2.5/3] Generating assets..."
    python3 -c "
from PIL import Image
import struct, wave, math

for name, color in [('icon_idle', (128, 128, 128)), ('icon_recording', (0, 200, 0)), ('icon_processing', (255, 200, 0))]:
    img = Image.new('RGBA', (64, 64), color + (255,))
    img.save(f'src/assets/{name}.png')

with wave.open('src/assets/chime.wav', 'w') as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(44100)
    frames = b''.join(
        struct.pack('<h', int(16000 * math.sin(2 * math.pi * 880 * i / 44100)))
        for i in range(int(44100 * 0.15))
    )
    f.writeframes(frames)
"
fi

echo "  [3/3] Launching Voxel..."
echo ""
echo "  ⚠️  macOS will ask for Accessibility & Microphone permissions."
echo "     Grant them in System Settings → Privacy & Security."
echo ""
echo "  Hold Ctrl+Shift+Space to dictate!"
echo "  ========================================"
echo ""

python3 -m src.main
