#!/bin/bash
pip install -r requirements.txt
python fix_issues.py
python fix_frontend.py
python -c "from app import scrape_all; scrape_all()"
gunicorn --bind 0.0.0.0:${PORT:-5050} app:app
