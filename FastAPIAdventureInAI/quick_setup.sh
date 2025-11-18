#!/bin/bash
# Quick start script for FastAPI Adventure in AI
# This script sets up the database and provides instructions

echo "================================================================"
echo "FastAPI Adventure in AI - Quick Setup"
echo "================================================================"
echo ""

# Check if virtual environment exists
if [ ! -f "env/bin/activate" ]; then
    echo "[ERROR] Virtual environment not found!"
    echo ""
    echo "Please create it first:"
    echo "  python -m venv env"
    echo "  source env/bin/activate"
    echo "  pip install -r requirements.txt"
    echo ""
    exit 1
fi

# Activate virtual environment
echo "[Step 1/3] Activating virtual environment..."
source env/bin/activate
echo ""

# Setup database
echo "[Step 2/3] Setting up database..."
python setup_database.py
echo ""

# Instructions
echo "[Step 3/3] Ready to start!"
echo ""
echo "================================================================"
echo "To start the application, open 3 separate terminals:"
echo "================================================================"
echo ""
echo "Terminal 1 - AI Server:"
echo "  cd FastAPIAdventureInAI"
echo "  source env/bin/activate"
echo "  python ai_server.py"
echo ""
echo "Terminal 2 - API Server:"
echo "  cd FastAPIAdventureInAI"
echo "  source env/bin/activate"
echo "  python main.py"
echo ""
echo "Terminal 3 - Frontend:"
echo "  cd adventure-client"
echo "  npm start"
echo ""
echo "================================================================"
echo "Then open browser to: http://localhost:3000"
echo "Login: admin / admin123"
echo "================================================================"
echo ""
