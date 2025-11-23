# Quick Install Script for Medicine Donation Project
# This script installs dependencies using pre-built wheels

Write-Host "=== Installing Dependencies ===" -ForegroundColor Cyan

# Find Python
$pythonCmd = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCmd = "py"
} else {
    # Try to find Python in common locations
    $pythonPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "C:\Python*\python.exe"
    )
    
    foreach ($path in $pythonPaths) {
        if (Test-Path $path) {
            $pythonCmd = $path
            break
        }
    }
    
    if (-not $pythonCmd) {
        Write-Host "ERROR: Python not found!" -ForegroundColor Red
        Write-Host "Please install Python from https://www.python.org/downloads/" -ForegroundColor Yellow
        Write-Host "Make sure to check 'Add Python to PATH' during installation." -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "Using Python: $pythonCmd" -ForegroundColor Green

# Upgrade pip
Write-Host "`nUpgrading pip..." -ForegroundColor Yellow
& $pythonCmd -m pip install --upgrade pip --quiet

# Install packages one by one, using only pre-built wheels
Write-Host "`nInstalling packages (using pre-built wheels only)..." -ForegroundColor Yellow

$packages = @("streamlit", "pandas", "sqlalchemy")

foreach ($package in $packages) {
    Write-Host "Installing $package..." -ForegroundColor Cyan
    & $pythonCmd -m pip install $package --only-binary :all: --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Warning: $package installation had issues, trying without --only-binary..." -ForegroundColor Yellow
        & $pythonCmd -m pip install $package --quiet
    }
}

Write-Host "`n=== Installation Complete! ===" -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host "  1. Initialize database: $pythonCmd db_init.py" -ForegroundColor White
Write-Host "  2. Run application: $pythonCmd -m streamlit run app.py" -ForegroundColor White



