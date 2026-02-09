"""
Voice2json Intent Configuration
===============================

This file centralizes all voice2json intent mappings and system action definitions.
Edit this file to add/modify voice commands WITHOUT touching core Python code.

HOW THE VOICE COMMAND SYSTEM WORKS
----------------------------------

1. USER SPEAKS → Whisper STT transcribes to text
2. TEXT → voice2json matches against sentences.ini patterns
3. INTENT → Mapped to ACTION via INTENT_ACTIONS below
4. ACTION → Either:
   a) SYSTEM_ACTION: Executes immediately via xdotool (clipboard, browser, keys)
   b) MODULE_ACTION: Routes to appropriate module (calendar, dictation, chat)

PERFORMANCE
-----------
- voice2json: <1ms intent recognition (offline, no network)
- System actions: instant via xdotool
- Module actions: may involve Ollama LLM (~1-3s)

FILES INVOLVED
--------------
- ~/.local/share/voice2json/en-us_kaldi-rhasspy/sentences.ini  (English patterns)
- ~/.local/share/voice2json/nl_kaldi-rhasspy/sentences.ini     (Dutch patterns)
- config_intents.py (THIS FILE - action mappings)
- core/nlp/router.py (intent router - imports from here)
- core/actions.py (xdotool execution - imports from here)

ADDING A NEW VOICE COMMAND
--------------------------
1. Add pattern to sentences.ini:
   [MyIntent]
   my trigger phrase
   another way to say it

2. Retrain voice2json:
   docker run --rm -v "$HOME:$HOME" -e "HOME=$HOME" --user "$(id -u):$(id -g)" \\
       synesthesiam/voice2json --profile en-us_kaldi-rhasspy train-profile

3. Add mapping below:
   INTENT_ACTIONS["MyIntent"] = "my_action"

4. If system action, add to SYSTEM_ACTIONS and XDOTOOL_KEYS

5. Test:
   docker run ... voice2json --profile en-us_kaldi-rhasspy \\
       recognize-intent --text-input "my trigger phrase"
"""

# =============================================================================
# INTENT TO ACTION MAPPING
# =============================================================================
#
# Maps voice2json intent names → internal action identifiers.
#
# When voice2json recognizes "[IntentName]" from sentences.ini,
# it looks up the action here. The action string determines routing.
#
# Format: "IntentName": "action_name"
#
# The IntentName MUST match exactly what's in sentences.ini [brackets]
# The action_name is used to route to modules or execute system actions.

INTENT_ACTIONS = {
    # =========================================================================
    # HELP & SESSION MANAGEMENT
    # =========================================================================
    # These route to built-in help display or session management
    "Help": "help",                      # Show help menu
    "ClearSession": "clear_session",     # Clear conversation history
    "LearnCorrection": "learn_correction",  # Teach STT correction
    "ShowCorrections": "show_corrections",  # List learned corrections

    # =========================================================================
    # CALENDAR MODULE
    # =========================================================================
    # Routes to modules/calendar/module.py
    "AddCalendar": "add_calendar",       # "Add meeting tomorrow at 3pm"
    "CheckCalendar": "check_calendar",   # "What's on my calendar?"
    "ClearCalendar": "clear_calendar",   # "Clear my calendar"
    "RemoveCalendar": "remove_calendar", # "Remove the meeting"

    # =========================================================================
    # DICTATION MODULE
    # =========================================================================
    # Routes to modules/dictation/module.py
    "Dictate": "dictate",                # Enter dictation mode
    "StopDictate": "stop_dictate",       # Exit dictation mode
    "SpellMode": "spell_mode",           # Enter NATO alphabet spelling
    "StopSpellMode": "stop_spell_mode",  # Exit spell mode

    # =========================================================================
    # TERMINAL & CODING MODULES
    # =========================================================================
    # Routes to modules/terminal/ and modules/coding/
    "Terminal": "terminal",              # "Run command ls -la"
    "CodingMode": "coding_mode",         # "Join me" - pair programming

    # =========================================================================
    # LANGUAGE SWITCHING
    # =========================================================================
    # Switches TTS voice language
    "SpeakEnglish": "speak_english",     # Switch to English TTS
    "SpeakDutch": "speak_dutch",         # Switch to Dutch TTS
    "AutoLanguage": "auto_language",     # Auto-detect language

    # =========================================================================
    # SYSTEM - TIME & DATE
    # =========================================================================
    # Instant responses, no LLM needed
    "Sleep": "sleep",                    # "Go to sleep" - pause listening
    "WhatTime": "what_time",             # "What time is it?"
    "WhatDate": "what_date",             # "What's the date?"

    # =========================================================================
    # SYSTEM - VOLUME CONTROL
    # =========================================================================
    # Uses pactl to control PulseAudio
    "VolumeUp": "volume_up",             # +5% volume
    "VolumeDown": "volume_down",         # -5% volume
    "VolumeMute": "volume_mute",         # Toggle mute

    # =========================================================================
    # KEYBOARD NAVIGATION
    # =========================================================================
    # Direct xdotool key presses - instant, no TTS feedback (mostly)
    "PageUp": "page_up",                 # Page Up key
    "PageDown": "page_down",             # Page Down key
    "Home": "key_home",                  # Home key
    "End": "key_end",                    # End key
    "Backspace": "key_backspace",        # Backspace key
    "Enter": "key_enter",                # Enter/Return key
    "Tab": "key_tab",                    # Tab key
    "CapsLock": "caps_lock",             # Toggle Caps Lock

    # =========================================================================
    # BROWSER CONTROL
    # =========================================================================
    # xdotool keyboard shortcuts for browser navigation
    "OpenBrowser": "open_browser",       # xdg-open browser
    "BrowserBack": "browser_back",       # Alt+Left (history back)
    "BrowserForward": "browser_forward", # Alt+Right (history forward)
    "BrowserRefresh": "browser_refresh", # F5 (reload page)
    "BrowserNewTab": "browser_new_tab",  # Ctrl+T (new tab)
    "BrowserCloseTab": "browser_close_tab", # Ctrl+W (close tab)
    "ClearCache": "clear_cache",         # Ctrl+Shift+Del (clear data dialog)

    # =========================================================================
    # CLIPBOARD OPERATIONS
    # =========================================================================
    # Standard Ctrl+key shortcuts via xdotool
    "Copy": "clipboard_copy",            # Ctrl+C
    "Paste": "clipboard_paste",          # Ctrl+V
    "Cut": "clipboard_cut",              # Ctrl+X
    "SelectAll": "select_all",           # Ctrl+A
    "Undo": "undo",                       # Ctrl+Z
    "Redo": "redo",                       # Ctrl+Y

    # =========================================================================
    # CONFIRMATION INTENTS - DISABLED
    # =========================================================================
    # NOTE: Confirm/Deny are NOT global intents!
    # They interfere with normal conversation ("yes" triggers calendar confirm).
    # Confirmation is handled contextually within modules that need it.
    # "Confirm": "confirm",              # DISABLED - handled in module context
    # "Deny": "deny",                    # DISABLED - handled in module context
}


# =============================================================================
# SYSTEM ACTIONS
# =============================================================================
#
# Actions that execute IMMEDIATELY via xdotool, bypassing Ollama LLM.
# These provide instant response (<10ms) for simple commands.
#
# If an action is in this set, it's handled by core/actions.py
# If NOT in this set, it's routed to a module (may use Ollama)
#
# Add action names here (not intent names!) for instant execution.

SYSTEM_ACTIONS = {
    # Clipboard - Ctrl+key shortcuts
    "clipboard_copy",      # Ctrl+C
    "clipboard_paste",     # Ctrl+V
    "clipboard_cut",       # Ctrl+X
    "select_all",          # Ctrl+A
    "undo",                # Ctrl+Z
    "redo",                # Ctrl+Y

    # Browser - keyboard shortcuts
    "browser_back",        # Alt+Left
    "browser_forward",     # Alt+Right
    "browser_refresh",     # F5
    "browser_new_tab",     # Ctrl+T
    "browser_close_tab",   # Ctrl+W
    "clear_cache",         # Ctrl+Shift+Delete
    "open_browser",        # xdg-open

    # Keyboard navigation
    "page_up",             # Page_Up key
    "page_down",           # Page_Down key
    "key_home",            # Home key
    "key_end",             # End key
    "key_backspace",       # BackSpace key
    "key_enter",           # Return key
    "key_tab",             # Tab key
    "caps_lock",           # Caps_Lock key

    # Volume - pactl commands
    "volume_up",           # pactl +5%
    "volume_down",         # pactl -5%
    "volume_mute",         # pactl toggle mute

    # Time/Date - Python datetime
    "what_time",           # Return current time
    "what_date",           # Return current date

    # Sleep mode
    "sleep",               # Pause wake word listening
}


# =============================================================================
# KEYWORD FALLBACK PATTERNS
# =============================================================================
#
# Used when voice2json Docker container is NOT available.
# Simple keyword matching as backup - less accurate than voice2json.
#
# Format: "IntentName": (["keyword1", "keyword2", ...], "action")
#
# The keywords are matched with "keyword in text.lower()"
# First match wins, so order can matter for overlapping keywords.

KEYWORD_FALLBACK = {
    # -------------------------------------------------------------------------
    # Help & Session
    # -------------------------------------------------------------------------
    "Help": (
        ["help", "help me", "what can you do"],
        "help"
    ),
    "ClearSession": (
        ["clear session", "forget everything", "vergeet alles", "wis sessie"],
        "clear_session"
    ),
    "LearnCorrection": (
        ["learn that", "correct that", "fix that", "leer dat", "corrigeer dat"],
        "learn_correction"
    ),
    "ShowCorrections": (
        ["show corrections", "list corrections", "toon correcties"],
        "show_corrections"
    ),

    # -------------------------------------------------------------------------
    # Calendar
    # -------------------------------------------------------------------------
    "AddCalendar": (
        ["add to calendar", "schedule", "voeg toe aan agenda", "plan"],
        "add_calendar"
    ),
    "CheckCalendar": (
        ["check calendar", "check my calendar", "bekijk agenda", "what's on my calendar"],
        "check_calendar"
    ),
    "ClearCalendar": (
        ["clear calendar", "wis agenda", "delete all events"],
        "clear_calendar"
    ),
    "RemoveCalendar": (
        ["remove event", "delete event", "cancel event", "remove appointment",
         "verwijder afspraak", "wis afspraak", "annuleer afspraak", "afspraak verwijderen",
         "verwijder een afspraak", "afspraak wissen"],
        "remove_calendar"
    ),

    # -------------------------------------------------------------------------
    # Dictation
    # -------------------------------------------------------------------------
    "Dictate": (
        ["dictate", "dicteer", "start typing", "type this"],
        "dictate"
    ),
    "SpellMode": (
        ["spell mode", "spelmode", "spelling mode"],
        "spell_mode"
    ),
    "StopSpellMode": (
        ["stop spell mode", "stop spelmode", "normal mode"],
        "stop_spell_mode"
    ),

    # -------------------------------------------------------------------------
    # Terminal & Coding
    # -------------------------------------------------------------------------
    "Terminal": (
        ["run command", "terminal", "execute", "shell"],
        "terminal"
    ),
    "CodingMode": (
        ["coding mode", "join me", "pair programming", "programmeer modus"],
        "coding_mode"
    ),

    # -------------------------------------------------------------------------
    # Language Switching
    # -------------------------------------------------------------------------
    "SpeakEnglish": (
        ["speak english", "switch to english", "english"],
        "speak_english"
    ),
    "SpeakDutch": (
        ["speak dutch", "spreek nederlands", "dutch", "nederlands"],
        "speak_dutch"
    ),
    "AutoLanguage": (
        ["auto language", "automatisch", "auto detect"],
        "auto_language"
    ),

    # -------------------------------------------------------------------------
    # System
    # -------------------------------------------------------------------------
    "Sleep": (
        ["sleep", "slaap", "pause", "pauze"],
        "sleep"
    ),
    "WhatTime": (
        ["what time", "hoe laat", "current time"],
        "what_time"
    ),
    "WhatDate": (
        ["what date", "welke datum", "today's date"],
        "what_date"
    ),
    "VolumeUp": (
        ["volume up", "louder", "harder"],
        "volume_up"
    ),
    "VolumeDown": (
        ["volume down", "quieter", "zachter"],
        "volume_down"
    ),
    "VolumeMute": (
        ["mute", "dempen", "unmute"],
        "volume_mute"
    ),

    # -------------------------------------------------------------------------
    # Keyboard Navigation
    # -------------------------------------------------------------------------
    "PageUp": (
        ["page up", "scroll up", "pagina omhoog"],
        "page_up"
    ),
    "PageDown": (
        ["page down", "scroll down", "pagina omlaag"],
        "page_down"
    ),
    "Home": (
        ["home", "go home", "begin", "naar begin"],
        "key_home"
    ),
    "End": (
        ["go to end", "go end", "end key", "press end", "einde", "naar einde", "naar het einde"],
        "key_end"
    ),
    "Backspace": (
        ["backspace", "delete back", "wissen"],
        "key_backspace"
    ),
    "Enter": (
        ["enter", "new line", "nieuwe regel"],
        "key_enter"
    ),
    "Tab": (
        ["tab", "next field", "tabje"],
        "key_tab"
    ),
    "CapsLock": (
        ["caps lock", "toggle caps", "hoofdletters"],
        "caps_lock"
    ),

    # -------------------------------------------------------------------------
    # Browser Control
    # -------------------------------------------------------------------------
    "OpenBrowser": (
        ["open browser", "open firefox", "open chrome", "open brave", "brave browser", "start browser"],
        "open_browser"
    ),
    "BrowserBack": (
        ["page back", "go back", "previous page", "terug"],
        "browser_back"
    ),
    "BrowserForward": (
        ["page forward", "go forward", "next page", "vooruit"],
        "browser_forward"
    ),
    "BrowserRefresh": (
        ["refresh", "reload", "ververs", "herlaad"],
        "browser_refresh"
    ),
    "BrowserNewTab": (
        ["new tab", "open new tab", "nieuw tabblad"],
        "browser_new_tab"
    ),
    "BrowserCloseTab": (
        ["close tab", "close this tab", "sluit tabblad"],
        "browser_close_tab"
    ),
    "ClearCache": (
        ["clear cache", "clear cookies", "wis cache", "wis cookies"],
        "clear_cache"
    ),

    # -------------------------------------------------------------------------
    # Clipboard Operations
    # -------------------------------------------------------------------------
    "Copy": (
        ["copy", "copy that", "kopieer"],
        "clipboard_copy"
    ),
    "Paste": (
        ["paste", "paste that", "plak"],
        "clipboard_paste"
    ),
    "Cut": (
        ["cut", "cut that", "knip"],
        "clipboard_cut"
    ),
    "SelectAll": (
        ["select all", "selecteer alles"],
        "select_all"
    ),
    "Undo": (
        ["undo", "take back", "ongedaan maken"],
        "undo"
    ),
    "Redo": (
        ["redo", "opnieuw"],
        "redo"
    ),

    # -------------------------------------------------------------------------
    # Confirmation - DISABLED as global intents
    # -------------------------------------------------------------------------
    # NOTE: Confirm/Deny keywords would catch "yes"/"no" during normal chat.
    # Confirmation is handled contextually within modules (calendar, etc.)
    # "Confirm": (["yes", "ja", "okay", "confirm", "do it", "go ahead"], "confirm"),
    # "Deny": (["no", "nee", "cancel", "nevermind"], "deny"),
}


# =============================================================================
# XDOTOOL KEY MAPPINGS
# =============================================================================
#
# Maps action names → xdotool key sequences.
# Used by core/actions.py for keyboard simulation.
#
# Format: "action_name": "key_sequence"
#
# Key sequence syntax (xdotool):
# - Single key: "F5", "Return", "BackSpace"
# - Modifier+key: "ctrl+c", "alt+Left", "ctrl+shift+Delete"
# - Multiple keys: "ctrl+alt+t" (all pressed together)
#
# Common xdotool key names:
# - Modifiers: ctrl, alt, shift, super
# - Navigation: Left, Right, Up, Down, Home, End, Page_Up, Page_Down
# - Editing: BackSpace, Delete, Return, Tab
# - Function: F1-F12, Escape
# - Toggle: Caps_Lock, Num_Lock, Scroll_Lock

XDOTOOL_KEYS = {
    # Clipboard shortcuts (Ctrl+key)
    "clipboard_copy": "ctrl+c",
    "clipboard_paste": "ctrl+v",
    "clipboard_cut": "ctrl+x",
    "select_all": "ctrl+a",
    "undo": "ctrl+z",
    "redo": "ctrl+y",

    # Browser shortcuts
    "browser_back": "alt+Left",           # History back
    "browser_forward": "alt+Right",       # History forward
    "browser_refresh": "F5",              # Reload page
    "browser_new_tab": "ctrl+t",          # New tab
    "browser_close_tab": "ctrl+w",        # Close current tab
    "clear_cache": "ctrl+shift+Delete",   # Open clear data dialog

    # Navigation keys
    "page_up": "Page_Up",
    "page_down": "Page_Down",
    "key_home": "Home",
    "key_end": "End",
    "key_backspace": "BackSpace",
    "key_enter": "Return",
    "key_tab": "Tab",
    "caps_lock": "Caps_Lock",
}


# =============================================================================
# TTS RESPONSE MESSAGES
# =============================================================================
#
# Text-to-speech responses for system actions.
# Set to None for silent actions (like backspace, enter, tab).
#
# Format: "action_name": "Response text" or None
#
# Keep responses SHORT - they should be quick confirmations.
# For actions that are obvious (typing keys), silence is better.

ACTION_RESPONSES = {
    # Clipboard - brief confirmations
    "clipboard_copy": "Copied",
    "clipboard_paste": "Pasted",
    "clipboard_cut": "Cut",
    "select_all": "Selected all",
    "undo": "Undone",
    "redo": "Redone",

    # Browser - brief confirmations
    "browser_back": "Back",
    "browser_forward": "Forward",
    "browser_refresh": "Refreshed",
    "browser_new_tab": "New tab",
    "browser_close_tab": "Tab closed",
    "clear_cache": "Opening clear data dialog",
    "open_browser": "Opening browser",

    # Navigation - mostly silent, user sees the action
    "page_up": "Page up",
    "page_down": "Page down",
    "key_home": "Home",
    "key_end": "End",
    "key_backspace": None,   # Silent - user sees deletion
    "key_enter": None,       # Silent - user sees newline
    "key_tab": None,         # Silent - user sees tab
    "caps_lock": "Caps lock toggled",

    # Volume - brief confirmations
    "volume_up": "Volume up",
    "volume_down": "Volume down",
    "volume_mute": "Mute toggled",

    # Sleep
    "sleep": "Going to sleep",
}


# =============================================================================
# VOICE2JSON PROFILES
# =============================================================================
#
# Available voice2json language profiles.
# Located in ~/.local/share/voice2json/
#
# To add a new language:
# 1. Download profile: docker run synesthesiam/voice2json download-profile <profile>
# 2. Add entry here
# 3. Create sentences.ini with localized patterns

VOICE2JSON_PROFILES = {
    "en": "en-us_kaldi-rhasspy",   # English (US)
    "nl": "nl_kaldi-rhasspy",       # Dutch (Netherlands)
    # "de": "de_kaldi-rhasspy",     # German (uncomment if installed)
    # "fr": "fr_kaldi-rhasspy",     # French (uncomment if installed)
}
