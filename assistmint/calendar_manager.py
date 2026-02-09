from datetime import datetime, timedelta
import re
import os
import subprocess
import shutil
import dateparser
import time

# --- Dependency injection for TTS and config ---
# Each project (jarvis1, jarvis2) registers its own speak function at startup.

_speak_func = None

# Config defaults (overridden by set_calendar_config)
CALENDAR_BACKEND = "evolution"
CALENDAR_ID = "primary"
CALENDAR_DEFAULT_DURATION = 60


def set_speak_func(func):
    """Register the TTS speak function. Call this at startup."""
    global _speak_func
    _speak_func = func


def set_calendar_config(backend=None, calendar_id=None, default_duration=None):
    """Override calendar config values. Call this at startup."""
    global CALENDAR_BACKEND, CALENDAR_ID, CALENDAR_DEFAULT_DURATION
    if backend is not None:
        CALENDAR_BACKEND = backend
    if calendar_id is not None:
        CALENDAR_ID = calendar_id
    if default_duration is not None:
        CALENDAR_DEFAULT_DURATION = default_duration


def _speak(text, **kwargs):
    """Internal speak wrapper - uses registered TTS or prints to console."""
    if _speak_func is not None:
        _speak_func(text, **kwargs)
    else:
        print(f"[calendar] {text}")

# Check if gcalcli is available
GCALCLI_AVAILABLE = shutil.which("gcalcli") is not None

# Check if Evolution Data Server is available
EVOLUTION_AVAILABLE = False
try:
    import gi
    gi.require_version('EDataServer', '1.2')
    gi.require_version('ECal', '2.0')
    gi.require_version('ICalGLib', '3.0')
    from gi.repository import EDataServer, ECal, ICalGLib, Gio
    EVOLUTION_AVAILABLE = True
except (ImportError, ValueError):
    pass

# Evolution calendar cache
_evolution_registry = None
_evolution_client = None


def _get_evolution_client():
    """Get or create Evolution calendar client."""
    global _evolution_registry, _evolution_client

    if not EVOLUTION_AVAILABLE:
        return None

    if _evolution_client is not None:
        return _evolution_client

    try:
        # Get the registry
        if _evolution_registry is None:
            _evolution_registry = EDataServer.SourceRegistry.new_sync(None)

        # Find the calendar source
        sources = _evolution_registry.list_sources(EDataServer.SOURCE_EXTENSION_CALENDAR)

        target_source = None
        for source in sources:
            # Match by CALENDAR_ID (can be uid, display name, or partial match)
            uid = source.get_uid()
            name = source.get_display_name()
            if CALENDAR_ID in [uid, name, "primary"]:
                target_source = source
                break
            # Also match Google calendar by email
            if "@gmail.com" in CALENDAR_ID and CALENDAR_ID in name:
                target_source = source
                break
            # Default to first Google calendar or "Persoonlijk"
            if target_source is None:
                if "@gmail.com" in name or name == "Persoonlijk":
                    target_source = source

        if target_source is None:
            print("[EVOLUTION] No suitable calendar found")
            return None

        print(f"[EVOLUTION] Using calendar: {target_source.get_display_name()}")

        # Create calendar client
        _evolution_client = ECal.Client.connect_sync(
            target_source,
            ECal.ClientSourceType.EVENTS,
            30,  # timeout in seconds
            None
        )

        return _evolution_client

    except Exception as e:
        print(f"[EVOLUTION] Error connecting: {e}")
        return None



# Word to number mapping for date parsing
WORD_TO_NUM = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
    "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
    "eighteen": "18", "nineteen": "19", "twenty": "20", "thirty": "30",
    "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70",
    "eighty": "80", "ninety": "90",
    "first": "1", "second": "2", "third": "3", "fourth": "4", "fifth": "5",
    "sixth": "6", "seventh": "7", "eighth": "8", "ninth": "9", "tenth": "10",
    "eleventh": "11", "twelfth": "12", "thirteenth": "13", "fourteenth": "14",
    "fifteenth": "15", "sixteenth": "16", "seventeenth": "17", "eighteenth": "18",
    "nineteenth": "19", "twentieth": "20", "thirtieth": "30", "thirty first": "31",
    # Add these base ordinals for tens
    "fortieth": "40", "fiftieth": "50", "sixtieth": "60", "seventieth": "70",
    "eightieth": "80", "ninetieth": "90",
}


def words_to_numbers(text):
    """Convert spoken number words to digits in a string.

    Examples:
        "august twenty nine" -> "august 29"
        "the fifteenth of march" -> "the 15 of march"
        "twenty first" -> "21"
    """
    if not text:
        return text

    text = text.lower().strip()

    # Handle compound numbers like "twenty nine" -> "29"
    compound_patterns = [
        (r'\btwenty[- ]?one\b', '21'), (r'\btwenty[- ]?two\b', '22'),
        (r'\btwenty[- ]?three\b', '23'), (r'\btwenty[- ]?four\b', '24'),
        (r'\btwenty[- ]?five\b', '25'), (r'\btwenty[- ]?six\b', '26'),
        (r'\btwenty[- ]?seven\b', '27'), (r'\btwenty[- ]?eight\b', '28'),
        (r'\btwenty[- ]?nine\b', '29'),
        (r'\bthirty[- ]?one\b', '31'),
    ]

    for pattern, replacement in compound_patterns:
        text = re.sub(pattern, replacement, text)

    # Handle ordinal compounds like "twenty first" -> "21"
    ordinal_compounds = [
        (r'\btwenty[- ]?first\b', '21'), (r'\btwenty[- ]?second\b', '22'),
        (r'\btwenty[- ]?third\b', '23'), (r'\btwenty[- ]?fourth\b', '24'),
        (r'\btwenty[- ]?fifth\b', '25'), (r'\btwenty[- ]?sixth\b', '26'),
        (r'\btwenty[- ]?seventh\b', '27'), (r'\btwenty[- ]?eighth\b', '28'),
        (r'\btwenty[- ]?ninth\b', '29'),
        (r'\bthirty[- ]?first\b', '31'),
    ]

    for pattern, replacement in ordinal_compounds:
        text = re.sub(pattern, replacement, text)

    # Replace simple number words
    for word, num in WORD_TO_NUM.items():
        text = re.sub(r'\b' + word + r'\b', num, text)

    return text


# Helper function to parse ordinal numbers up to 1 billion
def parse_ordinal_to_number(text):
    """Convert ordinal text to number (e.g., 'twenty first' -> 21)"""

    # First check if it's already in the dictionary
    if text in WORD_TO_NUM:
        return int(WORD_TO_NUM[text])

    # Split into words
    words = text.lower().split()

    # Handle "thousand", "million", "billion" cases
    large_numbers = {
        "thousand": 1000,
        "million": 1000000,
        "billion": 1000000000
    }

    # Handle simple compound ordinals (like "thirty first", "forty second")
    if len(words) == 2:
        # Check if it's a tens + ones ordinal combination
        tens_words = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

        if words[0] in tens_words:
            # Get tens value (remove "ty" ending for lookup)
            tens_key = words[0]
            if tens_key.endswith("ty"):
                base_tens = tens_key[:-2] + "y" if tens_key == "eighty" else tens_key[:-1]
                base_tens = base_tens.replace("twent", "twenty").replace("thirt", "thirty")
            else:
                base_tens = tens_key

            # Look up tens value from cardinal
            if base_tens in WORD_TO_NUM:
                tens_value = int(WORD_TO_NUM[base_tens])
            elif tens_key in WORD_TO_NUM:
                tens_value = int(WORD_TO_NUM[tens_key])
            else:
                return None

            # Get ones value from ordinal
            ones_ordinal = words[1]
            if ones_ordinal in WORD_TO_NUM:
                ones_value = int(WORD_TO_NUM[ones_ordinal])
                return tens_value + ones_value

    # For more complex cases (hundreds, thousands, etc.)
    # We'll implement a full parser
    return parse_complex_ordinal(words)

def parse_complex_ordinal(words):
    """Parse complex ordinal expressions"""
    total = 0
    current = 0

    # Mapping for ones ordinals (remove "th", "st", "nd", "rd" if present)
    ones_map = {
        "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
        "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9
    }

    # Mapping for tens ordinals
    tens_map = {
        "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13,
        "fourteenth": 14, "fifteenth": 15, "sixteenth": 16,
        "seventeenth": 17, "eighteenth": 18, "nineteenth": 19,
        "twentieth": 20, "thirtieth": 30, "fortieth": 40, "fiftieth": 50,
        "sixtieth": 60, "seventieth": 70, "eightieth": 80, "ninetieth": 90
    }

    # Cardinal mappings for reference
    cardinals = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
        "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
        "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
        "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
        "ninety": 90, "hundred": 100, "thousand": 1000,
        "million": 1000000, "billion": 1000000000
    }

    i = 0
    while i < len(words):
        word = words[i]

        # Check if it's a direct ordinal
        if word in ones_map:
            current += ones_map[word]
            i += 1
        elif word in tens_map:
            current += tens_map[word]
            i += 1
        # Check if it's a cardinal number
        elif word in cardinals:
            value = cardinals[word]

            # Handle multipliers
            if i + 1 < len(words):
                next_word = words[i + 1]
                if next_word in ["hundred", "thousand", "million", "billion"]:
                    current += value * cardinals[next_word]
                    i += 2
                    continue
                elif next_word in ["and", "&"]:
                    i += 1
                    continue

            current += value
            i += 1
        elif word == "and":
            i += 1
            continue
        elif word in ["hundred", "thousand", "million", "billion"]:
            # Handle cases where the multiplier is specified without a number before it
            if current == 0:
                current = 1
            current *= cardinals[word]
            i += 1
        else:
            # Unknown word
            return None

        # Check for ordinal suffix in the last word
        if i >= len(words) and current > 0:
            # Remove ordinal suffixes if present in the original text
            return current

    return total if total > 0 else current

# Usage in your date parsing:
def parse_date_with_ordinals(date_text):
    """Example function showing how to use the ordinal parser"""

    # First try direct lookup
    if date_text in WORD_TO_NUM:
        return WORD_TO_NUM[date_text]

    # Try parsing as ordinal
    result = parse_ordinal_to_number(date_text)
    if result is not None:
        return str(result)

    # Fallback or error handling
    return None

def parse_event(line):
    time_pattern = r'AT (\d{1,2}:\d{2})'
    time_match = re.search(time_pattern, line)

    if time_match:
        start_time = time_match.group(1)
        start_time_obj = datetime.strptime(start_time, "%H:%M")

        if start_time_obj.minute == 0:
            formatted_time = start_time_obj.strftime('%I').lstrip('0')
        else:
            formatted_time = start_time_obj.strftime('%I:%M').lstrip('0').replace(':00', '').replace(':', ' ')

        if "AM" in start_time_obj.strftime('%p'):
            formatted_time += " in the morning"
        elif "PM" in start_time_obj.strftime('%p'):
            hour = start_time_obj.hour
            if 12 <= hour < 17:
                formatted_time += " in the afternoon"
            else:
                formatted_time += " in the evening"

        event_description = line.split('MSG')[-1].strip()
        return (start_time_obj, f"{event_description} at {formatted_time}")

    return (None, line.split('MSG')[-1].strip())

def parse_time(time_str, silent=False):
    """Parses time in natural language or numeric format and converts to 'H:MM AM/PM' format.

    Args:
        time_str: Time string to parse
        silent: If True, don't speak error messages (for validation use)
    """
    original_str = time_str
    time_str = time_str.lower().strip()

    # Dutch number words mapping
    dutch_nums = {
        "een": "1", "één": "1", "twee": "2", "drie": "3", "vier": "4", "vijf": "5",
        "zes": "6", "zeven": "7", "acht": "8", "negen": "9", "tien": "10",
        "elf": "11", "twaalf": "12"
    }

    # Handle Dutch time patterns FIRST (before normalizing "uur")
    # "half X" in Dutch = (X-1):30 (half 3 = 2:30, half 12 = 11:30)
    half_match = re.match(r'^half\s+(\w+)$', time_str)
    if half_match:
        hour_word = half_match.group(1)
        hour_str = dutch_nums.get(hour_word, hour_word)
        try:
            hour = int(hour_str)
            # Dutch "half 3" means 2:30 (half hour BEFORE 3)
            hour = hour - 1 if hour > 1 else 12
            period = "pm" if hour >= 1 and hour <= 6 else "am"
            if hour >= 7 and hour <= 11:
                period = "am"
            return f"{hour}:30 {period.upper()}"
        except ValueError:
            pass

    # "kwart over X" = X:15
    kwart_over_match = re.match(r'^kwart\s+over\s+(\w+)$', time_str)
    if kwart_over_match:
        hour_word = kwart_over_match.group(1)
        hour_str = dutch_nums.get(hour_word, hour_word)
        try:
            hour = int(hour_str)
            period = "pm" if hour >= 1 and hour <= 6 else "am"
            if hour >= 7 and hour <= 11:
                period = "am"
            return f"{hour}:15 {period.upper()}"
        except ValueError:
            pass

    # "kwart voor X" = (X-1):45
    kwart_voor_match = re.match(r'^kwart\s+voor\s+(\w+)$', time_str)
    if kwart_voor_match:
        hour_word = kwart_voor_match.group(1)
        hour_str = dutch_nums.get(hour_word, hour_word)
        try:
            hour = int(hour_str)
            hour = hour - 1 if hour > 1 else 12
            period = "pm" if hour >= 1 and hour <= 6 else "am"
            if hour >= 7 and hour <= 11:
                period = "am"
            return f"{hour}:45 {period.upper()}"
        except ValueError:
            pass

    # "X uur" pattern (Dutch for "X o'clock")
    uur_match = re.match(r'^(\w+)\s*uur$', time_str)
    if uur_match:
        hour_word = uur_match.group(1)
        hour_str = dutch_nums.get(hour_word, hour_word)
        try:
            hour = int(hour_str)
            # Guess AM/PM based on hour
            if hour > 12:
                hour -= 12
                period = "pm"
            elif hour >= 7 and hour <= 11:
                period = "am"
            else:
                period = "pm"
            return f"{hour}:00 {period.upper()}"
        except ValueError:
            pass

    # Normalize A.M./P.M. variations to am/pm
    time_str = re.sub(r'a\.?m\.?', 'am', time_str)
    time_str = re.sub(r'p\.?m\.?', 'pm', time_str)
    # Remove "hours" / "hour" / "uur" noise
    time_str = re.sub(r'\s*(hours?|uur)\s*', ':', time_str)
    # Clean up multiple colons or leading colon
    time_str = re.sub(r':+', ':', time_str).strip(':')

    # Handle numeric formats first (e.g., "1130", "11:30", "1130 am")
    numeric_match = re.match(r'^(\d{1,2}):?(\d{2})?\s*(am|pm)?$', time_str)
    if numeric_match:
        hour = int(numeric_match.group(1))
        minutes = numeric_match.group(2) or "00"
        period = numeric_match.group(3)

        # If no period specified, guess based on hour
        if not period:
            if hour >= 7 and hour <= 11:
                period = "am"
            else:
                period = "pm"
            # Handle 24h format
            if hour > 12:
                hour -= 12
                period = "pm"

        return f"{hour}:{minutes} {period.upper()}"

    # Mapping of number words to digits for both hours and minutes (English + Dutch)
    num_words = {
        # English
        "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
        "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
        "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14", "fifteen": "15",
        "sixteen": "16", "seventeen": "17", "eighteen": "18", "nineteen": "19", "twenty": "20",
        "twenty-one": "21", "twenty-two": "22", "twenty-three": "23", "twenty-four": "24",
        "twenty-five": "25", "twenty-six": "26", "twenty-seven": "27", "twenty-eight": "28",
        "twenty-nine": "29", "thirty": "30", "thirty-one": "31", "thirty-two": "32",
        "thirty-three": "33", "thirty-four": "34", "thirty-five": "35", "thirty-six": "36",
        "thirty-seven": "37", "thirty-eight": "38", "thirty-nine": "39", "forty": "40",
        "forty-one": "41", "forty-two": "42", "forty-three": "43", "forty-four": "44",
        "forty-five": "45", "forty-six": "46", "forty-seven": "47", "forty-eight": "48",
        "forty-nine": "49", "fifty": "50", "fifty-one": "51", "fifty-two": "52",
        "fifty-three": "53", "fifty-four": "54", "fifty-five": "55", "fifty-six": "56",
        "fifty-seven": "57", "fifty-eight": "58", "fifty-nine": "59",
        # Dutch
        "een": "1", "één": "1", "twee": "2", "drie": "3", "vier": "4", "vijf": "5",
        "zes": "6", "zeven": "7", "acht": "8", "negen": "9", "tien": "10",
        "elf": "11", "twaalf": "12", "dertien": "13", "veertien": "14", "vijftien": "15",
        "zestien": "16", "zeventien": "17", "achttien": "18", "negentien": "19", "twintig": "20",
    }

    try:
        # Normalize input by converting to lowercase and stripping extra spaces
        time_str = time_str.lower().strip()

        # Replace words with digits if necessary
        for word, digit in num_words.items():
            time_str = time_str.replace(word, digit)

        # Handle cases where there's no space between the number and 'am/pm'
        time_str = re.sub(r'(\d)(am|pm)', r'\1 \2', time_str)

        # Remove potential words like "o'clock" or extra spaces
        time_str = time_str.replace("o'clock", "").replace("oclock", "").strip()

        # Split the string into parts (e.g., "three thirty pm" -> ["3", "30", "pm"])
        time_parts = time_str.split()

        if len(time_parts) == 2:  # e.g., "seven am", "five pm"
            hour = time_parts[0]
            period = time_parts[1]
            minutes = "00"
        elif len(time_parts) == 3:  # e.g., "three thirty pm"
            hour = time_parts[0]
            minutes = time_parts[1]
            period = time_parts[2]
        else:
            if not silent:
                _speak(f"Sorry, I couldn't understand the time {time_str}.")
            return None

        # Validate period is AM or PM
        period = period.lower().strip('.')
        if period not in ["am", "pm"]:
            if not silent:
                _speak(f"Please specify AM or PM.")
            return None

        # Construct the final time string in "H:MM AM/PM" format
        formatted_time = f"{hour}:{minutes} {period.upper()}"
        return formatted_time
    except ValueError:
        if not silent:
            _speak(f"Sorry, I couldn't understand the time {time_str}.")
        return None

def parse_date(date_str, silent=False, lang=None):
    """Parses natural language dates like 'today', 'tomorrow', 'this Friday', or 'August 29'.

    Args:
        date_str: Date string to parse
        silent: If True, don't speak error messages (for validation use)
        lang: Language hint ('nl' or 'en') - if None, tries to detect from TTS setting
    """
    now = datetime.now()

    # Get language from TTS setting if not specified
    if lang is None:
        try:
            from core.audio.tts import get_language
            lang = get_language()
        except ImportError:
            lang = None

    # Convert spoken words to numbers first
    converted = words_to_numbers(date_str)
    date_lower = converted.lower().strip()
    print(f"[DATE] '{date_str}' -> '{converted}' (lang={lang})")

    # === DIRECT HANDLING for common Dutch/English dates ===
    # Handle these BEFORE dateparser to avoid issues

    # Today / Vandaag
    if date_lower in ["today", "vandaag", "nu", "now"]:
        return now

    # Tomorrow / Morgen
    if date_lower in ["tomorrow", "morgen", "morgn"]:
        return now + timedelta(days=1)

    # Day after tomorrow / Overmorgen
    if date_lower in ["day after tomorrow", "overmorgen", "over morgen"]:
        return now + timedelta(days=2)

    # Yesterday / Gisteren
    if date_lower in ["yesterday", "gisteren"]:
        return now - timedelta(days=1)

    # Next week (without specific day) = same day next week
    if date_lower in ["next week", "volgende week"]:
        return now + timedelta(days=7)

    # This week (without specific day) = today
    if date_lower in ["this week", "deze week"]:
        return now

    # === WEEK NUMBER support (week 4, week 5, etc.) ===
    week_match = re.match(r'^week\s*(\d+)$', date_lower)
    if week_match:
        week_num = int(week_match.group(1))
        # Get first day (Monday) of that week number in current year
        year = now.year
        # If the week is in the past, assume next year
        first_day_of_week = datetime.strptime(f'{year}-W{week_num:02d}-1', '%Y-W%W-%w')
        if first_day_of_week < now - timedelta(days=7):  # More than a week in the past
            first_day_of_week = datetime.strptime(f'{year + 1}-W{week_num:02d}-1', '%Y-W%W-%w')
        print(f"[DATE] Week {week_num} -> {first_day_of_week.strftime('%Y-%m-%d')}")
        return first_day_of_week

    # Configure dateparser with language priority
    # Dutch first if NL mode, otherwise English first
    if lang == "nl":
        languages = ['nl', 'en']
    else:
        languages = ['en', 'nl']

    # Also handle Dutch date words that dateparser might miss
    dutch_date_map = {
        "vandaag": "today", "morgen": "tomorrow", "overmorgen": "day after tomorrow",
        "gisteren": "yesterday", "volgende week": "next week", "deze week": "this week",
        "maandag": "monday", "dinsdag": "tuesday", "woensdag": "wednesday",
        "donderdag": "thursday", "vrijdag": "friday", "zaterdag": "saturday", "zondag": "sunday",
        "januari": "january", "februari": "february", "maart": "march", "april": "april",
        "mei": "may", "juni": "june", "juli": "july", "augustus": "august",
        "september": "september", "oktober": "october", "november": "november", "december": "december"
    }

    # Pre-convert Dutch words to English for better dateparser support
    converted_lower = date_lower
    for nl, en in dutch_date_map.items():
        converted_lower = converted_lower.replace(nl, en)

    parsed_date = dateparser.parse(converted_lower, languages=languages)

    if parsed_date is None:
        if not silent:
            _speak(f"Sorry, I couldn't understand the date {date_str}.")
        return None

    # Handle cases where the year is not specified
    if parsed_date.year == now.year and parsed_date < now:
        parsed_date = parsed_date.replace(year=now.year + 1)

    return parsed_date

def add_event_to_calendar(event_name, start_time, end_time, date="today"):
    """Add an event to calendar (Evolution, Google Calendar, or local .reminders)."""

    event_date = parse_date(date)
    if event_date is None:
        return

    start_time_parsed = parse_time(start_time)
    end_time_parsed = parse_time(end_time)
    if not start_time_parsed or not end_time_parsed:
        return

    # Use Evolution if configured and available
    if CALENDAR_BACKEND == "evolution":
        if not EVOLUTION_AVAILABLE:
            _speak("Evolution calendar is not available. Please install gir1.2-ecal-2.0.")
            return
        _add_event_evolution(event_name, event_date, start_time_parsed, end_time_parsed)
    # Use Google Calendar if configured and available
    elif CALENDAR_BACKEND == "google":
        if not GCALCLI_AVAILABLE:
            _speak("Google Calendar is not set up. Please install gcalcli first.")
            print("Run: pip install gcalcli && gcalcli init")
            return
        _add_event_google(event_name, event_date, start_time_parsed, end_time_parsed)
    else:
        _add_event_local(event_name, event_date, start_time_parsed, end_time_parsed)


def _add_event_evolution(event_name, event_date, start_time, end_time):
    """Add event to calendar via Evolution Data Server (syncs with Google)."""
    # Use the extended version with default values
    _add_event_evolution_extended(event_name, event_date, start_time, end_time)


def _add_event_evolution_extended(event_name, event_date, start_time, end_time,
                                   location=None, description=None, reminder_minutes=30):
    """Add event to calendar via Evolution Data Server with extended fields."""
    client = _get_evolution_client()
    if client is None:
        _speak("Could not connect to Evolution calendar.")
        return

    try:
        # Parse times and create full datetime
        date_str = event_date.strftime("%Y-%m-%d")
        start_24hr = datetime.strptime(start_time, "%I:%M %p").strftime("%H:%M")
        end_24hr = datetime.strptime(end_time, "%I:%M %p").strftime("%H:%M")

        start_dt = datetime.strptime(f"{date_str} {start_24hr}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{date_str} {end_24hr}", "%Y-%m-%d %H:%M")

        # Create iCal VEVENT string with extended fields
        import uuid
        uid = str(uuid.uuid4())

        # Build iCal components
        ical_lines = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTART:{start_dt.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:{event_name}",
        ]

        # Add optional fields
        if location:
            ical_lines.append(f"LOCATION:{location}")

        if description:
            # Escape newlines and special chars in description
            desc_escaped = description.replace('\n', '\\n').replace(',', '\\,')
            ical_lines.append(f"DESCRIPTION:{desc_escaped}")

        # Add reminder/alarm
        if reminder_minutes and reminder_minutes > 0:
            ical_lines.extend([
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                f"TRIGGER:-PT{reminder_minutes}M",
                f"DESCRIPTION:Reminder: {event_name}",
                "END:VALARM"
            ])

        ical_lines.append("END:VEVENT")
        ical_str = "\n".join(ical_lines)

        # Parse to ICalComponent
        vevent = ICalGLib.Component.new_from_string(ical_str)

        # Add to calendar with cancellable
        cancellable = Gio.Cancellable.new()
        success, new_uid = client.create_object_sync(vevent, ECal.OperationFlags.NONE, cancellable)

        if success:
            extras = []
            if location:
                extras.append(f"at {location}")
            if reminder_minutes:
                extras.append(f"reminder {reminder_minutes}min")
            extra_str = f" ({', '.join(extras)})" if extras else ""

            print(f"[EVOLUTION] Added: {event_name} on {date_str} from {start_time} to {end_time}{extra_str}")
            _speak(f"Added {event_name} to your calendar.")
        else:
            print(f"[EVOLUTION] Failed to add event")
            _speak("Sorry, I couldn't add the event.")

    except Exception as e:
        print(f"[EVOLUTION] Error adding event: {e}")
        _speak("Sorry, there was an error adding the event.")


def check_calendar_conflicts(date, start_time, end_time):
    """
    Check if there are conflicting events at the specified time.
    Returns list of conflicting event names, or empty list if no conflicts.
    """
    if CALENDAR_BACKEND != "evolution" or not EVOLUTION_AVAILABLE:
        return []  # Can't check conflicts without Evolution

    client = _get_evolution_client()
    if client is None:
        return []

    try:
        # Parse date
        if isinstance(date, str):
            parsed = parse_date(date, silent=True)
            if not parsed:
                return []
            check_date = parsed.date()
        else:
            check_date = date.date() if hasattr(date, 'date') else date

        # Create time range for query
        start_dt = datetime.combine(check_date, datetime.min.time())
        end_dt = datetime.combine(check_date, datetime.max.time())

        start_iso = start_dt.strftime("%Y%m%dT000000Z")
        end_iso = end_dt.strftime("%Y%m%dT235959Z")

        query = f"(occur-in-time-range? (make-time \"{start_iso}\") (make-time \"{end_iso}\"))"
        cancellable = Gio.Cancellable.new()
        success, events = client.get_object_list_sync(query, cancellable)

        if not success or not events:
            return []

        # Parse the requested time
        req_start_h, req_start_m = map(int, start_time.split(":"))
        req_end_h, req_end_m = map(int, end_time.split(":")) if end_time else (req_start_h + 1, req_start_m)
        req_start_mins = req_start_h * 60 + req_start_m
        req_end_mins = req_end_h * 60 + req_end_m

        conflicts = []
        for ical_comp in events:
            summary_prop = ical_comp.get_first_property(ICalGLib.PropertyKind.SUMMARY_PROPERTY)
            dtstart_prop = ical_comp.get_first_property(ICalGLib.PropertyKind.DTSTART_PROPERTY)
            dtend_prop = ical_comp.get_first_property(ICalGLib.PropertyKind.DTEND_PROPERTY)

            if summary_prop and dtstart_prop:
                event_name = summary_prop.get_summary()

                # Get event times
                dt_start = dtstart_prop.get_dtstart()
                evt_start_mins = dt_start.get_hour() * 60 + dt_start.get_minute() if dt_start else 0

                evt_end_mins = evt_start_mins + 60  # Default 1 hour
                if dtend_prop:
                    dt_end = dtend_prop.get_dtend()
                    if dt_end:
                        evt_end_mins = dt_end.get_hour() * 60 + dt_end.get_minute()

                # Check for overlap
                if not (req_end_mins <= evt_start_mins or req_start_mins >= evt_end_mins):
                    conflicts.append(event_name)

        return conflicts

    except Exception as e:
        print(f"[EVOLUTION] Error checking conflicts: {e}")
        return []


def add_event_to_calendar_extended(event_name, start_time, end_time, date="today",
                                    location=None, description=None, reminder_minutes=30):
    """Add an event with extended fields (location, description, reminder)."""

    event_date = parse_date(date)
    if event_date is None:
        return

    start_time_parsed = parse_time(start_time)
    end_time_parsed = parse_time(end_time)
    if not start_time_parsed or not end_time_parsed:
        return

    # Use Evolution if configured and available
    if CALENDAR_BACKEND == "evolution":
        if not EVOLUTION_AVAILABLE:
            _speak("Evolution calendar is not available.")
            return
        _add_event_evolution_extended(event_name, event_date, start_time_parsed, end_time_parsed,
                                       location, description, reminder_minutes)
    elif CALENDAR_BACKEND == "google":
        # Google calendar via gcalcli doesn't support all fields easily
        # Fall back to basic add
        _add_event_google(event_name, event_date, start_time_parsed, end_time_parsed)
    else:
        _add_event_local(event_name, event_date, start_time_parsed, end_time_parsed)


def _add_event_google(event_name, event_date, start_time, end_time):
    """Add event to Google Calendar using gcalcli."""
    # Format: "2024-01-15 14:00" for gcalcli
    date_str = event_date.strftime("%Y-%m-%d")
    start_24hr = datetime.strptime(start_time, "%I:%M %p").strftime("%H:%M")
    end_24hr = datetime.strptime(end_time, "%I:%M %p").strftime("%H:%M")

    start_datetime = f"{date_str} {start_24hr}"
    end_datetime = f"{date_str} {end_24hr}"

    try:
        cmd = [
            "gcalcli", "add",
            "--calendar", CALENDAR_ID,
            "--title", event_name,
            "--when", start_datetime,
            "--end", end_datetime,
            "--noprompt"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            print(f"[GOOGLE] Added: {event_name} on {date_str} from {start_time} to {end_time}")
            _speak(f"Added {event_name} to your Google Calendar.")
        else:
            print(f"[GOOGLE] Error: {result.stderr}")
            _speak("Sorry, I couldn't add the event to Google Calendar.")

    except subprocess.TimeoutExpired:
        _speak("Google Calendar timed out.")
    except Exception as e:
        print(f"[GOOGLE] Exception: {e}")
        _speak("Sorry, there was an error adding to Google Calendar.")


def _add_event_local(event_name, event_date, start_time, end_time):
    """Add event to local .reminders file."""
    reminder_file = os.path.expanduser("~/.reminders")

    event_date_str = event_date.strftime("%d %b %Y")

    start_time_24hr = datetime.strptime(start_time, "%I:%M %p").strftime("%H:%M")
    end_time_24hr = datetime.strptime(end_time, "%I:%M %p").strftime("%H:%M")

    duration_hours = int(end_time_24hr.split(":")[0]) - int(start_time_24hr.split(":")[0])
    duration_minutes = int(end_time_24hr.split(":")[1]) - int(start_time_24hr.split(":")[1])

    if duration_minutes < 0:
        duration_minutes += 60
        duration_hours -= 1

    duration = f"+{duration_hours}h{duration_minutes}m"

    reminder_entry = f"REM {event_date_str} AT {start_time_24hr} {duration} MSG {event_name}\n"

    with open(reminder_file, "a") as file:
        file.write(reminder_entry)

    print(f"[LOCAL] Added: {event_name} on {event_date_str} from {start_time} to {end_time}")
    _speak(f"The event {event_name} has been added to your calendar.")

def check_calendar(date="today", week=False, specific_week_start=None):
    """Check calendar events (Evolution, Google Calendar, or local .reminders)."""

    # Use Evolution if configured and available
    if CALENDAR_BACKEND == "evolution":
        if not EVOLUTION_AVAILABLE:
            _speak("Evolution calendar is not available.")
            return
        return _check_calendar_evolution(date, week, specific_week_start)
    # Use Google Calendar if configured and available
    elif CALENDAR_BACKEND == "google":
        if not GCALCLI_AVAILABLE:
            _speak("Google Calendar is not set up. Please install gcalcli first.")
            return
        return _check_calendar_google(date, week, specific_week_start)
    else:
        return _check_calendar_local(date, week, specific_week_start)


def _check_calendar_evolution(date="today", week=False, specific_week_start=None):
    """Check calendar events via Evolution Data Server."""
    client = _get_evolution_client()
    if client is None:
        _speak("Could not connect to Evolution calendar.")
        return

    # Calculate date range
    if week:
        if date.lower() == "this week":
            start_date = datetime.now().date() - timedelta(days=datetime.now().weekday())
            end_date = start_date + timedelta(days=6)
        elif date.lower() == "next week":
            start_date = datetime.now().date() + timedelta(days=(7 - datetime.now().weekday()))
            end_date = start_date + timedelta(days=6)
        elif specific_week_start:
            parsed = parse_date(specific_week_start)
            if parsed:
                start_date = parsed.date()
                end_date = start_date + timedelta(days=6)
            else:
                return
        else:
            _speak("I couldn't understand the week query.")
            return
    else:
        date_lower = date.lower().strip()
        if "today" in date_lower:
            start_date = end_date = datetime.now().date()
        elif "tomorrow" in date_lower:
            start_date = end_date = datetime.now().date() + timedelta(days=1)
        else:
            parsed = parse_date(date)
            if not parsed:
                return
            start_date = end_date = parsed.date()

    try:
        # Create time range for query (start of start_date to end of end_date)
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        # Format for Evolution query (ISO format)
        start_iso = start_dt.strftime("%Y%m%dT000000Z")
        end_iso = end_dt.strftime("%Y%m%dT235959Z")

        # Query events in date range
        query = f"(occur-in-time-range? (make-time \"{start_iso}\") (make-time \"{end_iso}\"))"

        cancellable = Gio.Cancellable.new()
        success, events = client.get_object_list_sync(query, cancellable)

        if success and events:
            # Parse events and sort by time
            event_list = []
            for ical_comp in events:
                # ical_comp is already an ICalGLib.Component
                summary_prop = ical_comp.get_first_property(ICalGLib.PropertyKind.SUMMARY_PROPERTY)
                dtstart_prop = ical_comp.get_first_property(ICalGLib.PropertyKind.DTSTART_PROPERTY)

                if summary_prop:
                    summary_text = summary_prop.get_summary()
                    hour, minute = 0, 0
                    time_str = ""

                    if dtstart_prop:
                        dt = dtstart_prop.get_dtstart()
                        if dt:
                            hour = dt.get_hour()
                            minute = dt.get_minute()
                            if hour > 0 or minute > 0:  # Has time component
                                time_str = f"{hour}:{minute:02d}"

                    event_list.append((hour, minute, summary_text, time_str))

            # Sort by time
            event_list.sort(key=lambda x: (x[0], x[1]))

            if event_list:
                # Build complete response to speak with consistent language
                if week:
                    header = "Your events for this week:"
                else:
                    header = f"Your events for {start_date.strftime('%A, %B %d')}:"

                # Collect all events into one text block
                event_texts = []
                for _, _, summary, time_str in event_list[:10]:
                    if time_str:
                        event_texts.append(f"{summary} at {time_str}")
                    else:
                        event_texts.append(summary)

                # Join with pause markers and speak all at once (consistent language)
                full_text = f"{header} " + ". ".join(event_texts)
                _speak(full_text)

                return f"Found {len(event_list)} events"
            else:
                if week:
                    _speak("You have no events this week.")
                else:
                    _speak(f"You have no events on {start_date.strftime('%A, %B %d')}.")
        else:
            if week:
                _speak("You have no events this week.")
            else:
                _speak(f"You have no events on {start_date.strftime('%A, %B %d')}.")

    except Exception as e:
        print(f"[EVOLUTION] Error checking calendar: {e}")
        _speak("Sorry, I couldn't check your calendar.")


def _check_calendar_google(date="today", week=False, specific_week_start=None):
    """Check Google Calendar events using gcalcli."""

    # Calculate date range
    if week:
        if date.lower() == "this week":
            start_date = datetime.now().date() - timedelta(days=datetime.now().weekday())
            end_date = start_date + timedelta(days=6)
        elif date.lower() == "next week":
            start_date = datetime.now().date() + timedelta(days=(7 - datetime.now().weekday()))
            end_date = start_date + timedelta(days=6)
        elif specific_week_start:
            parsed = parse_date(specific_week_start)
            if parsed:
                start_date = parsed.date()
                end_date = start_date + timedelta(days=6)
            else:
                return
        else:
            _speak("I couldn't understand the week query.")
            return
    else:
        date_lower = date.lower().strip()
        if "today" in date_lower:
            start_date = end_date = datetime.now().date()
        elif "tomorrow" in date_lower:
            start_date = end_date = datetime.now().date() + timedelta(days=1)
        else:
            parsed = parse_date(date)
            if not parsed:
                return
            start_date = end_date = parsed.date()

    try:
        # gcalcli agenda "start" "end"
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")  # +1 to include end date

        cmd = [
            "gcalcli", "agenda",
            start_str, end_str,
            "--calendar", CALENDAR_ID,
            "--nostarted"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0 and result.stdout.strip():
            output = result.stdout.strip()
            # Clean up gcalcli output for speech
            lines = [line.strip() for line in output.split('\n') if line.strip()]

            if lines and not all("No Events" in line for line in lines):
                # Build complete response to speak with consistent language
                if week:
                    header = "Your events for this week:"
                else:
                    header = f"Your events for {start_date.strftime('%A, %B %d')}:"

                # Collect all events into one text block
                event_texts = []
                for line in lines[:10]:  # Limit to 10 events for speech
                    # Skip header lines
                    if line and not line.startswith('-'):
                        event_texts.append(line)

                # Join with pause markers and speak all at once (consistent language)
                full_text = f"{header} " + ". ".join(event_texts)
                _speak(full_text)
            else:
                if week:
                    _speak("You have no events this week.")
                else:
                    _speak(f"You have no events on {start_date.strftime('%A, %B %d')}.")
        else:
            if week:
                _speak("You have no events this week.")
            else:
                _speak(f"You have no events on {start_date.strftime('%A, %B %d')}.")

    except subprocess.TimeoutExpired:
        _speak("Google Calendar timed out.")
    except Exception as e:
        print(f"[GOOGLE] Error checking calendar: {e}")
        _speak("Sorry, I couldn't check your Google Calendar.")


def _check_calendar_local(date="today", week=False, specific_week_start=None):
    """Check local .reminders file for events."""
    reminder_file = os.path.expanduser("~/.reminders")

    if week:
        # Handle "this week", "next week", or a specific week
        if date.lower() == "this week":
            start_date = datetime.now().date() - timedelta(days=datetime.now().weekday())  # Monday of this week
            end_date = start_date + timedelta(days=6)
        elif date.lower() == "next week":
            start_date = (datetime.now().date() + timedelta(days=(7 - datetime.now().weekday())))  # Monday of next week
            end_date = start_date + timedelta(days=6)
        elif specific_week_start:
            start_date = datetime.strptime(specific_week_start, "%d %b %Y").date()
            end_date = start_date + timedelta(days=6)
        else:
            return "Invalid week query."

        print(f"Attempting to retrieve calendar events for the week of {start_date.strftime('%A, %B %d')} through {end_date.strftime('%A, %B %d')}...")
    else:
        date_lower = date.lower().strip()
        # Handle variations like "for today", "today's", etc.
        if "today" in date_lower:
            start_date = end_date = datetime.now().date()
        elif "tomorrow" in date_lower:
            start_date = end_date = (datetime.now().date() + timedelta(days=1))
        else:
            parsed_date = parse_date(date)
            if not parsed_date:
                return
            start_date = end_date = parsed_date.date()

    try:
        print(f"Checking calendar events between {start_date.strftime('%d %b %Y')} and {end_date.strftime('%d %b %Y')}...")

        # Read the .reminders file directly
        with open(reminder_file, 'r') as file:
            lines = file.readlines()

        day_events = []
        unique_events = set()  # To track unique events and prevent duplicates

        for line in lines:
            event_date_str = re.search(r'REM (\d{2} \w{3} \d{4})', line)
            if event_date_str:
                event_date = datetime.strptime(event_date_str.group(1), "%d %b %Y").date()
                if start_date <= event_date <= end_date:
                    time_obj, formatted_event = parse_event(line.strip())
                    if time_obj and formatted_event not in unique_events:
                        day_events.append((event_date, time_obj, formatted_event))
                        unique_events.add(formatted_event)

        # Sort events by date and then by time
        day_events.sort(key=lambda x: (x[0], x[1]))

        if day_events:
            # Build complete response to speak with consistent language
            if week:
                week_str = f"{start_date.strftime('%A, %B %d')} through {end_date.strftime('%A, %B %d')}"
                header = f"Events for the week of {week_str}:"
            else:
                day_str = f"{start_date.strftime('%A, %B %d, %Y')}"
                header = f"Here are your events for {day_str}:"

            # Collect all events into one text block
            event_texts = [f"{event[2]} on {event[0].strftime('%A, %B %d')}" for event in day_events]

            # Join with pause markers and speak all at once (consistent language)
            full_text = f"{header} " + ". ".join(event_texts)
            _speak(full_text)

            if week:
                return f"Events for the week of {week_str}: {'; '.join(event[2] for event in day_events)}"
            else:
                return f"Events for {day_str}: {'; '.join(event[2] for event in day_events)}"
        else:
            print("No events found.")
            if week:
                week_str = f"{start_date.strftime('%A, %B %d')} through {end_date.strftime('%A, %B %d')}"
                _speak(f"You have no events on your calendar for the week of {week_str}.")
                return f"You have no events on your calendar for the week of {week_str}."
            else:
                day_str = f"{start_date.strftime('%A, %B %d, %Y')}"
                _speak(f"You have no events on your calendar for {day_str}.")
                return f"You have no events on your calendar for {day_str}."
    except FileNotFoundError:
        print(f"Error: {reminder_file} not found.")
        _speak(f"Error: {reminder_file} not found.")
        return f"Error: {reminder_file} not found."
    except Exception as e:
        print(f"Unexpected error: {e}")
        _speak("An unexpected error occurred.")
        return "An unexpected error occurred."

def get_events_on_date(date):
    """
    Get all events on a specific date with UIDs for deletion.

    Args:
        date: Date string like "today", "tomorrow", "2026-01-20"

    Returns:
        List of dicts: [{name, time_str, uid}, ...] or empty list
    """
    event_date = parse_date(date)
    if event_date is None:
        return []

    if CALENDAR_BACKEND == "evolution":
        if not EVOLUTION_AVAILABLE:
            return []
        return _get_events_evolution(event_date)
    else:
        # Local file backend - return simple list without UIDs
        return _get_events_local(event_date)


def _get_events_evolution(event_date):
    """Get events from Evolution calendar with UIDs."""
    client = _get_evolution_client()
    if client is None:
        return []

    try:
        check_date = event_date.date() if hasattr(event_date, 'date') else event_date
        start_dt = datetime.combine(check_date, datetime.min.time())
        end_dt = datetime.combine(check_date, datetime.max.time())

        start_iso = start_dt.strftime("%Y%m%dT000000Z")
        end_iso = end_dt.strftime("%Y%m%dT235959Z")

        query = f"(occur-in-time-range? (make-time \"{start_iso}\") (make-time \"{end_iso}\"))"
        cancellable = Gio.Cancellable.new()
        success, events = client.get_object_list_sync(query, cancellable)

        if not success or not events:
            return []

        event_list = []
        for ical_comp in events:
            summary_prop = ical_comp.get_first_property(ICalGLib.PropertyKind.SUMMARY_PROPERTY)
            uid_prop = ical_comp.get_first_property(ICalGLib.PropertyKind.UID_PROPERTY)
            dtstart_prop = ical_comp.get_first_property(ICalGLib.PropertyKind.DTSTART_PROPERTY)

            if summary_prop and uid_prop:
                summary_text = summary_prop.get_summary()
                uid = uid_prop.get_uid()
                time_str = ""
                hour, minute = 0, 0

                if dtstart_prop:
                    dt = dtstart_prop.get_dtstart()
                    if dt:
                        hour = dt.get_hour()
                        minute = dt.get_minute()
                        if hour > 0 or minute > 0:
                            time_str = f"{hour}:{minute:02d}"

                event_list.append({
                    "name": summary_text,
                    "time_str": time_str,
                    "uid": uid,
                    "hour": hour,
                    "minute": minute
                })

        # Sort by time
        event_list.sort(key=lambda x: (x["hour"], x["minute"]))
        return event_list

    except Exception as e:
        print(f"[EVOLUTION] Error getting events: {e}")
        return []


def _get_events_local(event_date):
    """Get events from local .reminders file (no UIDs, use index)."""
    reminder_file = os.path.expanduser("~/.reminders")
    event_date_str = event_date.strftime("%d %b %Y")
    events = []

    if os.path.exists(reminder_file):
        with open(reminder_file, 'r') as f:
            for i, line in enumerate(f):
                if event_date_str in line:
                    events.append({
                        "name": line.strip(),
                        "time_str": "",
                        "uid": str(i),  # Use line number as "uid"
                        "hour": 0,
                        "minute": 0
                    })
    return events


def remove_event_by_uid(uid, date=None):
    """
    Remove event by UID (or line number for local backend).

    Args:
        uid: Event UID (Evolution) or line index (local)
        date: Required for local backend to find the file

    Returns:
        True if removed, False otherwise
    """
    if CALENDAR_BACKEND == "evolution":
        if not EVOLUTION_AVAILABLE:
            return False
        return _remove_event_by_uid_evolution(uid)
    else:
        return _remove_event_by_uid_local(uid)


def _remove_event_by_uid_evolution(uid):
    """Remove event from Evolution by UID."""
    client = _get_evolution_client()
    if client is None:
        return False

    try:
        cancellable = Gio.Cancellable.new()
        # API: remove_object_sync(uid, rid, mod, opflags, cancellable)
        # rid = recurrence ID (None for non-recurring events)
        success = client.remove_object_sync(
            uid,
            None,  # rid (recurrence ID)
            ECal.ObjModType.ALL,
            ECal.OperationFlags.NONE,
            cancellable
        )
        if success:
            print(f"[EVOLUTION] Removed event with UID: {uid}")
        return success
    except Exception as e:
        print(f"[EVOLUTION] Error removing event: {e}")
        return False


def _remove_event_by_uid_local(uid):
    """Remove event from local file by line index."""
    reminder_file = os.path.expanduser("~/.reminders")
    line_index = int(uid)

    try:
        with open(reminder_file, 'r') as f:
            lines = f.readlines()

        if 0 <= line_index < len(lines):
            del lines[line_index]
            with open(reminder_file, 'w') as f:
                f.writelines(lines)
            return True
        return False
    except Exception as e:
        print(f"[LOCAL] Error removing event: {e}")
        return False


def remove_event(event_name, date):
    """Remove a specific event by name and date (Evolution, Google, or local)."""
    event_date = parse_date(date)
    if event_date is None:
        _speak("I couldn't understand the date.")
        return

    # Use Evolution if configured and available
    if CALENDAR_BACKEND == "evolution":
        if not EVOLUTION_AVAILABLE:
            _speak("Evolution calendar is not available.")
            return
        return _remove_event_evolution(event_name, event_date)
    # Use Google Calendar if configured
    elif CALENDAR_BACKEND == "google":
        # Google via gcalcli - not implemented yet
        _speak("Removing events from Google Calendar is not yet supported.")
        return
    else:
        return _remove_event_local(event_name, event_date)


def _remove_event_evolution(event_name, event_date):
    """Remove event from Evolution calendar by name and date."""
    client = _get_evolution_client()
    if client is None:
        _speak("Could not connect to Evolution calendar.")
        return

    try:
        # Query events on that date
        check_date = event_date.date() if hasattr(event_date, 'date') else event_date
        start_dt = datetime.combine(check_date, datetime.min.time())
        end_dt = datetime.combine(check_date, datetime.max.time())

        start_iso = start_dt.strftime("%Y%m%dT000000Z")
        end_iso = end_dt.strftime("%Y%m%dT235959Z")

        query = f"(occur-in-time-range? (make-time \"{start_iso}\") (make-time \"{end_iso}\"))"
        cancellable = Gio.Cancellable.new()
        success, events = client.get_object_list_sync(query, cancellable)

        if not success or not events:
            _speak(f"No events found on {check_date.strftime('%A, %B %d')}.")
            return

        # Find matching event by name (case-insensitive partial match)
        event_name_lower = event_name.lower()
        found_event = None
        found_uid = None

        for ical_comp in events:
            summary_prop = ical_comp.get_first_property(ICalGLib.PropertyKind.SUMMARY_PROPERTY)
            uid_prop = ical_comp.get_first_property(ICalGLib.PropertyKind.UID_PROPERTY)

            if summary_prop and uid_prop:
                summary_text = summary_prop.get_summary()
                if summary_text and event_name_lower in summary_text.lower():
                    found_event = summary_text
                    found_uid = uid_prop.get_uid()
                    break

        if not found_uid:
            _speak(f"No event matching '{event_name}' found on {check_date.strftime('%A, %B %d')}.")
            return

        # Delete the event
        cancellable = Gio.Cancellable.new()
        success = client.remove_object_sync(
            found_uid,
            None,  # rid (recurrence ID)
            ECal.ObjModType.ALL,
            ECal.OperationFlags.NONE,
            cancellable
        )

        if success:
            print(f"[EVOLUTION] Removed: {found_event} on {check_date}")
            _speak(f"Removed '{found_event}' from your calendar.")
        else:
            _speak("Sorry, I couldn't remove the event.")

    except Exception as e:
        print(f"[EVOLUTION] Error removing event: {e}")
        _speak("Sorry, there was an error removing the event.")


def _remove_event_local(event_name, event_date):
    """Remove event from local .reminders file."""
    reminder_file = os.path.expanduser("~/.reminders")
    event_date_str = event_date.strftime("%d %b %Y")

    try:
        with open(reminder_file, 'r') as file:
            lines = file.readlines()

        with open(reminder_file, 'w') as file:
            removed = False
            for line in lines:
                if event_date_str in line and event_name.lower() in line.lower():
                    removed = True
                    continue
                file.write(line)

        if removed:
            _speak(f"The event {event_name} on {event_date_str} has been removed from your calendar.")
        else:
            _speak(f"No matching event found for {event_name} on {event_date_str}.")

    except FileNotFoundError:
        _speak(f"Error: {reminder_file} not found.")

def clear_calendar(date=None, week=False):
    """Clear all events on a specific date or within a week (Evolution, Google, or local)."""
    # Calculate date range first
    if week:
        parsed = parse_date(date)
        if not parsed:
            _speak("I couldn't understand the date.")
            return
        start_date = parsed.date()
        start_date = start_date - timedelta(days=start_date.weekday())
        end_date = start_date + timedelta(days=6)
    else:
        parsed = parse_date(date)
        if not parsed:
            _speak("I couldn't understand the date.")
            return
        start_date = end_date = parsed.date()

    # Use Evolution if configured and available
    if CALENDAR_BACKEND == "evolution":
        if not EVOLUTION_AVAILABLE:
            _speak("Evolution calendar is not available.")
            return
        return _clear_calendar_evolution(start_date, end_date, week)
    # Use Google Calendar if configured
    elif CALENDAR_BACKEND == "google":
        _speak("Clearing events from Google Calendar is not yet supported.")
        return
    else:
        return _clear_calendar_local(start_date, end_date, week)


def _clear_calendar_evolution(start_date, end_date, week=False):
    """Clear all events in date range from Evolution calendar."""
    client = _get_evolution_client()
    if client is None:
        _speak("Could not connect to Evolution calendar.")
        return

    try:
        # Query events in date range
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        start_iso = start_dt.strftime("%Y%m%dT000000Z")
        end_iso = end_dt.strftime("%Y%m%dT235959Z")

        query = f"(occur-in-time-range? (make-time \"{start_iso}\") (make-time \"{end_iso}\"))"
        cancellable = Gio.Cancellable.new()
        success, events = client.get_object_list_sync(query, cancellable)

        if not success or not events:
            if week:
                _speak(f"No events found for the week.")
            else:
                _speak(f"No events found on {start_date.strftime('%A, %B %d')}.")
            return

        # Collect all UIDs to delete
        uids_to_delete = []
        for ical_comp in events:
            uid_prop = ical_comp.get_first_property(ICalGLib.PropertyKind.UID_PROPERTY)
            if uid_prop:
                uids_to_delete.append(uid_prop.get_uid())

        # Delete all events
        deleted_count = 0
        for uid in uids_to_delete:
            try:
                cancellable = Gio.Cancellable.new()
                success = client.remove_object_sync(
                    uid,
                    None,  # rid (recurrence ID)
                    ECal.ObjModType.ALL,
                    ECal.OperationFlags.NONE,
                    cancellable
                )
                if success:
                    deleted_count += 1
            except Exception as e:
                print(f"[EVOLUTION] Error deleting event {uid}: {e}")

        if week:
            week_str = f"{start_date.strftime('%A, %B %d')} through {end_date.strftime('%A, %B %d')}"
            print(f"[EVOLUTION] Cleared {deleted_count} events for week of {week_str}")
            _speak(f"Cleared {deleted_count} events for the week.")
        else:
            print(f"[EVOLUTION] Cleared {deleted_count} events on {start_date}")
            _speak(f"Cleared {deleted_count} events on {start_date.strftime('%A, %B %d')}.")

    except Exception as e:
        print(f"[EVOLUTION] Error clearing calendar: {e}")
        _speak("Sorry, there was an error clearing the calendar.")


def _clear_calendar_local(start_date, end_date, week=False):
    """Clear events from local .reminders file."""
    reminder_file = os.path.expanduser("~/.reminders")

    try:
        with open(reminder_file, 'r') as file:
            lines = file.readlines()

        with open(reminder_file, 'w') as file:
            for line in lines:
                event_date_str = re.search(r'REM (\d{2} \w{3} \d{4})', line)
                if event_date_str:
                    event_date = datetime.strptime(event_date_str.group(1), "%d %b %Y").date()
                    if not (start_date <= event_date <= end_date):
                        file.write(line)

        if week:
            week_str = f"{start_date.strftime('%A, %B %d')} through {end_date.strftime('%A, %B %d')}"
            _speak(f"All events for the week of {week_str} have been cleared from your calendar.")
        else:
            _speak(f"All events on {start_date.strftime('%A, %B %d')} have been cleared from your calendar.")

    except FileNotFoundError:
        _speak(f"Error: {reminder_file} not found.")
