<div align="center">

<img src="docs/banner.png" alt="Voxel - Your voice, clean text, any app" width="700" />

# 🎙️ Voxel

### Hold a hotkey. Speak. Clean text appears wherever your cursor is.

### Say bye bye to [WisprFlow](https://wisprflow.ai/) 👋

[![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)](../../releases)
[![macOS](https://img.shields.io/badge/macOS-000000?style=for-the-badge&logo=apple&logoColor=white)](#-install-macos)
[![Python](https://img.shields.io/badge/Python_3.13+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License: GPL v3](https://img.shields.io/badge/License-GPL_v3-6366f1?style=for-the-badge)](LICENSE)

<br>

**Free & open-source voice dictation for Windows & macOS**
<br>
Powered by Groq Whisper + GPT-OSS. No subscriptions, no cost.

<br>

<img src="https://img.shields.io/badge/Speak_naturally-Remove_filler_words-22c55e?style=flat-square" />
<img src="https://img.shields.io/badge/Fix_grammar-Auto_punctuation-6366f1?style=flat-square" />
<img src="https://img.shields.io/badge/Works_in-Any_app-f59e0b?style=flat-square" />
<img src="https://img.shields.io/badge/Price-$0_forever-ef4444?style=flat-square" />

</div>

---

## 🤔 Why Voxel exists

[WisprFlow](https://wisprflow.ai/) is a great voice dictation tool, but it costs money. Voxel does the same thing for **free**.

If you use **Claude Code in VS Code** (or any AI coding extension), you lose the ability to talk via mic. Voxel brings it back. Hold a hotkey, speak, and your cleaned-up text gets pasted right into the chat, the terminal, or wherever your cursor is.

Windows has built-in voice typing (`Win+H`), but it produces messy, unedited text. You still have to go back and fix grammar, remove filler words, and add punctuation. That defeats the purpose.

Voxel fixes this by running your speech through **two AI steps**:

> 🎤 **Whisper** (speech-to-text) - transcribes your voice accurately
>
> ✨ **GPT-OSS 120B** (text cleanup) - removes filler words, fixes grammar, keeps your tone

The result: you speak naturally, and clean text appears. **No editing needed.**

### Voxel vs WisprFlow

| | Voxel | WisprFlow |
|---|---|---|
| Price | **Free forever** | $8/mo+ |
| Open source | Yes | No |
| AI cleanup | Yes (Groq GPT-OSS 120B) | Yes |
| Works in any app | Yes | Yes |
| Customizable hotkey | Yes | Yes |
| Offline mode | Yes (local Whisper) | No |
| Dictation history | Yes | Yes |
| Custom voice commands | Yes | Yes |
| Multiple dictation modes | Yes (6 built-in) | Yes |
| Per-app auto profiles | Yes | Yes |
| Statistics dashboard | Yes | Yes |
| No account required | Just a free Groq API key | Requires account + payment |
| Windows + macOS | Yes | Yes |

---

## ✨ Features

### Core
- 🎙️ **Push-to-talk** - hold hotkey, speak, release, get clean text
- ✨ **AI text cleanup** - removes "um", "uh", fixes grammar, adds punctuation
- 🌐 **Works in any app** - Chrome, VS Code, Slack, Word, Discord, Notepad
- ⌨️ **Customizable hotkey** - set any combo you like
- 🎤 **Mic selector** - choose your recording device
- 🌍 **Auto-detect language** - or pick from 9 languages

### Smart Features
- 📚 **Dictation History** - every transcription saved, searchable
- 🎭 **6 Dictation Modes** - Raw, Grammar only (keeps your words), Grammar + tidy up, Professional Email, Code Comments, Technical Writing
- 🗣️ **Voice Commands** - say "sign off" → insert your signature template
- 📊 **Statistics Dashboard** - track your usage and time saved
- 🪄 **Auto-switch profile per app** - use "Professional" in Outlook, "Code" in VS Code
- 💾 **Offline Mode** - use local Whisper model, no internet needed

### Polish
- 🎨 **Light and dark themes** that follow your Windows setting
- 🔊 **Audio feedback** (or mute if you prefer)
- 📋 **Clipboard fallback** - copies text if no text field is focused
- 📋 **Always copy to clipboard** option
- 🔒 **Privacy-focused** - your API key never leaves your machine

---

## ⚡ How it works

```
1. 🟢 Hold your hotkey (default: Ctrl+Shift+Space)
   (or tap once to start if you switch Activation to toggle)
2. 🎙️ Speak naturally - say "um" and "like" all you want
3. 🔴 Release the hotkey (or tap again in toggle mode)
4. ✅ Clean, polished text is pasted into whatever app you're using
```

Works with **any app** - Chrome, VS Code, Word, Slack, Discord, Notepad, you name it.

---

## ⏱️ Recording limit

Groq's free tier has a limit on audio length per request. If you hit it, just **release the hotkey and press it again** to start a new recording. It's seamless - you won't lose anything. For most dictation (emails, messages, code comments), you'll never hit the limit.

---

## 🔑 Getting a Groq API Key (free)

| Step | Action |
|------|--------|
| 1 | Go to [console.groq.com](https://console.groq.com) |
| 2 | Sign up for a free account (Google/GitHub sign-in works) |
| 3 | Go to **API Keys** in the sidebar |
| 4 | Click **Create API Key** |
| 5 | Copy the key (starts with `gsk_`) |
| 6 | Paste it into Voxel's settings when you first launch |

> 💡 No credit card. No trial period. Just free.

---

## 🪟 Install (Windows)

### Option 1: Installer
Download **`Voxel_Setup.exe`** from [📦 Releases](../../releases), run it, done.

### Option 2: From source
```bash
git clone https://github.com/draxctrl/Voxel.git
cd Voxel
pip install -r requirements.txt
python -m src.main
```

---

## 🍎 Install (macOS)

### Option 1: DMG
Download **`Voxel.dmg`** from [📦 Releases](../../releases), open it, drag **Voxel** into your Applications folder, done.

### Option 2: From source
```bash
git clone https://github.com/draxctrl/Voxel.git
cd Voxel/BudgetWhisper-mac
chmod +x setup_mac.sh run.sh
bash setup_mac.sh
bash run.sh
```

> ⚠️ macOS will ask for **Microphone**, **Accessibility**, and **Input Monitoring** permissions - say yes to all.

Default hotkey on Mac: `Cmd+Shift+Space`

---

## 🎨 What it looks like

Everything lives in one window now. Pick a topic on the left, and that is
all you see on the right - no scrolling past settings you were not looking
for. History and Statistics used to be windows of their own; they are
sections in here instead.

<div align="center">
<img src="docs/screenshots/settings-writing-style.png" alt="The settings window: a sidebar on the left, one topic at a time on the right" width="760" />
<br><br>
<img src="docs/screenshots/history.png" alt="History: everything you have dictated, searchable, inside the main window" width="760" />
<br><br>
<img src="docs/screenshots/appearance-light.png" alt="The same window in light mode" width="760" />
</div>

What changed in this release:

- **A sidebar instead of one long page.** One topic on screen at a time.
- **History and Statistics moved inside** and stopped being separate windows.
- **Plain-language labels** - "Writing style" rather than "Dictation Mode".
- **Light and dark**, following your Windows setting, or pinned to one.
- **Settings apply the moment you change them.** There is no Save button.

---

## ⚙️ Settings

Right-click the tray icon and choose **Settings**. Everything below is
in that one window:

| Section | What is in it |
|---------|---------------|
| ✏️ **Writing style** | How much Voxel tidies up what you say, plus offline mode |
| 🗣️ **Voice commands** | Trigger phrases that expand into templates |
| 🌍 **Language** | Auto-detect, or pick from 9 languages |
| 🎤 **Microphone** | Choose your device and watch its level move as you talk |
| ⌨️ **Shortcuts** | Your hotkey, and hold-to-talk versus press-to-start |
| 🎨 **Appearance** | Light or dark, and what Voxel shows while you are talking |
| 🕓 **History** | Everything you have dictated, searchable |
| 📊 **Stats** | Words dictated and time saved |
| ⚙️ **General** | Your Groq key, sounds, clipboard behaviour, start with Windows |
| ℹ️ **About** | Version and licence |

---

## 🛠️ Tech stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.13+ |
| AI Backend | Groq API (free) - Whisper Large v3 + GPT-OSS 120B |
| Offline Transcription | faster-whisper (CTranslate2) |
| UI Framework | PyQt6 |
| Hotkey Listener | pynput |
| Audio | PyAudio |
| System Tray | pystray |
| Storage | SQLite (history) + JSON (config) |
| Packaging | PyInstaller + NSIS |

---

<div align="center">

### 💜 Support this project

If Voxel saves you time, consider supporting development:

[![PayPal](https://img.shields.io/badge/PayPal-Support_Voxel-6366f1?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/draxctrl)

</div>

## 📄 Licence

Voxel is released under the **GNU General Public License v3.0** - see
[LICENSE](LICENSE).

In plain words: you are free to use Voxel, read its source and change it.
If you share a changed version, you have to share your changes under the
same licence. Nobody can take this work, close the source and sell it.

Voxel is built on PyQt6, which is itself GPL v3, so this is also the
licence the project is required to use.

Bundled third-party work keeps its own licence: Phosphor Icons (MIT),
Inter (SIL Open Font License), and the flag artwork under
`src/assets/flags/`.
