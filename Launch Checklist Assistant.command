#!/bin/bash
# Double-click this file in Finder to launch Checklist Assistant.
# It activates the project's venv and runs main.py, in this exact folder.
cd "$(dirname "$0")"
source venv/bin/activate
python main.py
