<div align="center">

# 🎙️ Voxel

### Hold a hotkey. Speak. Clean text appears wherever your cursor is.

### Say bye bye to [WisprFlow](https://wisprflow.ai/) 👋

[![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)](../../releases)
[![macOS](https://img.shields.io/badge/macOS-000000?style=for-the-badge&logo=apple&logoColor=white)](#-install-macos)
[![Python](https://img.shields.io/badge/Python_3.13+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-6366f1?style=for-the-badge)](LICENSE)

<br>

**Free & open-source voice dictation for Windows & macOS**
<br>
Powered by Groq Whisper + Llama 3. No subscriptions, no cost.

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
> ✨ **Llama 3** (text cleanup) - removes filler words, fixes grammar, keeps your tone

The result: you speak naturally, and clean text appears. **No editing needed.**

### Voxel vs WisprFlow

| | Voxel | WisprFlow |
|---|---|---|
| Price | **Free forever** | $8/mo+ |
| Open source | Yes | No |
| AI cleanup | Yes (Groq Llama 3) | Yes |
| Works in any app | Yes | Yes |
| Customizable hotkey | Yes | Yes |
| No account required | Just a free Groq API key | Requires account + payment |
| Windows + macOS | Yes | Yes |

---

## ⚡ How it works

```
1. 🟢 Hold your hotkey (default: Ctrl+Shift+Space)
2. 🎙️ Speak naturally - say "um" and "like" all you want
3. 🔴 Release the hotkey
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

```bash
git clone https://github.com/draxctrl/Voxel.git
cd Voxel/BudgetWhisper-mac
chmod +x setup_mac.sh
bash setup_mac.sh
bash run.sh
```

> ⚠️ macOS will ask for **Microphone**, **Accessibility**, and **Input Monitoring** permissions - say yes to all.

Default hotkey on Mac: `Cmd+Shift+Space`

---

## ⚙️ Settings

Right-click the tray icon or click the taskbar window to open settings:

| Setting | Description |
|---------|-------------|
| 🔑 **API Key** | Your Groq API key |
| ⌨️ **Hotkey** | Customizable push-to-talk key combo |
| 🌍 **Language** | Transcription language (English, Spanish, French, German, etc.) |
| 🔇 **Mute sounds** | Disable the chime after recording |
| 📋 **Always copy to clipboard** | Leave transcribed text on clipboard after pasting |
| 💬 **Show clipboard notice** | Show a notification when text is copied instead of pasted |

---

## 🛠️ Tech stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.13+ |
| AI Backend | Groq API (free) - Whisper Large v3 + Llama 3.3 70B |
| UI Framework | PyQt6 |
| Hotkey Listener | pynput |
| Audio | PyAudio |
| System Tray | pystray |
| Packaging | PyInstaller + NSIS |

---

<div align="center">

### 💜 Support this project

If Voxel saves you time, consider supporting development:

[![PayPal](https://img.shields.io/badge/PayPal-Support_Voxel-6366f1?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/draxctrl)

Built with <3 by **Drax**

MIT License

</div>
