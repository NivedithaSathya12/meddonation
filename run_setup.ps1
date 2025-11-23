# Direct Setup Script - Medicine Donation Project
# This script finds Python and sets up the project

Write-Host "=== Medicine Donation Project Setup ===" -ForegroundColor Cyan
Write-Host ""

# Find Python executable
$pythonExe = $null

# Check common Python installation paths
$pythonPaths = @(
    "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "$env:ProgramFiles\Python314\python.exe",
    "$env:ProgramFiles\Python313\python.exe",
    "$env:ProgramFiles\Python312\python.exe"
)

foreach ($path in $pythonPaths) {
    if (Test-Path $path) {
        $pythonExe = $path
        Write-Host "Found Python at: $pythonExe" -ForegroundColor Green
        break
    }
}

# If not found, try commands
if (-not $pythonExe) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $pythonExe = "python"
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $pythonExe = "py"
    }
}

if (-not $pythonExe) {
    Write-Host "ERROR: Python not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Python from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "During installation, make sure to check 'Add Python to PATH'" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Or if Python is already installed, add it to PATH manually." -ForegroundColor Yellow
    exit 1
}

Write-Host "Using: $pythonExe" -ForegroundColor Green
Write-Host ""

# Step 1: Upgrade pip
Write-Host "Step 1: Upgrading pip..." -ForegroundColor Yellow
& $pythonExe -m pip install --upgrade pip

if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: pip upgrade failed, continuing anyway..." -ForegroundColor Yellow
}

# Step 2: Install dependencies (skip pyarrow build issues by using pre-built wheels)
Write-Host ""
Write-Host "Step 2: Installing dependencies..." -ForegroundColor Yellow
Write-Host "This may take a few minutes..." -ForegroundColor Gray

# Install streamlit first (it will pull in dependencies)
& $pythonExe -m pip install streamlit --no-build-isolation

# Install other packages
& $pythonExe -m pip install pandas sqlalchemy

if ($LASTEXITCODE -eq 0) {
    Write-Host "Dependencies installed successfully!" -ForegroundColor Green
} else {
    Write-Host "Some dependencies may have failed. Trying alternative installation..." -ForegroundColor Yellow
    # Try installing without pyarrow dependency issues
    & $pythonExe -m pip install streamlit pandas sqlalchemy --no-deps
    & $pythonExe -m pip install streamlit pandas sqlalchemy
}

# Step 3: Initialize database
Write-Host ""
Write-Host "Step 3: Initializing database..." -ForegroundColor Yellow
& $pythonExe db_init.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "Database initialized successfully!" -ForegroundColor Green
} else {
    Write-Host "Error initializing database!" -ForegroundColor Red
    exit 1
}

# Success!
Write-Host ""
Write-Host "=== Setup Complete! ===" -ForegroundColor Green
Write-Host ""
Write-Host "To run the application, use:" -ForegroundColor Cyan
Write-Host "  $pythonExe -m streamlit run app.py" -ForegroundColor White
Write-Host ""



