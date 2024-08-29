import requests
import json  # Add this line to import the json module
from text_to_speech import speak

def ask_jan(question):
    """Send a question to Jan AI and return the answer."""
    url = "http://localhost:1337/v1/chat/completions"  # Update with your API URL
    payload = {
        "model": "mistral-ins-7b-q4",  # Ensure the model is correctly specified
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": question},
        ],
        "stream": False,
        "max_tokens": 2048,
        "stop": None,
        "frequency_penalty": 0,
        "presence_penalty": 0,
        "temperature": 0.7,
        "top_p": 0.95
    }
    headers = {"Content-Type": "application/json"}

    # Print the API call details for debugging
    print("API Call Information:")
    print(f"URL: {url}")
    print(f"Headers: {headers}")
    print(f"Payload: {json.dumps(payload, indent=4)}")

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Content: {response.content.decode('utf-8')}")

        if response.status_code == 200:
            answer = response.json().get("choices", [{}])[0].get("message", {}).get("content", "Sorry, I couldn't get a response.")
            speak(answer, speed=1.5)
        else:
            speak("An error occurred while trying to communicate with Jan AI.", speed=1.5)
    except requests.ConnectionError:
        print("Connection error: Unable to reach the Jan AI API.")
        speak("Please make sure the Jan AI API is running.", speed=1.5)
    except requests.RequestException as e:
        print(f"API request failed: {e}")
        speak("An error occurred while trying to communicate with Jan AI.", speed=1.5)

