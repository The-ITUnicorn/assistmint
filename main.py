from speech_recognition import list_microphones, select_microphone_and_samplerate, vosk_speech_to_text
from calendar_manager import add_event_to_calendar, check_calendar, remove_event, clear_calendar
from jan_ai import ask_jan
from text_to_speech import speak

def main():
    input_devices = list_microphones()
    selected_device, samplerate = select_microphone_and_samplerate(input_devices)
    
    while True:
        mode = input("Type 'voice' to speak or 'type' to enter commands: ").strip().lower()
        if mode == "voice":
            while True:
                transcription = vosk_speech_to_text(selected_device, samplerate)
                if transcription:
                    print(f"Transcribed: {transcription}")
                    
                    if "put this on my calendar" in transcription.lower():
                        speak("What is the event?", speed=1.5)
                        event_name = vosk_speech_to_text(selected_device, samplerate).strip()

                        speak("What time does the event start?", speed=1.5)
                        start_time = vosk_speech_to_text(selected_device, samplerate).strip()

                        speak("What time does the event end?", speed=1.5)
                        end_time = vosk_speech_to_text(selected_device, samplerate).strip()

                        speak("What date is the event on?", speed=1.5)
                        event_date = vosk_speech_to_text(selected_device, samplerate).strip()

                        add_event_to_calendar(event_name, start_time, end_time, date=event_date)

                    elif "what's on my calendar" in transcription.lower():
                        speak("For which date or week?", speed=1.5)
                        query = vosk_speech_to_text(selected_device, samplerate).strip()

                        if "week" in query.lower():
                            if "this week" in query.lower():
                                check_calendar(date="this week", week=True)
                            elif "next week" in query.lower():
                                check_calendar(date="next week", week=True)
                            elif "week of" in query.lower():
                                specific_week_start = query.lower().replace("week of", "").strip()
                                check_calendar(specific_week_start=specific_week_start, week=True)
                            else:
                                speak("I couldn't understand the week query.", speed=1.5)
                        else:
                            check_calendar(date=query)

                    elif "clear my calendar" in transcription.lower():
                        speak("For which date or week would you like to clear your calendar?", speed=1.5)
                        query = vosk_speech_to_text(selected_device, samplerate).strip()

                        if "week" in query.lower():
                            if "this week" in query.lower():
                                clear_calendar(date="this week", week=True)
                            elif "next week" in query.lower():
                                clear_calendar(date="next week", week=True)
                            elif "week of" in query.lower():
                                specific_week_start = query.lower().replace("week of", "").strip()
                                clear_calendar(date=specific_week_start, week=True)
                            else:
                                speak("I couldn't understand the week query.", speed=1.5)
                        else:
                            clear_calendar(date=query)

                    elif "remove" in transcription.lower() and "event" in transcription.lower():
                        speak("What is the name of the event you'd like to remove?", speed=1.5)
                        event_name = vosk_speech_to_text(selected_device, samplerate).strip()

                        speak("What date is this event on?", speed=1.5)
                        event_date = vosk_speech_to_text(selected_device, samplerate).strip()

                        remove_event(event_name, event_date)

                    elif "ask jan" in transcription.lower():
                        speak("What would you like to ask Jan?", speed=1.5)
                        question = vosk_speech_to_text(selected_device, samplerate).strip()
                        ask_jan(question)

                    else:
                        print("Command not recognized.")

        elif mode == "type":
            while True:
                command = input("Enter your command: ").strip().lower()

                if "put this on my calendar" in command:
                    speak("What is the event?", speed=1.5)
                    event_name = input("Enter the event name: ").strip()

                    speak("What time does the event start?", speed=1.5)
                    start_time = input("Enter the start time (e.g., 8:00 AM): ").strip()

                    speak("What time does the event end?", speed=1.5)
                    end_time = input("Enter the end time (e.g., 10:00 AM): ").strip()

                    speak("What date is the event on?", speed=1.5)
                    event_date = input("Enter the date (e.g., today, tomorrow, or Aug 29): ").strip()

                    add_event_to_calendar(event_name, start_time, end_time, date=event_date)

                elif "what's on my calendar" in command:
                    speak("For which date or week?", speed=1.5)
                    query = input("Enter the date or week (e.g., today, tomorrow, this week, next week, or the week of Aug 29): ").strip()

                    if "week" in query:
                        if "this week" in query.lower():
                            check_calendar(date="this week", week=True)
                        elif "next week" in query.lower():
                            check_calendar(date="next week", week=True)
                        elif "week of" in query.lower():
                            specific_week_start = query.lower().replace("week of", "").strip()
                            check_calendar(specific_week_start=specific_week_start, week=True)
                        else:
                            speak("I couldn't understand the week query.", speed=1.5)
                    else:
                        check_calendar(date=query)

                elif "clear my calendar" in command:
                    speak("For which date or week would you like to clear your calendar?", speed=1.5)
                    query = input("Enter the date or week to clear (e.g., today, tomorrow, this week, next week, or the week of Aug 29): ").strip()

                    if "week" in query:
                        if "this week" in query.lower():
                            clear_calendar(date="this week", week=True)
                        elif "next week" in query.lower():
                            clear_calendar(date="next week", week=True)
                        elif "week of" in query.lower():
                            specific_week_start = query.lower().replace("week of", "").strip()
                            clear_calendar(date=specific_week_start, week=True)
                        else:
                            speak("I couldn't understand the week query.", speed=1.5)
                    else:
                        clear_calendar(date=query)

                elif "remove" in command and "event" in command:
                    speak("What is the name of the event you'd like to remove?", speed=1.5)
                    event_name = input("Enter the event name: ").strip()

                    speak("What date is this event on?", speed=1.5)
                    event_date = input("Enter the date (e.g., today, tomorrow, or Aug 29): ").strip()

                    remove_event(event_name, event_date)

                elif "ask jan" in command:
                    speak("What would you like to ask Jan?", speed=1.5)
                    question = input("Enter your question: ").strip()
                    ask_jan(question)

                else:
                    print("Unknown command.")
        else:
            print("Invalid mode selected. Please choose 'voice' or 'type'.")

if __name__ == "__main__":
    main()

