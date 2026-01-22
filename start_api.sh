#!/bin/bash
# Start Canonical API Server

cd "$(dirname "$0")"
source venv/bin/activate
uvicorn canonical.api:app --host 0.0.0.0 --port 8000 --reload
