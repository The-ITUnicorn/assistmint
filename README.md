# Assistmint - Local Voice Assistant for Linux

A local AI voice assistant for Ubuntu Linux 24.04+ with bilingual (EN/NL) support.

> **Full Documentation:** See [HELP.md](HELP.md) for complete reference guide with all voice commands, modules, and configuration options.

## Features

- **Speech-to-Text**: faster-whisper (GPU accelerated with CUDA)
- **Noise Reduction**: AI-powered noise suppression (noisereduce)
- **Intent Recognition**: voice2json via Docker (offline, fast command matching)
- **LLM Backend**: Ollama (local LLMs)
- **Text-to-Speech**: Piper TTS (fast, high-quality neural voices)
  - English: en_US-lessac-medium (female)
  - Dutch: nl_BE-nathalie-medium (Belgian Dutch, female)
- **Wake Word**: OpenWakeWord ("Hey Jarvis" default)

## Quick Controls

| Action | How | When |
|--------|-----|------|
| **Pause dictation (privacy)** | Say "sleep" / "slaap" | Someone walks in - mic silenced |
| **Resume dictation** | Say "Hey Jarvis" | Wake from sleep |
| **Interrupt TTS** | Speak loudly | Stop assistant mid-sentence |
| **Switch to English** | "Speak English" | Force English voice |
| **Switch to Dutch** | "Spreek Nederlands" | Force Dutch voice |
| **Auto language** | "Automatisch" | Auto-detect language |
| **Quit** | Type `quit` | In type mode |

## Requirements

- Ubuntu Linux 24.04+
- Python 3.10+
- CUDA 11.8+ (for GPU acceleration)
- Docker (for voice2json)
- Ollama running locally
- RTX GPU recommended (tested with RTX 3070)

## Installation

```bash
# Clone and setup
cd ~/Work/ai/llm
git clone <repo> assistmint
cd assistmint

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
sudo apt-get install sox xdotool xclip
pip install -r requirements.txt

# Download Piper voices
mkdir -p ~/.local/share/piper/voices
cd ~/.local/share/piper/voices
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/nl/nl_BE/nathalie/medium/nl_BE-nathalie-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/nl/nl_BE/nathalie/medium/nl_BE-nathalie-medium.onnx.json

# Add user to docker group (logout/login required)
sudo usermod -aG docker $USER

# Download voice2json profiles
docker run --rm -v "${HOME}:${HOME}" -e "HOME=${HOME}" --user "$(id -u):$(id -g)" \
    synesthesiam/voice2json --profile en-us_kaldi-rhasspy download-profile
docker run --rm -v "${HOME}:${HOME}" -e "HOME=${HOME}" --user "$(id -u):$(id -g)" \
    synesthesiam/voice2json --profile nl_kaldi-rhasspy download-profile

# Make scripts executable
chmod +x start_assistant.sh
```

## Google Calendar Setup (Optional)

Sync calendar events with your Google account - events show up on your phone!

```bash
# Install gcalcli
pip install gcalcli

# Authenticate with Google (one-time, opens browser)
gcalcli init

# Test it works
gcalcli list          # Should show your calendars
gcalcli agenda        # Should show upcoming events
```

**Config** (`config.py`):
```python
CALENDAR_BACKEND = "google"     # "google" = sync with Google, "local" = ~/.reminders file
CALENDAR_ID = "primary"         # Which Google Calendar to use
```

**How it works**:
- Say "Add to calendar" → Event syncs to Google Calendar
- Notifications appear on your phone automatically
- Check events: "What's on my calendar today?"

**To disable Google sync**: Set `CALENDAR_BACKEND = "local"` to use local `.reminders` file only.

## Usage

```bash
# Start voice assistant (modular version)
python3 main_modular.py

# Quick start with defaults
./start_assistant.sh

# Type mode for testing (no microphone)
python3 main_modular.py --type
```

### New in v2.2

- **Programming Mode**: Say "let's program" or "coding mode" to enter interactive programming session
  - Offers to open a terminal with `tail -f` on the code output file
  - Code from LLM responses auto-saved to `~/.assistmint/last_code.txt`
  - Say "save code" to save current code to clipboard-ready file
  - Say "write code" to save to timestamped file in `~/.assistmint/code/`
- **Improved Dictation**: Better punctuation handling - no more periods after single words, proper spacing between sentences
- **Session Memory**: 50-message rolling window for better conversation context (25 complete exchanges)
- **Ollama Health Checks**: Graceful timeout and fallback when Ollama is unavailable
- **Calendar Error Handling**: Spoken feedback when LLM extraction fails

### New in v2.0

- **Automatic Model Switching**: Switches between English (qwen2.5:3b) and Dutch (fietje) models based on language
- **VRAM Optimization**: Models unload when switching languages or when TTS is interrupted
- **Live VRAM Monitor**: Real-time GPU memory display in audio meter
- **Interactive Calendar Remove**: Numbered event selection for deletion
- **Terminal Commands**: Execute shell commands by number from customizable list

## Voice Commands

### Language Switching
| Command (EN) | Command (NL) | Action |
|--------------|--------------|--------|
| "Speak English" | - | Force English voice |
| "Switch to English" | - | Force English voice |
| - | "Spreek Nederlands" | Force Dutch voice |
| - | "Schakel naar Nederlands" | Force Dutch voice |
| "Auto language" | "Automatisch" | Auto-detect language |

### Calendar Management (syncs with Google Calendar!)
| Command (EN) | Command (NL) | Action |
|--------------|--------------|--------|
| "Add to calendar" | "Voeg toe aan agenda" | Add event (syncs to phone!) |
| "Check my calendar" | "Bekijk mijn agenda" | View events |
| "Remove event" | "Verwijder afspraak" | Delete event |
| "Clear my calendar" | "Wis mijn agenda" | Clear events |

Calendar asks "English or Dutch?" at the start - answer in either language to set the conversation language.

### Session & Learning
| Command (EN) | Command (NL) | Action |
|--------------|--------------|--------|
| "Clear session" | "Vergeet alles" | Reset conversation |
| "Learn that" | "Leer dat" | Correct misrecognition |
| "Show corrections" | "Toon correcties" | List learned corrections |

### Dictation Mode
| Command (EN) | Command (NL) | Action |
|--------------|--------------|--------|
| "Dictate" | "Dicteer" | Start dictation to active window |
| "Stop" | "Stop" / "Klaar" | End dictation |
| "Sleep" / "Pause" | "Slaap" / "Pauze" | Silence mic (privacy mode) |
| "Hey Jarvis" | "Hey Jarvis" | Resume from sleep |

### Terminal Commands
| Command (EN) | Command (NL) | Action |
|--------------|--------------|--------|
| "Run command" | "Voer commando uit" | Execute shell command |
| "Terminal" | "Terminal" | Execute shell command |

### Programming Mode (Voice Pair Programming!)
| Command (EN) | Command (NL) | Action |
|--------------|--------------|--------|
| "Let's program" | "Laten we programmeren" | Enter programming mode |
| "Coding mode" | "Codeermodus" | Enter programming mode |
| "Type" | "Typen" | Switch to keyboard input (flags, vars, commands) |
| "Save code" | "Bewaar code" | Save last code to clipboard file |
| "Write code" | "Schrijf code" | Save to timestamped file |

**How it works:**
1. Say "let's program" - Jarvis asks if you want to tail the code file
2. Say "yes" - Opens gnome-terminal with `tail -f ~/.assistmint/last_code.txt`
3. Ask programming questions - code auto-saves to the file as you talk
4. Say "type" to switch to keyboard for technical input (flags, vars, commands)
5. Watch code appear live in the terminal!

### Other
| Command | Action |
|---------|--------|
| "Help" / "Menu" | Show available commands |
| Just ask anything | Sends to Ollama LLM |

## Dictation Grammar

### Case (for words)
| Command | Result | Example |
|---------|--------|---------|
| "capital X" | X | "capital hello" → "HELLO" |
| "lowercase X" | x | "lowercase HELLO" → "hello" |
| "all caps X" | X | "all caps test" → "TEST" |

### Spell Mode (single letters)
| Command | Result |
|---------|--------|
| "capital A" | A |
| "lower A" / "kleine A" | a |
| "capital alpha" | A (NATO phonetic) |
| "letter alpha" | a (NATO phonetic) |

### NATO Phonetic Alphabet (+ alternatives)
```
A = Alpha / Albert       N = November / Nancy
B = Bravo / Boy / Beta   O = Oscar / Oliver
C = Charlie / Charles    P = Papa / Peter / Paul
D = Delta / David        Q = Quebec / Queen
E = Echo / Edward        R = Romeo / Robert / Roger
F = Foxtrot / Fox        S = Sierra / Sugar / Sam
G = Golf / George        T = Tango / Tom / Tommy
H = Hotel / Henry        U = Uniform / Uncle
I = India / Indigo       V = Victor / Victoria
J = Juliet / John        W = Whiskey / William
K = Kilo / King          X = Xray / X-ray
L = Lima / London        Y = Yankee / Yellow
M = Mike / Michael       Z = Zulu / Zebra
```

### Numbers
| Command (EN) | Command (NL) | Result |
|--------------|--------------|--------|
| "number 5" | "cijfer 5" | 5 |
| "digit five" | "cijfer vijf" | 5 |

### Punctuation
| Command (EN) | Command (NL) | Result |
|--------------|--------------|--------|
| "period" | "punt" | . |
| "comma" | "komma" | , |
| "question mark" | "vraagteken" | ? |
| "exclamation mark" | "uitroepteken" | ! |
| "colon" | "dubbele punt" | : |
| "semicolon" | "puntkomma" | ; |

### Keyboard Actions
| Command (EN) | Command (NL) | Action |
|--------------|--------------|--------|
| "backspace" | "wissen" | Delete last char |
| "delete" | "verwijderen" | Delete next char |
| "enter" | "nieuwe regel" | New line |
| "tab" | "tabje" | Tab |
| "space" | "spatie" | Space |
| "home" / "home key" | "begin" / "start" | Go to start of line |
| "end" / "end key" | "einde" / "eind" | Go to end of line |
| "5 backspaces" | "vijf backspaces" | Delete 5 chars |
| "10 tabs" | "tien tabs" | 10 tabs |

### Scroll Commands (Hands-free browsing!)
| Command (EN) | Command (NL) | Action |
|--------------|--------------|--------|
| "scroll up" | "omhoog scrollen" | Scroll up |
| "scroll down" | "naar beneden scrollen" | Scroll down |
| "page up" | - | Page up |
| "page down" | - | Page down |
| "5 scroll ups" | "vijf scroll ups" | Scroll up 5x |
| "15 page downs" | - | Page down 15x |

### Caps Lock & Inline Caps
| Command (EN) | Command (NL) | Action |
|--------------|--------------|--------|
| "toggle caps lock" | "toggle hoofdletters" | Toggle real Caps Lock (LED!) |
| "this is a test IN ALL CAPS" | - | Types: THIS IS A TEST |
| "dit is een test IN HOOFDLETTERS" | - | Types: DIT IS EEN TEST |
| "write in caps hello world" | "schrijf in caps hallo wereld" | Types: HELLO WORLD |

Inline caps triggers (customize in `config.py` → `INLINE_CAPS_TRIGGERS`):
- English: "in all caps", "in caps", "all caps", "write in caps"
- Dutch: "in hoofdletters", "in alle caps", "met hoofdletters"

### Spell Mode
| Command (EN) | Command (NL) | Action |
|--------------|--------------|--------|
| "spell mode" | "spelmode" | Enter spell mode (letters only) |
| "stop spell mode" | "stop spelmode" | Exit spell mode |

In spell mode:
- Single letters: A B C → abc
- NATO alphabet: alpha bravo charlie → abc
- Case modifiers: capital alpha → A
- Numbers: one two three → 123
- Keyboard actions still work: backspace, space, enter

### Symbols
| Command (EN) | Command (NL) | Result |
|--------------|--------------|--------|
| "at sign" | "apenstaartje" | @ |
| "hashtag" | - | # |
| "slash" | "schuine streep" | / |
| "backslash" | - | \ |
| "underscore" | "liggend streepje" | _ |
| "hyphen" / "dash" | "min" | - |
| "quote" | "aanhalingsteken" | " |
| "single quote" | "apostrof" | ' |
| "open parenthesis" | "haakje openen" | ( |
| "close parenthesis" | "haakje sluiten" | ) |
| "open bracket" | - | [ |
| "close bracket" | - | ] |

### Emojis
| Word (EN) | Word (NL) | Emoji |
|-----------|-----------|-------|
| house | huis | 🏠 |
| heart | hart | ❤️ |
| smile | lach | 😊 |
| sun | zon | ☀️ |
| star | ster | ⭐ |
| fire | vuur | 🔥 |
| dog | hond | 🐕 |
| cat | kat | 🐈 |
| coffee | koffie | ☕ |
| pizza | pizza | 🍕 |

100+ emojis supported including plurals. Disable with `DICTATE_EMOJIS = False` in config.py.

## Configuration (config.py)

### LLM Settings
```python
DEFAULT_MODEL = "qwen2.5:7b"     # Ollama model
MAX_TOKENS = 150                 # Response length
TEMPERATURE = 0.5                # Creativity (0.0-1.0)
FREQUENCY_PENALTY = 0.4          # Reduce repetition
PRESENCE_PENALTY = 0.4           # Encourage variety
```

### Audio Settings
```python
AUDIO_SAMPLE_RATE = 16000        # Mic monitoring (16kHz optimal)
SILENCE_DURATION = 1.2           # Seconds before recording stops
SILENCE_DURATION_EXT = 2.0       # Extended listen (longer questions)
NOISE_REDUCE = True              # AI noise suppression
```

### Whisper STT
```python
WHISPER_MODEL = "base"           # tiny/base/small/medium/large
WHISPER_BEAM_SIZE = 5            # Quality vs speed (1-10)
USE_GPU = True                   # GPU acceleration
```

### TTS Settings
```python
# English voice
TTS_SPEED_EN = 0.90              # English speed (0.5-1.5)
TTS_PITCH_EN = 0.95              # English pitch (0.8-1.2)
TTS_VOLUME_EN = 1.0              # English volume (0.5-2.0)

# Dutch voice
TTS_SPEED_NL = 0.83              # Dutch speed (0.5-1.5)
TTS_PITCH_NL = 0.90              # Dutch pitch (0.8-1.2)
TTS_VOLUME_NL = 1.0              # Dutch volume (0.5-2.0)

# Language detection
TTS_LANG_THRESHOLD = 0.15        # Auto-detect threshold
FORCE_LANGUAGE = None            # None/en/nl - force voice
```

### Calendar
```python
CALENDAR_BACKEND = "google"      # "google" = Google Calendar, "local" = ~/.reminders
CALENDAR_ID = "primary"          # Google Calendar ID
CALENDAR_ASK_LANGUAGE = True     # Ask "English or Dutch?" at start
CALENDAR_MAX_RETRIES = 2         # Retry if input not understood
```

### Wake Word
```python
WAKE_WORD = "hey_jarvis"         # hey_jarvis/alexa/hey_mycroft
WAKE_THRESHOLD = 0.8             # Sensitivity (0.5-0.9)
```

### Interrupt
```python
INTERRUPT_DB = -28               # Volume to interrupt TTS
INTERRUPT_DURATION = 0.3         # Sustained duration (seconds)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      ASSISTMINT                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Microphone → Noise Reduction → Whisper STT                 │
│                                    ↓                        │
│                          Voice2json Intent                  │
│                                    ↓                        │
│              ┌─────────────────────┴──────────────────┐     │
│              │                                        │     │
│         Intent Match                             No Match   │
│              │                                        │     │
│      Execute Action                          Send to Ollama │
│              │                                        │     │
│              └─────────────────────┬──────────────────┘     │
│                                    ↓                        │
│                    Piper TTS (Lessac/Nathalie)              │
│                                    ↓                        │
│                               Speaker                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## File Structure

```
assistmint/
├── main_modular.py         # Main entry point (v2.0)
├── config.py               # All configuration
├── config_intents.py       # Voice command mappings
├── calendar_manager.py     # Calendar functions
├── ollama.py               # LLM communication (legacy)
├── start_assistant.sh      # Quick start script
├── kill-gpu-python.sh      # VRAM cleanup script
├── HELP.md                 # Complete reference guide
├── README.md               # This file
│
├── core/                   # Core subsystems
│   ├── audio/              # STT (Whisper), TTS (Piper)
│   ├── nlp/                # Intent router, filters
│   ├── modules/            # Base module class
│   └── resources/          # GPU/VRAM management
│
├── modules/                # Feature modules
│   ├── calendar/           # Calendar management
│   ├── chat/               # LLM conversations
│   ├── coding/             # Pair programming mode
│   ├── dictation/          # Voice typing
│   └── terminal/           # Shell commands
│
└── ~/.assistmint/          # User config & data
    ├── commands.txt        # Custom voice commands
    ├── config.yaml         # User settings
    ├── last_code.txt       # Auto-saved code (tail -f this!)
    └── code/               # Saved code files (timestamped)
```

## Troubleshooting

### TTS sounds distorted
- Check `AUDIO_SAMPLE_RATE = 16000` in config.py
- Ensure Piper voices are downloaded correctly

### High CPU/GPU usage
- Reduce `WHISPER_MODEL` to "tiny" or "base"
- Set `NOISE_REDUCE = False` to disable noise reduction

### Wake word not detected
- Lower `WAKE_THRESHOLD` (e.g., 0.6)
- Ensure microphone is not muted

### Voice2json not working
- Check Docker is running: `docker ps`
- Verify profiles downloaded: `ls ~/.local/share/voice2json`

### Google Calendar not syncing
- Check gcalcli is installed: `which gcalcli`
- Re-authenticate: `gcalcli init`
- Test manually: `gcalcli add --title "Test" --when "tomorrow 3pm" --duration 60`
- Check config: `CALENDAR_BACKEND = "google"` in config.py

## GPU Optimization (RTX 20/30/40 Series)

### Tensor Core Acceleration

RTX GPUs have Tensor Cores for accelerated AI inference. Assistmint can use them for both STT and TTS.

| Component | Tensor Cores | Method |
|-----------|--------------|--------|
| Whisper STT | ✓ Active | float16 compute type (default) |
| Piper TTS | ✓ Ready | ONNX Runtime GPU + TensorRT |

### Enable GPU Acceleration

```bash
# Basic GPU support (CUDA)
pip install onnxruntime-gpu

# Maximum performance with TensorRT (optional)
pip install tensorrt
```

### TensorRT Benefits

When TensorRT is installed:
1. **First run**: Models compile to optimized TensorRT engines (~30s)
2. **Cached**: Engines stored in `~/.cache/onnx_tensorrt/`
3. **Subsequent runs**: Instant load, FP16 Tensor Core inference

### Verify GPU Usage

On startup, you should see:
```
[STT] Using CUDA: NVIDIA GeForce RTX 3070 (8GB)
[TTS] TensorRT available - Tensor Cores enabled
```

Or without TensorRT:
```
[TTS] CUDA available - using GPU
```

### GPU Memory Tips

- **RTX 3070 (8GB)**: Use `WHISPER_MODEL = "base"` or "small"
- **RTX 3080+ (10GB+)**: Can use `WHISPER_MODEL = "medium"`
- **Low VRAM**: Set `USE_GPU = False` in config.py for CPU fallback

### Config Options

```python
# config.py
USE_GPU = True                    # Enable GPU (with CPU fallback)
GPU_DEVICE_ID = 0                 # Specific GPU (None = auto-select best)
WHISPER_COMPUTE_TYPE = "float16"  # Tensor Core optimized (GPU)
```

## License

MIT License
