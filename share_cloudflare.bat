@echo off
title FloodShield AI - Cloudflare Public Tunnel
echo ===================================================
echo   FloodShield AI - Sharing via Cloudflare Tunnel
echo ===================================================
echo Starting Cloudflare Tunnel for Frontend (port 3000)...
echo.
echo Look for the link ending in .trycloudflare.com below!
echo Share that link with your teammates.
echo Press Ctrl+C anytime to stop sharing.
echo ===================================================
echo.
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:3000
pause
