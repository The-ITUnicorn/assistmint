#A local AI assistant that can add/remove/retrieve events on your calendar.  It also ties into Jan AI to have voice chats with all your LLMs in Jan.
#You'll need to download a vosk model and put it in a directory vosk-model in the same directory as the python files.
#clone this repo using git
#using python3.10:  
python3.10 -m venv tuxenv
source tuxenv/bin/activate
pip install -r requirements.txt
#now you can run the app using the start_assistant.sh file
#copy the Assistant.desktop and you can use that to launch it as well.
