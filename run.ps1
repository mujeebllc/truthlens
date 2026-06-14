# TruthLens Windows Startup Script
Write-Host "Starting TruthLens services on Windows..." -ForegroundColor Cyan

# 1. Backend Setup
cd backend
Write-Host "Installing backend dependencies..." -ForegroundColor Green
pip install -r requirements.txt

Write-Host "Initializing SQLite database..." -ForegroundColor Green
python db.py

# Check if model exists
if (-not (Test-Path "model/truthlens_distilbert")) {
    Write-Host "No fine-tuned model found — running train_model.py (LIAR dataset)..." -ForegroundColor Yellow
    try {
        python train_model.py
    } catch {
        Write-Host "Warning: Model training failed. Heuristic and zero-shot fallbacks will be active." -ForegroundColor Red
    }
}

# Start backend server in a separate background thread / window
Write-Host "Starting FastAPI server on http://localhost:8000..." -ForegroundColor Green
Start-Process python -ArgumentList "-m uvicorn main:app --reload --port 8000" -NoNewWindow

# Wait for binding
Start-Sleep -Seconds 2

# 2. Frontend Setup
cd ../frontend
Write-Host "Starting frontend server on http://localhost:5500..." -ForegroundColor Green
Write-Host "Please open http://localhost:5500 in your browser." -ForegroundColor Cyan
python -m http.server 5500
