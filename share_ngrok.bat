@echo off
title FloodShield AI - Ngrok Public Tunnel
echo ===================================================
echo   FloodShield AI - Sharing via Ngrok Tunnel
echo ===================================================
echo Starting Ngrok Tunnel for Frontend (port 3000)...
echo.
echo Look for the Forwarding link (https://....ngrok-free.app) below!
echo Share that link with your teammates.
echo Press Ctrl+C anytime to stop sharing.
echo ===================================================
echo.
"C:\Users\rifat\AppData\Local\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe" http 3000
pause
