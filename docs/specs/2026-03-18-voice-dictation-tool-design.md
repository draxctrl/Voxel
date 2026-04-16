# Voice Dictation Tool — Design Spec

**Date:** 2026-03-18
**Status:** Review
**Project:** Voxel

---

## 1. Overview

A Windows desktop voice dictation tool inspired by WisprFlow. The user holds a hotkey, speaks naturally, and polished text is typed into whatever application is currently focused. The app lives in the system tray and works with any app — Chrome, Word, Slack, VS Code, etc.

## 2. Problem Statement

Windows has built-in voice typing (Win+H), but it produces raw, unpolished text with no grammar correction or filler word removal. Users need a tool that takes natural, messy speech and outputs clean, professional text — without requiring manual editing.

## 3. Core User Flow

1. User presses and holds a hotkey (e.g., `Ctrl+Shift+Space`)
2. App records audio from the microphone while the key is held
3. User releases the hotkey — recording stops
4. Audio is sent to Groq Whisper API for transcription
5. Raw transcript is sent to Groq Llama 3 for cleanup (remove filler words, fix grammar, polish)
6. Cleaned text is typed into the currently focused application via keyboard simulation

## 4. Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Hotkey Listener │────▶│ Mic Recorder │────▶│ Groq Whisper API │────▶│ Groq Llama 3 API │────▶│  Text Injector   │
│   (pynput)       │     │  (pyaudio)   │     │  (transcription)  │    │  (text cleanup)   │    │ (clipboard+paste) │
└─────────────────┘     └──────────────┘     └──────────────────┘     └──────────────────┘     └──────────────────┘
                                                                                                         │
                                                                                                    Ctrl+V paste
                                                                                                         ▼
                                                                                                ┌────────────────┐
                                                                                                │  Focused App   │
                                                                                                │ (any window)   │
                                                                                                └────────────────┘
```

### Component Responsibilities

| Component | Library | Responsibility |
|-----------|---------|---------------|
| Hotkey Listener | `pynput` | Listens for global hotkey press/release events |
| Mic Recorder | `pyaudio` | Captures audio from default microphone into WAV buffer |
| Transcription | `groq` SDK | Sends audio to Groq Whisper API, returns raw text |
| Text Cleanup | `groq` SDK | Sends raw text to Groq Llama 3, returns polished text |
| Text Injector | `pyperclip` + `pyautogui` | Copies cleaned text to clipboard, pastes via `Ctrl+V` into focused window |
| System Tray | `pystray` + `Pillow` | Tray icon with menu (settings, quit), visual recording indicator |
| Settings UI | `customtkinter` | Settings window for API key, hotkey config, language |
| Config Storage | `json` | Persists user settings to `%APPDATA%\Voxel\config.json` |

## 5. Tech Stack

- **Language:** Python 3.11+
- **AI Backend:** Groq API (free tier)
  - Whisper Large v3 (`whisper-large-v3`) — speech-to-text transcription
  - Llama 3 70B (`llama3-70b-8192`) — text cleanup and grammar correction
  - Model IDs configurable in settings for future-proofing
- **Audio:** PyAudio — microphone capture
- **Global Hotkey:** pynput — cross-app key listener
- **Text Injection:** pyperclip + pyautogui — clipboard paste (`Ctrl+V`) into focused app
- **System Tray:** pystray + Pillow — tray icon and menu
- **Settings UI:** CustomTkinter — modern-looking settings window
- **Config:** JSON file in `%APPDATA%\Voxel\`
- **Packaging:** PyInstaller — compile to standalone .exe

## 6. Features (v1)

### 6.1 Hold-to-Talk Recording
- User holds a configurable hotkey to record
- Minimum hold duration: 300ms (taps shorter than this are ignored to prevent accidental triggers)
- Visual feedback: tray icon changes color (green = recording)
- Audio captured as WAV in memory (16kHz sample rate, mono, 16-bit PCM)
- Maximum recording duration: 2 minutes (tray shows warning at 1:45, auto-stops at 2:00)
- Release hotkey to stop recording and trigger processing
- OS key-repeat events are filtered out — only physical press/release matters
- Two-stage filtering: (1) hold < 300ms = tap ignored, recording never starts; (2) audio < 0.5s = recording discarded, no API call

### 6.2 AI Transcription + Cleanup
- Raw audio sent to Groq Whisper API
- Raw transcript cleaned by Groq Llama 3 (see Section 7 for full prompt)
- Cleanup goals: remove filler words, fix grammar/punctuation, keep meaning and tone

### 6.3 Text Injection Into Any App
- After cleanup, text is copied to clipboard and pasted via simulated `Ctrl+V`
- Clipboard paste is fast (instant vs character-by-character) and handles Unicode correctly
- User's previous plain-text clipboard content is saved and restored after paste (non-text clipboard content like images cannot be preserved — this is a known limitation)
- A short audio chime plays before pasting (using `winsound.PlaySound` — built-in, no extra dependency)
- If the focused window changes during processing, the text is still placed on clipboard and a toast notification shows "Text ready — paste with Ctrl+V"

### 6.4 System Tray App
- Runs in system tray (not taskbar)
- Tray icon states:
  - **Idle** (grey/default) — ready
  - **Recording** (green) — mic is active
  - **Processing** (yellow) — waiting for AI response
- Right-click menu: Settings, About, Quit
- Starts minimized to tray on launch

### 6.5 Settings Window
- **API Key** — input field for Groq API key (masked)
- **Hotkey** — configurable hotkey (default: `Ctrl+Shift+Space`)
- **Language** — dropdown for transcription language (default: English)
- **Auto-start** — option to launch on Windows startup
- Settings saved to `%APPDATA%\Voxel\config.json`

### 6.6 First Launch Experience
- On first launch, show settings window prompting for Groq API key
- Link to Groq's free API key signup page
- Validate the API key by making a lightweight test call to the Groq API; show success/error feedback
- Hotkey configuration uses a "press any key" capture dialog — user clicks "Record Hotkey", presses their desired combo, and it's saved

## 7. Text Cleanup Prompt

```
You are a dictation cleanup assistant. The user dictated the following text using voice.
Clean it up by:
- Removing filler words (um, uh, like, you know, basically, actually)
- Fixing grammar, spelling, and punctuation
- Keeping the original meaning and tone intact
- Keeping it natural — do not make it overly formal or robotic
- Do NOT add any commentary, explanation, or formatting — return ONLY the cleaned text

Dictated text: "{raw_transcript}"
```

## 8. File Structure

```
Voxel/
├── docs/
│   └── specs/
│       └── 2026-03-18-voice-dictation-tool-design.md
├── src/
│   ├── main.py              # Entry point, initializes all components
│   ├── hotkey_listener.py   # Global hotkey detection
│   ├── mic_recorder.py      # Audio capture from microphone
│   ├── transcriber.py       # Groq Whisper API integration
│   ├── text_cleaner.py      # Groq Llama 3 text cleanup
│   ├── text_injector.py     # Clipboard paste into focused app
│   ├── tray_app.py          # System tray icon and menu
│   ├── settings_ui.py       # Settings window (CustomTkinter)
│   ├── config.py            # Config loading/saving
│   └── assets/
│       ├── icon_idle.png       # Tray icon — idle state
│       ├── icon_recording.png  # Tray icon — recording state
│       ├── icon_processing.png # Tray icon — processing state
│       └── chime.wav           # Short audio chime before text injection
├── build.spec               # PyInstaller build config
├── requirements.txt         # Python dependencies
└── README.md                # Setup and usage instructions
```

## 9. Dependencies

```
groq
pyaudio
pynput
pyautogui
pyperclip
pystray
Pillow
customtkinter
pyinstaller
```

## 10. Threading Model

The app has four concurrent concerns that must coexist:

| Thread | Runs | Notes |
|--------|------|-------|
| **Main thread** | CustomTkinter UI (Tk event loop) | Tk must run on main thread; hidden root window created at startup |
| **Hotkey thread** | `pynput.keyboard.Listener` | Daemon thread; communicates via thread-safe queue |
| **Tray thread** | `pystray.Icon` | Daemon thread; runs its own event loop |
| **Worker thread** | API calls (Groq Whisper + Llama) | Spawned per-request; prevents UI/hotkey blocking |

Communication between threads uses `queue.Queue` (thread-safe). The flow:
1. Hotkey thread detects press → signals mic recorder to start via queue
2. Hotkey thread detects release → signals mic recorder to stop
3. Worker thread picks up audio buffer → calls Groq APIs → puts result in output queue
4. Main thread polls output queue → triggers text injection

**Overlapping recordings:** If the user starts a new recording while a previous one is still being processed by the API, the new recording proceeds normally and is queued. Requests are processed sequentially (FIFO). The tray icon shows "processing" until all queued requests are complete.

**Quit during recording/processing:** If the app is quit while recording, the in-progress recording is discarded. If quit during API processing, the request is abandoned (no result injected). A graceful shutdown gives worker threads up to 2 seconds to finish before force-terminating.

Logging uses Python's built-in `logging` module with `RotatingFileHandler`.

## 11. Error Handling

| Error | User-Facing Behavior |
|-------|---------------------|
| No internet / network timeout | Tray icon turns red; toast: "No internet connection" |
| Invalid/expired API key | Settings window opens with error message; "Please update your API key" |
| Groq rate limit exceeded | Toast: "Rate limit reached — try again in X seconds" |
| Microphone not found / in use | Toast: "Microphone unavailable — check your audio settings" |
| Recording too short (<0.5s of audio) | Silently ignored (no API call made) |
| Groq API returns empty transcript | Toast: "Couldn't hear anything — try speaking louder" |
| Clipboard paste fails | Text stays on clipboard; toast: "Text copied — paste manually with Ctrl+V" |
| Unexpected exception | Logged to `%APPDATA%\Voxel\voxel.log`; tray icon turns red |

Log file location: `%APPDATA%\Voxel\voxel.log` (rolling, max 5MB).

## 12. Auto-Start Mechanism

Auto-start uses the Windows Registry key `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`. When enabled, a registry entry pointing to the .exe path is created. When disabled, the entry is removed. This approach requires no admin privileges and is the standard method for user-level auto-start apps.

## 13. Out of Scope (v1)

- Personal dictionary / custom vocabulary
- Voice shortcuts / snippets
- Tone adjustment per application
- Cross-device sync
- Always-on / continuous listening mode
- Multi-language auto-detection (manual selection only)
- Push-to-talk toggle mode (hold-only for v1)

## 14. Future Enhancements (v2+)

- Personal dictionary that learns user-specific words
- Snippet library (voice shortcuts for common phrases)
- Per-app tone adjustment
- Toggle mode (press once to start, press again to stop)
- Audio history / transcript log
- Offline fallback with local Whisper model

## 15. Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Groq free tier rate limits | Show clear error message; queue requests; consider local fallback |
| Latency (API round-trip) | Show processing indicator; optimize audio encoding; use streaming if available |
| Hotkey conflicts with other apps | Make hotkey fully configurable; suggest uncommon defaults |
| PyAudio installation issues on Windows | Bundle pre-built wheels; document troubleshooting |
| Clipboard paste blocked by some apps | Document known limitations; text remains on clipboard for manual paste |
| Elevated (admin) windows block input | Document limitation; app cannot type into admin windows unless run as admin |
| Groq free tier discontinued | Design allows swapping API backend; document migration path to OpenAI or local Whisper |
