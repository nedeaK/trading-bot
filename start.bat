@echo off
echo Starting SMC AI Trading Analyst...
echo.
echo [1/2] Starting Python API server on http://localhost:7474
start "Bot Server" cmd /k "py -m uvicorn server.main:app --reload --port 7474"
timeout /t 2 /nobreak >nul
echo.
echo [2/2] Starting Sidebar UI on http://localhost:5173
start "Sidebar" cmd /k "cd sidebar && npm run dev"
echo.
echo ======================================================
echo  Sidebar:  http://localhost:5173
echo  API:      http://localhost:7474
echo  Docs:     http://localhost:7474/docs
echo ======================================================
echo.
echo For Chrome Extension:
echo   1. Go to chrome://extensions
echo   2. Enable Developer Mode
echo   3. Load unpacked ^> select the 'extension' folder
echo.
pause
