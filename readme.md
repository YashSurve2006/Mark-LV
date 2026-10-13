<div align="center">

# ⚙️ MARK LV (55)
### Autonomous Cross-Platform Personal Voice AI & Desktop Automation Engine
**Developed by Yash Surve ([@YashSurve2006](https://github.com/YashSurve2006)) — Powered by Google Gemini Live API**

[![Developer](https://img.shields.io/badge/Developer-Yash%20Surve-00E5FF?style=for-the-badge&logo=github&logoColor=white)](https://github.com/YashSurve2006)
[![GitHub Profile](https://img.shields.io/badge/GitHub-YashSurve2006-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/YashSurve2006)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/YashSurve2006/Mark-LV)
[![Gemini Live](https://img.shields.io/badge/Engine-Gemini%203.1%20Flash%20Live-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)
[![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey?style=for-the-badge)](https://creativecommons.org/licenses/by-nc/4.0/)

<br/>

<img src="assets/jarvis_hero_banner.png" alt="JARVIS Mark LV Hero Banner" width="100%" style="border-radius: 12px; box-shadow: 0 8px 32px rgba(0, 229, 255, 0.25);"/>

<br/>

> 🎙️ **A real-time voice AI that can hear, see, speak, and autonomously operate your computer with sub-50ms native reflexes.** Zero subscription fees, zero cloud lock-in, and total digital autonomy.

[⚡ Quick Start](#-quick-start) • [🖥️ Live UI Showcase](#️-live-interface--actual-screenshots) • [🌐 Chrome & OS Control](#-autonomous-chrome--computer-control) • [🏗️ Architecture](#️-system-architecture) • [🔧 Setup & Run Guide](#-step-by-step-setup-and-run-guide) • [👤 Developer](#-developer--community)

</div>

---

## 📑 Table of Contents

- [✨ Overview](#-overview)
- [🖥️ Live Interface & Actual Screenshots](#️-live-interface--actual-screenshots)
- [🌐 Autonomous Chrome & Computer Control](#-autonomous-chrome--computer-control)
- [🏗️ System Architecture](#️-system-architecture)
- [🚀 Core Capabilities](#-core-capabilities)
- [🆕 What's New in Mark LV](#-whats-new-in-mark-lv)
- [⚡ Quick Start](#-quick-start)
- [🔧 Step-by-Step Setup and Run Guide](#-step-by-step-setup-and-run-guide)
  - [1. Prerequisites](#1-prerequisites)
  - [2. Automated Setup (Recommended)](#2-automated-setup-recommended)
  - [3. Manual Setup](#3-manual-installation)
  - [4. Platform-Specific Setup](#4-platform-specific-configuration)
  - [5. How to Run](#5-how-to-run)
- [🎛️ Settings, Drawers & Customization](#️-settings-drawers--customization)
- [🗂️ Project Structure](#️-project-structure)
- [🔒 Security & Data Privacy](#-security--data-privacy)
- [🗺️ Version Roadmap](#️-version-roadmap)
- [👤 Developer & Community](#-developer--community)

---

## ✨ Overview

**Mark LV** bridges conversational intelligence with native computer autonomy. While typical voice assistants only output text or read search results, JARVIS Mark LV takes real physical control of your machine:

1. **Native Eyes & Ears:** Full-duplex bidirectional audio streaming via the **Gemini 3.1 Flash Live API**. Speaks and listens simultaneously with real-time viseme lip synchronization (~50 mouth shapes/sec) and zero cloud audio retention.
2. **Instant Native Motor Control:** Operating directly on your running Windows, macOS, or Linux workspace—manipulating open browser tabs, active applications, window stations, and system settings in sub-50ms.
3. **Autonomous Software Engineering:** Integrated autonomous coding engine (`dev_agent` and `code_helper`) that drafts architectures, writes multi-file apps, executes tests, and opens workspaces directly inside VS Code or Antigravity IDE.
4. **9-Tier Model Ladder with Resilient Failover:** Centralized model fallback cascade with intelligent cooldowns so API quota limits or network dropouts never freeze the assistant.

---

## 🖥️ Live Interface & Actual Screenshots

The HUD is built entirely with **PyQt6** and rendered in pure software. It requires **no dedicated GPU, no OpenGL drivers, and zero bulky game engine dependencies**.

### Actual Application Window

<div align="center">
  <img src="assets/actual_ui_screenshot.png" alt="JARVIS Mark LV Live Running UI" width="100%" style="border-radius: 12px; border: 1px solid rgba(0, 229, 255, 0.3); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);"/>
  <p><i>Actual live running HUD screenshot — 3D Holographic Head Mesh, Reactive Audio Oscilloscope, Hardware Telemetry Gauges, and Real-Time Activity Log.</i></p>
</div>

<br/>

### Controls Drawer & Setup Overlay

<div align="center">
  <table width="100%">
    <tr>
      <td width="50%" align="center">
        <img src="assets/actual_controls_drawer.png" alt="JARVIS Controls Drawer" width="100%" style="border-radius: 8px; border: 1px solid rgba(0, 229, 255, 0.2);"/>
        <br/><b>🎛️ Controls Drawer (Daily Switches)</b>
        <br/><sub>Wake Word, Fullscreen, Morning Brief, Sleep, Push-to-Talk</sub>
      </td>
      <td width="50%" align="center">
        <img src="assets/actual_setup_overlay.png" alt="JARVIS Setup Overlay" width="100%" style="border-radius: 8px; border: 1px solid rgba(0, 229, 255, 0.2);"/>
        <br/><b>⚙️ Setup Drawer (System Configuration)</b>
        <br/><sub>Audio Device Probing, Remote QR Pairing, Auto-Start, Customization</sub>
      </td>
    </tr>
  </table>
</div>

### Interface Features

| Component | Technical Implementation |
|:---|:---|
| **🧑‍🎤 3D Holographic Avatar** | 3D human head geometry computed dynamically from the canonical MediaPipe face model (468 vertices). Features realistic blinking, saccadic eye movements, head nods on emphasized syllables, and ~50Hz phonetic visemes. |
| **〰️ Reactive Waveform** | Real-time audio reactive oscilloscope beneath the avatar. Pulses with electric cyan amplitude while listening to your microphone and matches JARVIS's voice output during playback. |
| **📊 Hardware Telemetry Gauges** | Live circular telemetry meters tracking CPU load, core temperatures, GPU memory, RAM allocation, and network status in real time. |
| **📜 Live System Activity Log** | Transparent event stream detailing every tool call, motor execution, and latency in milliseconds. |
| **🎛️ Split Dual Drawers** | Fast drawer tabs: `⚙ SETUP` (remote access, auto-start, audio devices) and `🎛 CONTROLS` (wake word, HUD themes, fullscreen, sleep timers). |

---

## 🌐 Autonomous Chrome & Computer Control

JARVIS Mark LV works directly on your **active, logged-in Google Chrome browser** and workspace. It never opens an isolated, guest, or empty browser sandbox—all your Google accounts, extensions, tabs, and bookmarks remain active.

<div align="center">
  <img src="assets/jarvis_chrome_control.png" alt="JARVIS Chrome & Productivity Automation" width="100%" style="border-radius: 12px; margin: 16px 0;"/>
</div>

### Key Computer & Browser Capabilities

- **⚡ Lightning-Fast PDF Page Jumper (<40ms):**
  - Instant in-document navigation (`Home` + sequential `PageDown`) that jumps directly to requested page numbers in under 40 milliseconds without screen flicker.
  - Zero-latency URL hash fragment injection (`#page=N`) with automated hotkey reload for large document jumps.
  - Natural relative scrolling (*"scroll down 3 pages"*, *"next page"*, *"scroll up 2 pages"*) with zero AI vision model latency.
- **🔍 Zero-Token Active Address & Page Reader:**
  - Reads active tab URLs and full-page text in under 100ms without consuming Gemini input tokens or screenshot bandwidth.
- **📑 Seamless Tab Navigation:**
  - Switch tabs instantly by name or keyword using native Chromium Quick Tab search (`Ctrl+Shift+A`).
  - Open new tabs, close tabs, duplicate tabs, reload (`Ctrl+F5`), and zoom.
- **💻 Autonomous Coding & Agent IDE Integration:**
  - Ask JARVIS: *"Build a weather FastAPI service in Python and test it"* $\rightarrow$ JARVIS triggers `dev_agent` to draft architecture, generate source files, run unit tests, and open the workspace in VS Code or Antigravity IDE.
- **🖱️ Motor & Desktop Grounding:**
  - Mouse clicks, smooth drag-and-drop, natural wheel scrolling (calibrated to Windows `WHEEL_DELTA` 120 units), window management (minimize, maximize, focus, list), and system settings.

---

## 🏗️ System Architecture

JARVIS Mark LV separates voice processing, cognitive planning, and motor execution into decoupled, non-blocking pipelines:

<div align="center">
  <img src="assets/jarvis_architecture_diagram.png" alt="JARVIS Mark LV Technical Architecture" width="100%" style="border-radius: 12px; margin: 16px 0;"/>
</div>

```mermaid
flowchart TD
    subgraph AudioVision [Full-Duplex I/O Pipeline]
        MIC[Microphone Input] -->|PCM Audio 16kHz| LIVE[Gemini 3.1 Flash Live Session]
        SCREEN[Screen Capture MSS] -->|Scaled Frame| LIVE
        LIVE -->|Raw Audio Stream 24kHz| SPK[Audio Output MME/DirectSound]
        LIVE -->|Transcript & Formants| VISEME[Viseme Analyzer ~50Hz]
        VISEME --> HUD[PyQt6 3D Holographic Avatar]
    end

    subgraph Cognitive [Cognitive & Model Ladder]
        LIVE -->|Tool Call Request| DISPATCH[Action & Plugin Dispatcher]
        DISPATCH --> LADDER[9-Tier Model Ladder Core]
        LADDER --> M1[gemini-3.5-flash-lite]
        LADDER --> M2[gemini-3.1-flash-lite]
        LADDER --> M3[gemini-2.5-flash]
        LADDER --> M4[gemini-flash-lite-latest]
    end

    subgraph Motor [Cross-Platform Motor Engine]
        DISPATCH --> CHROME[Native Chrome Automation]
        DISPATCH --> OS[OS Desktop & Window Control]
        DISPATCH --> AGENT[Autonomous Dev Agent & Coding]
        DISPATCH --> MEM[Local Recallable Memory]
        DISPATCH --> UNDO[Universal Undo Stack]
    end

    CHROME -->|Result in <50ms| LIVE
    OS -->|Result in <20ms| LIVE
    AGENT -->|Status Update| LIVE
```

---

## 🚀 Core Capabilities

### Feature Matrix

| Feature | Category | Description |
|:---|:---|:---|
| **Holographic Avatar** | Visuals | 3D human head rendered via pure software `QPainter` geometry. Zero GPU requirements. |
| **Viseme Lip-Sync** | Speech | ~50 mouth shapes per second calculated from audio formants & transcripts. |
| **Push-to-Talk** | Audio | Hold **`Ctrl + Space`** globally on Windows to open mic; window-scoped on macOS/Linux. |
| **Wake Word Detection** | Voice | Offline **"Hey Jarvis"** wake-word detector with automated sleep after 2 min idle. |
| **Self-Echo Suppression** | Audio | Automatically cancels JARVIS's own audio feedback tail without muting your microphone. |
| **Instant PDF Navigation** | Automation | Jump to any page number or relative pages in Chrome/PDF reader in under 40ms. |
| **Real Chrome Integration** | Browser | Control running tabs, open URLs, search, and switch tabs without launching guest windows. |
| **Autonomous Dev Agent** | Coding | Build complete multi-file apps, run unit tests, and open IDEs directly from voice commands. |
| **9-Tier Model Ladder** | Resilience | Fallback cascade across 9 Gemini models with intelligent failure cooldowns. |
| **Recallable Memory** | Intelligence | Persistent long-term memory with fast local index search (`memory/long_term.json`). |
| **Universal Undo Stack** | Safety | Say *"Undo"* in any language to reverse file edits, folder moves, and settings changes. |
| **Hardware Confirmation** | Safety | Irreversible actions (Shutdown, Restart, WiFi Toggle) require physical UI confirmation. |
| **Video on the HUD** | Media | Play YouTube and local videos directly inside the HUD avatar viewport. |
| **Remote Dashboard** | Mobility | Mobile web dashboard accessible via QR code with self-signed TLS security. |
| **📨 WhatsApp Automation** | Messaging | Compose, draft, and send WhatsApp messages directly via protocol deep-link, desktop UWP app, or web. Includes contact memory & safe drafting mode. |

---

## 🆕 What's New in Mark LV

- 📺 **HUD Video Player:** Replaces avatar viewport on-demand for YouTube or local media with dual-stream synchronization and smart microphone auto-ducking.
- 📨 **Advanced WhatsApp Messaging Engine:** Deep-link protocol, Windows Desktop/UWP UI automation, contact and relationship resolution from memory, and safe review drafting mode.
- 🪜 **Unified 9-Tier Model Ladder:** Centralized fallback in `core/gemini.py` with 5-minute quota cooldowns and 30-minute outage backoffs.
- ⚡ **Ultra-Fast PDF Page Navigation:** Sub-50ms page jumping via in-document motor control and instant hash reloading.
- 🎛️ **Split Drawer Interface:** Clean separation of system configurations (`SETUP`) from daily toggles (`CONTROLS`).
- 🎧 **Calibrated Audio Device Prober:** Selects optimal host APIs (DirectSound for input, MME for output) to eliminate silent audio drops.
- 🔗 **Session Resumption:** Automatically recovers live sessions across audio device switches and transient network hiccups.

---

## ⚡ Quick Start

```bash
# 1. Clone repository
git clone https://github.com/YashSurve2006/Mark-LV.git
cd Mark-LV

# 2. Automated setup (installs OS-specific packages & browser engines)
python setup.py

# 3. Launch JARVIS Mark LV
python main.py
```

> [!NOTE]
> On first launch, JARVIS will ask you for your free **Google Gemini API Key** and store it securely in `config/api_keys.json`.

---

## 🔧 Step-by-Step Setup and Run Guide

### 1. Prerequisites

- **Operating System:** Windows 10/11 (64-bit), macOS 12+ (Apple Silicon or Intel), or Linux (Ubuntu 22.04+, Fedora, Arch).
- **Python:** `3.11`, `3.12`, or `3.13` (Python 3.11 or 3.12 recommended).
- **Audio Hardware:** Working microphone and speakers / headphones.
- **Gemini API Key:** Get a free API key at [Google AI Studio](https://aistudio.google.com/app/apikey).

---

### 2. Automated Setup (Recommended)

Run the included OS-aware setup script:

```bash
python setup.py
```

`setup.py` automatically:
1. Validates your Python version (`>= 3.11`).
2. Filters and installs dependencies for your current OS using `sys_platform` markers.
3. Installs Chromium and Firefox Playwright automation binaries.
4. Verifies the integrity of the 3D face model (`core/face_model.obj`).

---

### 3. Manual Installation

If you prefer installing dependencies manually using `pip`:

```bash
# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser engines
python -m playwright install chromium firefox
```

---

### 4. Platform-Specific Configuration

<details>
<summary><b>🪟 Windows Setup Notes</b></summary>

- **Global Hotkey:** `Ctrl + Space` push-to-talk works globally across all games and fullscreen windows.
- **Python Win32 Postinstall:** If `win32com` prompts for registration, run:
  ```bash
  python Scripts/pywin32_postinstall.py -install
  ```
- **Windows Terminal UTF-8:** Recommended to use Windows Terminal with UTF-8 encoding enabled.
</details>

<details>
<summary><b>🍎 macOS Setup Notes</b></summary>

- **Accessibility Permissions:** Required for keyboard and mouse automation. Grant access under:
  *System Settings $\rightarrow$ Privacy & Security $\rightarrow$ Accessibility $\rightarrow$ Terminal / Python*.
- **Microphone & Screen Recording:** Grant Terminal/IDE permission to capture audio and screen when prompted.
- **Push-to-Talk:** Push-to-talk operates within window scope on macOS.
</details>

<details>
<summary><b>🐧 Linux Setup Notes</b></summary>

- **Audio Subsystem:** Ensure `portaudio19-dev` and `pulseaudio` or `pipewire` headers are installed:
  ```bash
  sudo apt-get install portaudio19-dev libasound2-dev libpulse-dev
  ```
- **X11 / Wayland:** For full mouse and keyboard automation on Wayland, ensure XWayland compatibility or use an X11 desktop session.
</details>

---

### 5. How to Run

Launch JARVIS using the primary runner:

```bash
python main.py
```

Or launch the standalone UI window:

```bash
python ui.py
```

---

## 🎛️ Settings, Drawers & Customization

| Action | How to Trigger | Description |
|:---|:---|:---|
| **Push-to-Talk** | Hold **`Ctrl + Space`** | Instantly opens microphone; release to stop streaming audio. |
| **Wake Word** | Say *"Hey Jarvis"* | Activates assistant from sleep (toggle in `CONTROLS` drawer). |
| **Instant PDF Jump** | Say *"Scroll to page 5"* | Instantly jumps to page 5 in Chrome PDF reader (<40ms). |
| **Relative Page Scroll** | Say *"Scroll down 3 pages"* | Smoothly scrolls down 3 pages using `PageDown`. |
| **Custom Theme** | Open `SETUP` $\rightarrow$ **Hue Wheel** | Live recolors entire HUD and 3D avatar wireframe. |
| **Voice Selection** | Open `SETUP` $\rightarrow$ **Voices** | Switch live between 5 native Gemini voices (*Puck, Charon, Kore, Fenrir, Aoede*). |
| **Undo Last Action** | Say *"Undo that"* | Reverses file operations, moves, and computer settings. |
| **Remote Dashboard** | Open `SETUP` $\rightarrow$ **Remote** | Scan QR code on your phone to open mobile control HUD. |

---

## 🗂️ Project Structure

```
Mark-LV/
├── main.py                     # Primary runtime engine — Gemini Live loop, audio stream & tool dispatch
├── ui.py                       # PyQt6 HUD — 3D avatar canvas, waveform visualizer & dual drawers
├── setup.py                    # OS-aware automated environment & dependency installer
├── requirements.txt            # Python dependencies with platform-specific markers
├── LICENSE                     # Creative Commons Attribution-NonCommercial 4.0 International
├── readme.md                   # Complete architectural documentation & user manual
├── .gitignore                  # Security-first ignore rules guarding keys, certs & caches
│
├── assets/                     # High-resolution architectural and live UI assets
│   ├── actual_ui_screenshot.png       # Live running HUD screenshot (Avatar, Waveform, Telemetry)
│   ├── actual_controls_drawer.png     # Live running HUD screenshot (Daily Controls Drawer)
│   ├── actual_setup_overlay.png       # Live running HUD screenshot (System Setup Drawer)
│   ├── jarvis_hero_banner.png         # Official high-resolution header banner
│   ├── jarvis_architecture_diagram.png# Full-duplex audio/vision & motor architecture diagram
│   ├── jarvis_chrome_control.png      # Autonomous Chrome & PDF navigation showcase
│   └── jarvis_hud_ui.png              # Holographic HUD interface conceptual layout
│
├── actions/                    # Bundled Computer Skills (Auto-discovered dynamically at boot)
│   ├── computer_control.py     # Native mouse, keyboard, Chrome tabs & <40ms PDF navigation
│   ├── computer_settings.py    # Volume, brightness, WiFi, power states & fast page scrolling
│   ├── browser_control.py      # Playwright browser automation, DOM scraping & web forms
│   ├── screen_processor.py     # Real-time screen capture (MSS), multi-monitor & vision grounding
│   ├── dev_agent.py            # Autonomous software engineer (architecture, code, test, deploy)
│   ├── code_helper.py          # Quick script generation, test runner & IDE workspace launcher
│   ├── smart_automation.py     # Multi-step reasoning planner with iterative visual loop feedback
│   ├── file_controller.py      # Local file manager, search & automated desktop/downloads cleanup
│   ├── file_processor.py       # Document parser & summarizer for PDFs, text & markdown
│   ├── system_monitor.py       # Live hardware telemetry collector (CPU, GPU, RAM, temps, disk)
│   ├── github_manager.py       # GitHub REST API integration (repos, PRs, issues, commits)
│   ├── open_app.py             # Desktop application launcher & cross-platform process focus
│   ├── desktop.py              # Window geometry management & virtual desktop workspace switcher
│   ├── web_search.py           # Dual-pipeline search (Gemini Grounding + DuckDuckGo fallback)
│   ├── youtube_video.py        # YouTube search, streaming playback & media control
│   ├── video_player.py         # In-HUD synchronized video playback with audio ducking
│   ├── weather_report.py       # Real-time weather forecasts, meteorological data & alerts
│   ├── flight_finder.py        # Live flight tracker, route search & arrival status
│   ├── reminder.py             # Natural language alarm scheduler & desktop notifications
│   ├── send_message.py         # Outbound messaging dispatcher (WhatsApp multi-tier, Telegram, Discord)
│   ├── workflow.py             # Multi-command chained workflows & custom macro sequences
│   ├── proactive.py            # Ambient proactive intelligence & contextual user prompts
│   ├── game_updater.py         # Game library update monitor & patch status verifier
│   └── background_monitor.py   # Asynchronous background observer for clipboard & system health
│
├── core/                       # Core Runtime Subsystems & AI Engines
│   ├── gemini.py               # 9-tier Model Ladder with intelligent timeout & quota backoff
│   ├── llm_client.py           # Universal LLM abstraction interface & REST fallback handler
│   ├── coder_engine.py         # Deep coding LLM pipeline for software generation & repairs
│   ├── prompt.txt              # System prompt, personality grounding & motor execution schema
│   ├── action_loader.py        # Dynamic auto-discovery & schema reflection for actions/
│   ├── plugin_loader.py        # Modular lifecycle manager for user-contributed plugins
│   ├── avatar.py               # Pure-software 3D wireframe avatar renderer powered by QPainter
│   ├── avatar_mesh.py          # 3D head geometry mathematics, projection & rotational matrices
│   ├── face_model.obj          # Canonical MediaPipe 468-vertex 3D facial topology geometry
│   ├── viseme.py               # Phonetic transcript analyzer producing ~50Hz mouth visemes
│   ├── echo.py                 # Real-time acoustic self-echo cancellation & bleed suppression
│   ├── wake_word.py            # Offline lightweight wake-word detector ("Hey Jarvis")
│   ├── hotkey.py               # Cross-platform global keyboard hook (Ctrl+Space push-to-talk)
│   ├── undo.py                 # Universal undo journal engine to revert files & settings
│   ├── confirm.py              # Hardware confirmation token gate protecting high-risk actions
│   ├── audio_devices.py        # Latency prober & device enumerator (DirectSound / MME)
│   ├── installer.py            # Runtime dependency verifier & dynamic module helper
│   ├── stt.py                  # Offline / online speech-to-text transcription fallback
│   └── tts.py                  # Text-to-speech synthesis & audio output playback stream
│
├── dashboard/                  # Mobile & Web Remote Companion Subsystem
│   ├── server.py               # Local HTTPS/WebSocket server with self-signed TLS & token auth
│   └── static/                 # Companion web interface frontend assets
│       ├── app.html            # Single-page responsive mobile control HUD & remote microphone
│       ├── login.html          # Secure PIN / password authentication gate
│       └── crypto-js.min.js    # Client-side cryptographic hashing & secure token verification
│
├── memory/                     # Memory, State & Configuration Management
│   ├── memory_manager.py       # Long-term episodic memory engine with keyword indexing
│   ├── config_manager.py       # Thread-safe atomic JSON configuration reader/writer
│   └── long_term.json          # Persistent recallable facts, preferences & project history
│
├── plugins/                    # Drop-in Extensible Plugin Ecosystem
│   ├── _template.py            # Boilerplate starter template for custom user plugins
│   ├── _whatsapp_core.py       # Core multi-tier WhatsApp driver (Protocol, Desktop, Web)
│   ├── whatsapp.py             # Dedicated WhatsApp plugin (compose, draft, send, contacts)
│   ├── doc_writer.py           # Technical documentation, LaTeX & Markdown generator plugin
│   └── pdf_tutor.py            # Interactive PDF reading, educational analyzer & quiz tutor
│
└── config/                     # Configuration Templates & Application Resources
    ├── api_keys.json.example   # Clean template for API keys (Gemini, GitHub, etc.)
    ├── jarvis.ico              # Native application icon
    └── certs/                  # Auto-generated self-signed TLS certificates for local HTTPS
```

### Subsystem Breakdown

| Subsystem | Primary Responsibility | Key Files |
|:---|:---|:---|
| **I/O & Speech Engine** | Full-duplex 16kHz audio capture, 24kHz playback, ~50Hz viseme calculation, self-echo cancellation. | `core/audio_devices.py`, `core/viseme.py`, `core/echo.py`, `core/wake_word.py` |
| **Cognitive Ladder** | 9-tier model fallback cascading across Gemini models with quota cooldowns and auto-resumption. | `core/gemini.py`, `core/llm_client.py`, `core/prompt.txt` |
| **3D Holographic HUD** | Pure-software 3D facial mesh rendering with zero GPU overhead, audio oscilloscope, telemetry gauges. | `ui.py`, `core/avatar.py`, `core/avatar_mesh.py`, `core/face_model.obj` |
| **Motor & Browser Engine** | Sub-50ms native mouse, keyboard, active Chrome tab interaction, instant PDF jumping, settings control. | `actions/computer_control.py`, `actions/computer_settings.py`, `actions/browser_control.py` |
| **Autonomous Dev Agent** | Multi-file codebase synthesis, unit test execution, and IDE workspace launching from voice commands. | `actions/dev_agent.py`, `actions/code_helper.py`, `core/coder_engine.py` |
| **Safety & Memory** | Universal undo journal, hardware confirmation gates, persistent local recallable memory. | `core/undo.py`, `core/confirm.py`, `memory/memory_manager.py` |
| **Remote Companion** | Encrypted mobile web dashboard accessible via QR code with self-signed TLS encryption. | `dashboard/server.py`, `dashboard/static/app.html` |

---

## 🔒 Security & Data Privacy

- **100% Local Execution:** All application logic, GUI rendering, memory stores, and computer control scripts execute locally on your machine.
- **Zero Account Tracking:** No telemetry, no background analytics, and no third-party servers.
- **Encrypted Local Storage:** API keys and local tokens are stored locally in `config/api_keys.json` (strictly ignored by `.gitignore`).
- **Physical Confirmation Gate:** Dangerous actions (rebooting, system shutdowns, and WiFi disconnection) cannot be autonomously confirmed by the AI—they require a physical click on the HUD confirmation banner.

---

## 🗺️ Version Roadmap

| Version | Milestone Features |
|:---|:---|
| **Mark LII** | Live theme customizer, audio device prober, recallable memory, undo engine. |
| **Mark LIII** | Offline "Hey Jarvis" wake word, Gemini 3.1 Flash Live migration, instant spoken acknowledgments. |
| **Mark LIV** | 3D Holographic avatar mesh, 50Hz viseme lip-sync, push-to-talk chord, self-echo guard. |
| **Mark LV** | **Current Release:** Native in-HUD video player, 9-tier model ladder, sub-50ms PDF jump, autonomous Chrome driver, split control drawers. |
| **Mark LVI+** | Full voice barge-in interrupt, local speech-to-text offline fallback, Obsidian vault syncing, home automation. |

---

## 👤 Developer & Community

Engineered with passion for personal AI autonomy by **Yash Surve**.

- 🌐 **GitHub Profile:** [@YashSurve2006](https://github.com/YashSurve2006)
- 📦 **Project Repository:** [https://github.com/YashSurve2006/Mark-LV](https://github.com/YashSurve2006/Mark-LV)
- 📧 **Email:** [yashsurve2019@gmail.com](mailto:yashsurve2019@gmail.com)

---

<div align="center">
  <b>⭐ Star the repository on GitHub to support the journey to Mark 100! ⭐</b>
</div>
