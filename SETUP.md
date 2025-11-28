# Argos Platform - Setup Guide

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Git (to clone the repository)

## Installation Steps

### 1. Clone or Copy the Project

```bash
# If using git
git clone <repository-url>
cd argos-platform

# Or copy the project folder to your machine
```

### 2. Create Virtual Environment

```bash
# Create a new virtual environment
python3 -m venv venv

# Activate the virtual environment
# On Linux/Mac:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Upgrade pip first
pip install --upgrade pip setuptools wheel

# Install core dependencies
pip install grpcio grpcio-tools fastapi uvicorn pydantic sqlalchemy

# Optional: Install all dependencies from requirements.txt
# Note: Some packages like tensorflow may take time to install
pip install -r requirements.txt
```

### 4. Verify Installation

```bash
# Check Python version
python --version

# Check if packages are installed
pip list | grep -E "(grpcio|fastapi|uvicorn)"
```

## Running the Project

### Option 1: Run Demo Mode (Recommended for Testing)

```bash
# Activate virtual environment first
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Run demo
python -m argos.main --demo
```

### Option 2: Run Full Server

```bash
# Activate virtual environment first
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Run with custom ports (change if ports are in use)
python -m argos.main --grpc-port 50052 --rest-port 8888
```

The server will start with:
- **gRPC API**: `localhost:50052`
- **REST API**: `http://localhost:8888`
- **API Documentation**: `http://localhost:8888/docs`

### Option 3: Run in Background

```bash
# Linux/Mac
source venv/bin/activate
nohup python -m argos.main --grpc-port 50052 --rest-port 8888 > argos.log 2>&1 &

# Check if running
ps aux | grep "python -m argos.main"

# View logs
tail -f argos.log

# Stop the server
pkill -f "python -m argos.main"
```

```bash
# Windows (PowerShell)
venv\Scripts\activate
Start-Process python -ArgumentList "-m", "argos.main", "--grpc-port", "50052", "--rest-port", "8888" -WindowStyle Hidden
```

## Testing the API

### Using curl

```bash
# Health check
curl http://localhost:8888/health

# Get statistics
curl http://localhost:8888/statistics

# Create a student
curl -X POST http://localhost:8888/students \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@university.edu",
    "student_id": "S12345",
    "grade_level": "freshman"
  }'

# List students
curl http://localhost:8888/students
```

### Using Browser

Open your browser and go to:
- API Documentation: `http://localhost:8888/docs`
- Alternative Docs: `http://localhost:8888/redoc`

## Troubleshooting

### Port Already in Use

If you get "address already in use" error:

```bash
# Check what's using the port
# Linux/Mac:
lsof -i :8888
netstat -tuln | grep 8888

# Windows:
netstat -ano | findstr :8888

# Use different ports
python -m argos.main --grpc-port 50053 --rest-port 9999
```

### Missing Dependencies

```bash
# If you get import errors, install missing packages
pip install <package-name>

# Or reinstall all dependencies
pip install -r requirements.txt
```

### Python Version Issues

```bash
# Check Python version (needs 3.8+)
python --version

# If using older Python, upgrade or use python3
python3 -m venv venv
source venv/bin/activate
python3 -m argos.main --demo
```

### Virtual Environment Issues

```bash
# Deactivate current environment
deactivate

# Remove old environment
rm -rf venv

# Create fresh environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install grpcio grpcio-tools fastapi uvicorn pydantic sqlalchemy
```

## Quick Start Commands (Copy-Paste)

### Linux/Mac

```bash
# Complete setup and run
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install grpcio grpcio-tools fastapi uvicorn pydantic sqlalchemy
python -m argos.main --demo
```

### Windows (PowerShell)

```powershell
# Complete setup and run
python -m venv venv
venv\Scripts\activate
pip install --upgrade pip setuptools wheel
pip install grpcio grpcio-tools fastapi uvicorn pydantic sqlalchemy
python -m argos.main --demo
```

## Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests
pytest tests/

# Run with coverage
pytest tests/ --cov=argos --cov-report=html
```

## Stopping the Server

### If running in foreground
Press `Ctrl+C`

### If running in background (Linux/Mac)
```bash
# Find the process
ps aux | grep "python -m argos.main"

# Kill by process ID
kill <PID>

# Or kill all
pkill -f "python -m argos.main"
```

### If running in background (Windows)
```powershell
# Find the process
Get-Process python

# Stop by name
Stop-Process -Name python
```

## Additional Resources

- Project README: `README.md`
- API Documentation: Available at `/docs` endpoint when server is running
- Demo Scenarios: Check `demo/demo_scenario.py` for examples
