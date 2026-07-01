#!/bin/bash
pip install -r requirements.txt
python fix_issues.py || true
python fix_frontend.py || true
python -c "from app import scrape_all, DEALS_FILE; import os; scrape_all() if not os.path.exists(DEALS_FILE) else None" || true
gunicorn --bind 0.0.0.0:${PORT:-5050} app:app
