# Assistmint Voice Assistant - Complete Reference Guide

**Version:** 2.0
**Last Updated:** 2026-01-18
**Platform:** Ubuntu Linux 24.04+

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Wake Word & Basic Usage](#wake-word--basic-usage)
3. [Voice Commands Reference](#voice-commands-reference)
4. [Modules](#modules)
   - [Chat Module (LLM)](#chat-module-llm)
   - [Calendar Module](#calendar-module)
   - [Terminal Module](#terminal-module)
   - [Dictation Module](#dictation-module)
   - [Coding Module](#coding-module)
5. [Language Support](#language-support)
6. [VRAM Management](#vram-management)
7. [Configuration](#configuration)
8. [Custom Voice Commands](#custom-voice-commands)
9. [Troubleshooting](#troubleshooting)
10. [Architecture](#architecture)

---

## Quick Start

```bash
# Activate virtual environment
source venv/bin/activate

# Start voice assistant
python3 main_modular.py

# Start in text mode (no microphone)
python3 main_modular.py --type

# Or use the start script
./start_assistant.sh
```

---

## Wake Word & Basic Usage

### Wake Word
Say **"Hey Jarvis"** to activate the assistant. After activation, you have a few seconds to speak your command.

### Interrupting
While Jarvis is speaking, you can **speak loudly** to interrupt. This will:
1. Stop the current speech immediately
2. Unload the LLM from VRAM to free memory
3. Listen for your next command

### Audio Meter
While listening, you'll see a live audio meter:
```
[████████░░░░░░░░░░░░] -32.5dB | VRAM:45%
```
- The bar shows audio level
- dB shows decibel level
- VRAM shows GPU memory usage (updates every 2s)
- ⚠ appears if VRAM > 85%

---

## Voice Commands Reference

### Help & Session Management

| Command (EN) | Command (NL) | Action |
|--------------|--------------|--------|
| "help" | "help" | Show available commands |
| "clear session" | "vergeet alles" | Clear conversation history |
| "learn that" | "leer dat" | Teach STT correction |
| "show corrections" | "toon correcties" | List learned corrections |

### Time & Date

| Command (EN) | Command (NL) | Action |
|--------------|--------------|--------|
| "what time is it" | "hoe laat is het" | Current time |
| "what's the date" | "welke datum" | Current date |

### Language Switching

| Command (EN) | Command (NL) | Action |
|--------------|--------------|--------|
| "speak english" | "spreek engels" | Switch to English |
| "speak dutch" | "spreek nederlands" | Switch to Dutch |
| "auto language" | "automatisch" | Auto-detect language |

### System

| Command (EN) | Command (NL) | Action |
|--------------|--------------|--------|
| "go to sleep" | "ga slapen" | Pause listening |
| "open browser" | "open browser" | Open default browser |
| "open brave" | "open brave" | Open Brave browser |

---

## Modules

### Chat Module (LLM)

The default module - handles general questions and conversation using Ollama.

**Features:**
- Automatic model switching based on language
- Session memory (remembers conversation context)
- Per-model settings (temperature, tokens, etc.)

**Models:**
| Language | Model | VRAM |
|----------|-------|------|
| English | qwen2.5:3b | 1.9GB |
| Dutch | bramvanroy/fietje-2b-chat:q4_K_M | 1.7GB |

**Model Switching:**
When you speak Dutch, the assistant automatically:
1. Unloads the current model
2. Loads the Dutch model (fietje)
3. Responds in Dutch

This saves VRAM by never having both models loaded simultaneously.

---

### Calendar Module

Manage your Evolution calendar with voice commands.

#### Add Event
```
"Add meeting with Jan tomorrow at 3pm"
"Voeg toe aan agenda: vergadering morgen om half 4"
"Schedule dentist appointment on Friday at 10"
```

The assistant will:
1. Parse the event details
2. Ask for confirmation
3. Add to Evolution calendar

#### Check Events
```
"What's on my calendar?"
"Check my calendar for tomorrow"
"Bekijk mijn agenda voor volgende week"
```

#### Remove Event (NEW!)
```
"Remove event" / "Verwijder afspraak"
```

Interactive flow:
1. Jarvis: "Welke datum?"
2. You: "morgen"
3. Jarvis: "Er zijn 3 afspraken:
   1. Meeting met Jan om 10:00
   2. Lunch met Piet om 12:30
   3. Call met Bob om 15:00
   Welk nummer wil je verwijderen?"
4. You: "twee" or "2" or "alles"
5. Jarvis: "'Lunch met Piet' verwijderd."

**Trigger phrases (NL):**
- "verwijder afspraak"
- "wis afspraak"
- "annuleer afspraak"
- "afspraak verwijderen"

**Trigger phrases (EN):**
- "remove event"
- "delete event"
- "cancel event"
- "remove appointment"

#### Clear Calendar
```
"Clear my calendar for today"
"Wis alle afspraken van morgen"
```

---

### Terminal Module

Execute shell commands with voice.

#### Quick Commands
```
"show commands"
```
Shows numbered list of available commands from `~/.assistmint/commands.txt`

#### Execute by Number
```
"command 3" / "nummer 3" / "drie"
```
Executes command #3 from the list.

#### Execute by Name
```
"execute git status"
"run docker containers"
```

#### Background Execution
For long-running commands, say "background" or "achtergrond" when confirming:
```
Jarvis: "Run this command?"
You: "yes, background"
```

#### Custom Commands File
Edit `~/.assistmint/commands.txt`:
```
# Format: voice trigger | shell command
vramdump | bash ~/kill-gpu-python.sh
git status | git status
docker cleanup | docker system prune -f
syncvps | rsync -avz /source/ user@host:/dest/
```

---

### Dictation Module

Voice-to-text typing - types what you say directly into the active window.

#### Start Dictation
```
"dictate" / "dicteer" / "start typing"
```

#### While Dictating
- Speak naturally - text appears in your active window
- Say **"new line"** for Enter
- Say **"new paragraph"** for double Enter
- Say **"tab"** for Tab key

#### Stop Dictation
```
"stop dictating" / "stop met dicteren" / "done"
```

#### Spell Mode
For spelling out words letter by letter using NATO alphabet:
```
"spell mode" / "spelleer modus"
```
Then say: "alpha bravo charlie" → types "abc"

---

### Coding Module

Voice-controlled pair programming with AI.

#### Start Coding Mode
```
"join me" / "coding mode"
```

#### While in Coding Mode
- Wake word is disabled - continuous listening
- Talk naturally about your code
- AI assists with coding tasks

#### Exit Coding Mode
```
"done" / "klaar" / "exit"
```

See `README_COMMANDMODE.md` for full documentation.

---

## Language Support

### Supported Languages
- **English (en)** - Default
- **Dutch (nl)** - Full support

### Automatic Language Detection
The assistant detects which language you're speaking and:
1. Switches the LLM model (qwen for EN, fietje for NL)
2. Uses the appropriate TTS voice
3. Responds in the same language

### Manual Language Switching
```
"speak english" / "spreek engels"
"speak dutch" / "spreek nederlands"
```

### Dutch Time Conventions
The assistant understands Dutch time expressions:
- "half 3" = 14:30 (30 minutes BEFORE 3)
- "kwart over 2" = 14:15
- "kwart voor 3" = 14:45
- "3 uur" = 15:00

---

## VRAM Management

### Live VRAM Display
The audio meter shows current VRAM usage:
```
[████████░░░░░░░░░░░░] -32.5dB | VRAM:45%
[████████░░░░░░░░░░░░] -32.5dB |⚠VRAM:92%
```

### Automatic VRAM Optimization

1. **Model Switching**: When switching languages, the old model is unloaded before loading the new one.

2. **TTS Interrupt**: When you interrupt Jarvis while speaking, ALL loaded Ollama models are unloaded immediately.

3. **Model Sizes**:
   | Model | VRAM |
   |-------|------|
   | Whisper medium | ~2.5GB |
   | qwen2.5:3b | 1.9GB |
   | fietje q4_K_M | 1.7GB |

### Manual VRAM Cleanup
```bash
# Kill GPU Python processes
./kill-gpu-python.sh

# Or as voice command (add to commands.txt)
"vramdump" → bash ~/kill-gpu-python.sh
```

---

## Configuration

### Main Config: `config.py`

```python
# Models
DEFAULT_MODEL = "qwen2.5:3b"                      # English
DEFAULT_MODEL_NL = "bramvanroy/fietje-2b-chat:q4_K_M"  # Dutch
MODEL_AUTO_SWITCH = True  # Auto-switch based on language

# Audio
SILENCE_DURATION = 1.2      # Seconds of silence before processing
INTERRUPT_DB = -25          # dB threshold for TTS interrupt
TTS_GRACE_PERIOD = 0.8      # Seconds before interrupt detection starts

# Whisper STT
WHISPER_MODEL = "medium"    # tiny, base, small, medium, large
WHISPER_BEAM_SIZE = 4

# Terminal
TERMINAL_TIMEOUT = 600      # Max command runtime (seconds)
```

### Per-Model Settings: `config.py`

```python
MODEL_SETTINGS = {
    "qwen2.5:3b": {
        "max_tokens": 750,
        "temperature": 0.77,
        "top_p": 0.91,
    },
    "fietje": {
        "max_tokens": 500,
        "temperature": 0.5,  # Lower = less hallucination
    },
}
```

### Intent Configuration: `config_intents.py`

Maps voice2json intents to actions and defines keyword fallbacks.

---

## Custom Voice Commands

### File Location
`~/.assistmint/commands.txt`

### Format
```
# Comments start with #
voice trigger | shell command

# Multi-line commands use backslash
sync server | rsync -avz \
    --exclude 'node_modules/' \
    /source/ user@host:/dest/
```

### Examples
```
# System
system info | neofetch
disk space | df -h
memory | free -h

# Git
git status | git status
git pull | git pull

# Docker
docker containers | docker ps -a
docker cleanup | docker system prune -f

# Custom
vramdump | bash ~/kill-gpu-python.sh
restart audio | systemctl --user restart pipewire
```

### Using Commands
1. Say **"show commands"** to see numbered list
2. Say a number: **"3"** or **"drie"** or **"command 3"**
3. Confirm: **"yes"** (or **"yes background"** for long commands)

---

## Troubleshooting

### No Wake Word Detection
```bash
# Check microphone
arecord -l

# Test microphone
arecord -d 3 test.wav && aplay test.wav
```

### VRAM Issues / Out of Memory
```bash
# Check VRAM usage
nvidia-smi

# Kill GPU processes
./kill-gpu-python.sh --force

# Reduce model size
# In config.py, use smaller Whisper model:
WHISPER_MODEL = "small"  # instead of "medium"
```

### Ollama Not Responding
```bash
# Check if running
systemctl status ollama

# Restart
systemctl restart ollama

# Check loaded models
curl http://localhost:11434/api/ps
```

### Audio Crackling / Dropouts
```bash
# Restart audio pipeline
systemctl --user restart pipewire
```

### Calendar Not Working
```bash
# Check Evolution Data Server
systemctl --user status evolution-calendar-factory

# Test calendar access
python3 -c "from calendar_manager import check_calendar; check_calendar('today')"
```

---

## Architecture

```
assistmint/
├── main_modular.py          # Entry point
├── config.py                # Main configuration
├── config_intents.py        # Voice command mappings
├── calendar_manager.py      # Calendar operations
├── ollama.py                # LLM interface (legacy)
│
├── core/
│   ├── audio/
│   │   ├── stt.py           # Speech-to-Text (Whisper)
│   │   ├── tts.py           # Text-to-Speech (Piper)
│   │   └── device.py        # Audio device management
│   ├── nlp/
│   │   ├── router.py        # Intent recognition
│   │   └── filters.py       # Text processing
│   ├── modules/
│   │   └── base.py          # Base module class
│   └── resources/
│       └── manager.py       # GPU/VRAM management
│
├── modules/
│   ├── calendar/            # Calendar management
│   ├── chat/                # LLM conversations
│   ├── coding/              # Pair programming
│   ├── dictation/           # Voice typing
│   └── terminal/            # Shell commands
│
└── ~/.assistmint/
    ├── commands.txt         # Custom voice commands
    └── config.yaml          # User configuration
```

### Processing Flow

```
1. Audio Input
   └── Wake word detection (OpenWakeWord)
       └── "Hey Jarvis" detected

2. Speech-to-Text
   └── Whisper transcription
       └── "add meeting tomorrow at 3pm"

3. Intent Recognition
   └── voice2json (fast, offline)
       └── Fallback: keyword matching
           └── Intent: "add_calendar"

4. Module Routing
   └── CalendarModule.execute()
       └── Parse event details
       └── Add to Evolution

5. Response
   └── TTS output (Piper)
       └── "Added meeting to your calendar"
```

---

## Changelog

### 2026-01-18 (v2.0)
- **Calendar Remove**: Interactive event removal with numbered selection
- **VRAM Optimization**: Model unloading on switch and TTS interrupt
- **Live VRAM Display**: Real-time VRAM % in audio meter
- **Terminal Numbers**: Fixed number detection (no longer matches digits in command names)
- **Dutch Model**: Switched to q4_K_M quantization (1.7GB vs 5.6GB)

### Previous Updates
- Model auto-switching (EN/NL)
- Per-model LLM settings
- Terminal command background execution
- Audio pipeline warm-up (prevents first syllable cutoff)
- TTS interrupt detection
- Wake word integration

---

*Generated for Assistmint Voice Assistant*
