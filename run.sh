#!/bin/bash
# TruthLens Startup Script
# Set to exit on error for clean debugging
set -e

echo "Starting TruthLens services..."

# Step 1: Navigate to backend, install dependencies, and seed DB
cd backend
echo "Installing backend dependencies..."
pip install -r requirements.txt --break-system-packages

echo "Initializing SQLite database..."
python db.py

# Step 2: Check model training status (LIAR dataset)
if [ ! -d "model/truthlens_distilbert" ]; then
  echo "No fine-tuned model found — running train_model.py (LIAR dataset)..."
  # Run training. Note: If training fails, the script continues and uses BART/heuristic fallbacks.
  python train_model.py || echo "Warning: Model training failed. Heuristic and zero-shot fallbacks will be active."
fi

# Step 3: Start backend server in the background
echo "Starting FastAPI server on http://localhost:8000..."
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

# Ensure cleanup of background process on exit
trap "kill $BACKEND_PID" EXIT

# Step 4: Navigate to frontend, start HTTP server
cd ../frontend
echo "Starting frontend server on http://localhost:5500..."
# Attempt python command, then python3 if python is not available
python -m http.server 5500 || python3 -m http.server 5500
