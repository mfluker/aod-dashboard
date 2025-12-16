#!/bin/bash
# Quick local testing script for the dashboard

cd "$(dirname "$0")/dashboard"

echo "🚀 Starting dashboard locally..."
echo "📍 Dashboard will be available at: http://127.0.0.1:8050"
echo "🛑 Press Ctrl+C to stop"
echo ""

python3 render_app.py
