#!/bin/bash
cd ~/pipeline
source .venv/bin/activate 2>/dev/null || true
pip3 install -q flask
python3 app.py
