# Command Mode & Coding Module - Assistmint

**Version:** 1.0.0
**Created:** 2026-01-17
**Last Updated:** 2026-01-17

---

## Overview

The Command Mode system transforms Assistmint into a **multi-model voice-controlled AI partner** with specialized modules for different tasks. Each module can use its own LLM model optimized for its purpose.

### Core Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Model Manager | `core/models/manager.py` | Per-module model routing |
| Coding Module | `modules/coding/module.py` | Voice pair programming |
| Config | `~/.assistmint/config.yaml` | Model & module settings |
| Commands | `~/.assistmint/commands.txt` | Voice command aliases |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ASSISTMINT MEGA BRAIN                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   VOICE     │    │   MODEL     │    │   CONFIG    │         │
│  │   INPUT     │───▶│   MANAGER   │◀───│   YAML      │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                            │                                    │
│         ┌──────────────────┼──────────────────┐                │
│         ▼                  ▼                  ▼                │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │  Terminal   │    │   Coding    │    │    Chat     │         │
│  │  Module     │    │   Module    │    │   Module    │         │
│  │  (mistral)  │    │(qwen-coder) │    │  (qwen2.5)  │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Model Manager

### Location
`core/models/manager.py`

### Purpose
Routes LLM requests to the correct model based on which module is calling. Enables specialized models for different tasks.

### Key Features

- **Per-module model selection** - Each module gets its own LLM
- **Singleton pattern** - One manager instance across the app
- **YAML configuration** - Easy to edit `~/.assistmint/config.yaml`
- **Conversation history** - Maintains context per module
- **Ollama health check** - Verifies API availability

### API

```python
from core.models.manager import get_model_manager

mm = get_model_manager()

# Check if Ollama is running
if mm.is_ollama_available():
    # Ask a question using module-specific model
    response = mm.ask(
        question="Explain this code",
        module_name="coding",        # Uses qwen2.5-coder
        system_prompt="You are a coding assistant",
        temperature=0.3,
        max_tokens=2000
    )

# Get model for specific module
model = mm.get_model_for_module("coding")  # Returns "qwen2.5-coder:7b"

# List available models from Ollama
models = mm.list_available_models()

# Clear conversation history
mm.clear_history("coding")

# Get config value
verify = mm.get_config("terminal", "verify_with_llm", default=True)
```

### Configuration File

**Location:** `~/.assistmint/config.yaml`

```yaml
# Per-module model assignments
models:
  default: qwen2.5:7b          # Fallback model
  terminal: qwen2.5:7b         # Fast for command interpretation
  coding: qwen2.5-coder:7b     # Code-focused model
  chat: qwen2.5:7b             # General conversation

# Terminal module settings
terminal:
  verify_with_llm: true        # LLM explains before execution
  background_execution: false  # Run commands in background
  confirmation_required: true  # Require voice confirmation

# Coding module settings
coding:
  auto_backup: true            # Create .bak before editing
  max_context_lines: 500       # Max lines to include in context
  temperature: 0.3             # Lower for precise code

# General settings
session:
  enabled: true
  max_messages: 6
```

---

## 2. Coding Module (Voice Pair Programming)

### Location
`modules/coding/module.py`

### Purpose
Interactive voice-controlled pair programming. Load files, discuss code, generate solutions, and apply changes - all by voice.

### Activation Triggers

Say any of these to enter coding mode:
- **"Join me"**
- **"Code with me"**
- **"Help me code"**
- **"Pair program"**
- **"Coding mode"**
- **"Let's code"**
- **"Start coding"**

### Continuous Mode

Once activated, the coding module enters **continuous mode**:
- **No wake word needed** - Just speak naturally
- Stays active until you say "done" or "stop"
- Uses `qwen2.5-coder:7b` (or configured coding model)

### Voice Commands Inside Coding Mode

| Command | Action |
|---------|--------|
| `"open [file]"` | Load file into context |
| `"open main.py"` | Load main.py |
| `"explain this"` | Explain the loaded code |
| `"what does this do"` | Explain current code |
| `"write function [desc]"` | Generate code from description |
| `"fix this"` | Suggest fixes for issues |
| `"suggest fix"` | Same as above |
| `"apply"` / `"do it"` | Apply pending changes |
| `"show diff"` | Show pending changes as diff |
| `"cancel"` | Cancel pending changes |
| `"done"` / `"stop"` | Exit coding mode |

### Session Flow Example

```
You: "Hey Jarvis"
Jarvis: [wake word detected]

You: "Join me"
Jarvis: "Coding mode activated. What are you working on?"

╔══════════════════════════════════════════════════════════════════════╗
║  CODE MODE - Voice Pair Programming                                  ║
╠══════════════════════════════════════════════════════════════════════╣
║  Model: qwen2.5-coder:7b                                             ║
║  Commands: "open [file]", "explain", "fix", "apply", "done"          ║
╚══════════════════════════════════════════════════════════════════════╝

You: "Open main.py"
Jarvis: "Loaded main.py. 274 lines. What would you like to do?"

   1 #!/usr/bin/env python3
   2 """Main entry point for Assistmint."""
   3 import argparse
   4 ...
   ... (274 more lines)

You: "Add error handling to the voice loop"
Jarvis: "I'll wrap the voice loop in try-except to handle
         ConnectionError and TimeoutError. Here's the change:"

```python
try:
    result = process_voice(audio)
except ConnectionError:
    speak("Connection lost. Retrying...")
except TimeoutError:
    speak("Request timed out.")
```

Jarvis: "I've prepared changes. Say 'apply' to save, or 'show diff' to preview."

You: "Show diff"
Jarvis: [displays unified diff in terminal]

Diff for main.py:
--- main.py (original)
+++ main.py (modified)
@@ -180,6 +180,12 @@
-    result = process_voice(audio)
+    try:
+        result = process_voice(audio)
+    except ConnectionError:
+        speak("Connection lost. Retrying...")
+    except TimeoutError:
+        speak("Request timed out.")

You: "Apply"
Jarvis: "Changes applied. Backup saved."
        Changes saved to main.py
        Backup at main.py.bak

You: "Done"
Jarvis: "Ending coding session. Good work!"
```

### File Operations

**Loading Files:**
- Relative paths resolved from current working directory
- `~` expands to home directory
- File content added to LLM context
- Long files truncated to prevent context overflow

**Applying Changes:**
- Automatic `.bak` backup before any edit
- Shows diff before applying
- Confirmation required
- Updates loaded file context after apply

### Key Methods

| Method | Purpose |
|--------|---------|
| `execute()` | Entry point, starts coding loop |
| `_coding_loop()` | Main conversation loop |
| `_load_file(path)` | Load file into context |
| `_build_prompt(input)` | Build LLM prompt with file context |
| `_process_response(response)` | Extract code blocks, prepare changes |
| `_apply_pending_changes()` | Write changes to file |
| `_show_diff(old, new, file)` | Display unified diff |
| `_cleanup()` | Clear state on exit |

### Module Capabilities

```python
ModuleCapability.TEXT_INPUT |      # Accepts voice/text input
ModuleCapability.TEXT_OUTPUT |     # Returns spoken responses
ModuleCapability.EXTERNAL_API |    # Uses Ollama API
ModuleCapability.MULTI_TURN |      # Supports conversation
ModuleCapability.CONTINUOUS |      # No wake word during session
ModuleCapability.SYSTEM_ACCESS     # Can read/write files
```

---

## 3. Voice Command Aliases

### Location
`~/.assistmint/commands.txt`

### Format

```text
# Comments start with #
# Format: voice trigger | shell command

sync project | rsync -avz ~/project/ /backup/project/
update system | sudo apt update && sudo apt upgrade -y
docker cleanup | docker system prune -af
```

### How It Works

1. User says "sync project"
2. Terminal module matches trigger in commands.txt
3. Resolves to: `rsync -avz ~/project/ /backup/project/`
4. (Optional) LLM explains what command does
5. User confirms with "yes"
6. Command executes

### Adding Commands

**Via file edit:**
```bash
echo "my command | echo hello" >> ~/.assistmint/commands.txt
```

**Via voice (Terminal module):**
```
You: "Add command"
Jarvis: "What's the voice trigger?"
You: "sync documents"
Jarvis: "What command should it run?"
You: "rsync -avz ~/Documents/ /backup/Documents/"
Jarvis: "Added: 'sync documents' -> rsync command. Say it to test."
```

---

## 4. Hardware Considerations

### VRAM Management (8GB GPU)

The system is designed for **one model at a time**:

| Scenario | Model Loaded | VRAM Used |
|----------|--------------|-----------|
| Normal chat | qwen2.5:7b | ~4-5GB |
| Coding mode | qwen2.5-coder:7b | ~4-5GB |
| Terminal command | (uses loaded model) | No swap |

**Strategy:**
- Default model stays loaded
- Coding mode swaps to coder model
- Quick terminal commands use whatever's loaded
- Models unload when not needed

### CPU Fallback

If GPU unavailable, system runs on CPU:
- Slower responses (~10-30 seconds vs ~2-5 seconds)
- All features still work
- Whisper STT may use more CPU

---

## 5. Future Roadmap

### Phase 2: RAG Codebase System
- Embed entire codebases with ChromaDB
- Query code with natural language
- "Where is the login function?"
- "How does the render pipeline work?"

### Phase 3: Self-Builder Module
- Create new modules via voice
- "I need a weather module"
- Jarvis generates and registers the module

### Phase 4: Advanced Terminal
- LLM verification before dangerous commands
- Background execution with notifications
- Command history and suggestions

---

## 6. Troubleshooting

### Coding module not triggering

```bash
# Test trigger detection
python3 -c "
from modules.coding.module import CodingModule
cm = CodingModule()
print(cm.can_handle('join me'))  # Should be 0.95
"
```

### Model not switching

```bash
# Check config
cat ~/.assistmint/config.yaml

# Test model manager
python3 -c "
from core.models.manager import get_model_manager
mm = get_model_manager()
print('Coding model:', mm.get_model_for_module('coding'))
"
```

### Ollama not responding

```bash
# Check if running
curl http://localhost:11434/api/tags

# Restart Ollama
systemctl --user restart ollama
# or
ollama serve
```

### File not loading

```bash
# Check path resolution
python3 -c "
import os
path = 'main.py'
if not path.startswith('/'):
    path = os.path.join(os.getcwd(), path)
print('Resolved:', path)
print('Exists:', os.path.exists(path))
"
```

---

## 7. Changelog

### v1.0.0 (2026-01-17)
- Initial release
- Model Manager with per-module routing
- Coding Module with pair programming
- Config system (~/.assistmint/)
- Voice command aliases (commands.txt)

---

## Quick Reference

```bash
# Start assistant
python3 main_modular.py

# Enter coding mode
"Hey Jarvis" → "Join me"

# Load a file
"Open config.py"

# Get explanation
"Explain this function"

# Generate code
"Write a function to parse JSON"

# Apply changes
"Apply" or "Do it"

# Exit coding mode
"Done" or "Stop"
```

**Man + Machine = MEGA BRAIN**
