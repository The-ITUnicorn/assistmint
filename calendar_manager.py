from datetime import datetime, timedelta
import re
import os
import dateparser
from text_to_speech import speak
import time

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

def parse_time(time_str):
    """Parses time in natural language like 'seven am', 'three thirty pm', etc., and converts it to 'H:MM AM/PM' format."""

    # Mapping of number words to digits for both hours and minutes
    num_words = {
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
        "fifty-seven": "57", "fifty-eight": "58", "fifty-nine": "59"
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
            speak(f"Sorry, I couldn't understand the time {time_str}.", speed=1.5)
            return None

        # Construct the final time string in "H:MM AM/PM" format
        formatted_time = f"{hour}:{minutes} {period.upper()}"
        return formatted_time
    except ValueError:
        speak(f"Sorry, I couldn't understand the time {time_str}.", speed=1.5)
        return None

def parse_date(date_str):
    """Parses natural language dates like 'today', 'tomorrow', 'this Friday', or 'August 29'."""
    now = datetime.now()
    parsed_date = dateparser.parse(date_str)

    if parsed_date is None:
        speak(f"Sorry, I couldn't understand the date {date_str}.", speed=1.5)
        return None

    # Handle cases where the year is not specified
    if parsed_date.year == now.year and parsed_date < now:
        parsed_date = parsed_date.replace(year=now.year + 1)

    return parsed_date

def add_event_to_calendar(event_name, start_time, end_time, date="today"):
    """Function to add an event to the .reminders file"""
    reminder_file = os.path.expanduser("~/.reminders")
    
    event_date = parse_date(date)
    if event_date is None:
        return

    event_date_str = event_date.strftime("%d %b %Y")

    start_time = parse_time(start_time)
    end_time = parse_time(end_time)
    if not start_time or not end_time:
        return
    
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

    print(f"Added event: {event_name} on {event_date_str} from {start_time} to {end_time}")
    speak(f"The event {event_name} has been added to your calendar.", speed=1.5)

def check_calendar(date="today", week=False, specific_week_start=None):
    """Function to check and read calendar events from .reminders file"""
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
        if date.lower() == "today":
            start_date = end_date = datetime.now().date()
        elif date.lower() == "tomorrow":
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
            if week:
                week_str = f"{start_date.strftime('%A, %B %d')} through {end_date.strftime('%A, %B %d')}"
                speak(f"Events for the week of {week_str}:", speed=1.5)
            else:
                day_str = f"{start_date.strftime('%A, %B %d, %Y')}"
                speak(f"Here are your events for {day_str}:", speed=1.5)
            
            for event in day_events:
                speak(f"{event[2]} on {event[0].strftime('%A, %B %d')}", speed=1.5)
                time.sleep(1)  # Pause for one second between events

            if week:
                return f"Events for the week of {week_str}: {'; '.join(event[2] for event in day_events)}"
            else:
                return f"Events for {day_str}: {'; '.join(event[2] for event in day_events)}"
        else:
            print("No events found.")
            if week:
                week_str = f"{start_date.strftime('%A, %B %d')} through {end_date.strftime('%A, %B %d')}"
                speak(f"You have no events on your calendar for the week of {week_str}.", speed=1.5)
                return f"You have no events on your calendar for the week of {week_str}."
            else:
                day_str = f"{start_date.strftime('%A, %B %d, %Y')}"
                speak(f"You have no events on your calendar for {day_str}.", speed=1.5)
                return f"You have no events on your calendar for {day_str}."
    except FileNotFoundError:
        print(f"Error: {reminder_file} not found.")
        speak(f"Error: {reminder_file} not found.", speed=1.5)
        return f"Error: {reminder_file} not found."
    except Exception as e:
        print(f"Unexpected error: {e}")
        speak("An unexpected error occurred.", speed=1.5)
        return "An unexpected error occurred."

def remove_event(event_name, date):
    """Remove a specific event by name and date."""
    reminder_file = os.path.expanduser("~/.reminders")
    event_date = parse_date(date)
    if event_date is None:
        return

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
            speak(f"The event {event_name} on {event_date_str} has been removed from your calendar.", speed=1.5)
        else:
            speak(f"No matching event found for {event_name} on {event_date_str}.", speed=1.5)

    except FileNotFoundError:
        speak(f"Error: {reminder_file} not found.", speed=1.5)

def clear_calendar(date=None, week=False):
    """Clear all events on a specific date or within a week."""
    reminder_file = os.path.expanduser("~/.reminders")
    
    if week:
        start_date = parse_date(date)
        if not start_date:
            return
        start_date = start_date.date()
        start_date = start_date - timedelta(days=start_date.weekday())
        end_date = start_date + timedelta(days=6)
    else:
        start_date = end_date = parse_date(date)
        if not start_date:
            return
        start_date = start_date.date()
        end_date = end_date.date()

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
            speak(f"All events for the week of {week_str} have been cleared from your calendar.", speed=1.5)
        else:
            speak(f"All events on {start_date.strftime('%A, %B %d')} have been cleared from your calendar.", speed=1.5)

    except FileNotFoundError:
        speak(f"Error: {reminder_file} not found.", speed=1.5)

