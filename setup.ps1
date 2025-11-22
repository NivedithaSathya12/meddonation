# Medicine Donation Project Setup Script
# This script will install Python and set up the project

Write-Host "=== Medicine Donation Project Setup ===" -ForegroundColor Cyan
Write-Host ""

# Check if Python is already installed
Write-Host "Checking for Python installation..." -ForegroundColor Yellow
$pythonInstalled = $false

# Try different Python commands
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonVersion = python --version 2>&1
    Write-Host "Python found: $pythonVersion" -ForegroundColor Green
    $pythonInstalled = $true
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonVersion = py --version 2>&1
    Write-Host "Python found: $pythonVersion" -ForegroundColor Green
    $pythonInstalled = $true
}

if (-not $pythonInstalled) {
    Write-Host "Python is not installed. Installing Python 3.12..." -ForegroundColor Yellow
    Write-Host "This may require administrator privileges." -ForegroundColor Yellow
    Write-Host ""
    
    # Install Python using winget
    try {
        winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
        Write-Host "Python installation initiated. Please wait..." -ForegroundColor Yellow
        Write-Host "After installation completes, you may need to restart your terminal." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Once Python is installed, run this script again or manually run:" -ForegroundColor Cyan
        Write-Host "  pip install -r requirements.txt" -ForegroundColor White
        Write-Host "  python db_init.py" -ForegroundColor White
        Write-Host "  streamlit run app.py" -ForegroundColor White
        exit
    } catch {
        Write-Host "Error installing Python. Please install manually from https://www.python.org/downloads/" -ForegroundColor Red
        Write-Host "Make sure to check 'Add Python to PATH' during installation." -ForegroundColor Yellow
        exit
    }
}

# Refresh PATH to pick up newly installed Python
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

# Determine Python command
$pythonCmd = "python"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    $pythonCmd = "py"
}

Write-Host ""
Write-Host "Installing project dependencies..." -ForegroundColor Yellow
& $pythonCmd -m pip install --upgrade pip
& $pythonCmd -m pip install -r requirements.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host "Dependencies installed successfully!" -ForegroundColor Green
} else {
    Write-Host "Error installing dependencies. Please check the error messages above." -ForegroundColor Red
    exit
}

Write-Host ""
Write-Host "Initializing database..." -ForegroundColor Yellow
& $pythonCmd db_init.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "Database initialized successfully!" -ForegroundColor Green
} else {
    Write-Host "Error initializing database. Please check the error messages above." -ForegroundColor Red
    exit
}

Write-Host ""
Write-Host "=== Setup Complete! ===" -ForegroundColor Green
Write-Host ""
Write-Host "To run the application, use:" -ForegroundColor Cyan
Write-Host "  streamlit run app.py" -ForegroundColor White
Write-Host ""
Write-Host "Would you like to start the application now? (Y/N)" -ForegroundColor Yellow
$response = Read-Host

if ($response -eq "Y" -or $response -eq "y") {
    Write-Host ""
    Write-Host "Starting Streamlit application..." -ForegroundColor Green
    streamlit run app.py
}
