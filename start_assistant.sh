#!/bin/bash

# Navigate to the project directory
cd /home/itunicorn/ai/assistmint

# Activate the virtual environment
source assistmintenv/bin/activate

# Run the main.py script
python main.py

# Deactivate the virtual environment after the script ends
deactivate
