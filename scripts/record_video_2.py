import os
import subprocess
import time
import json
import urllib.request
from playwright.sync_api import sync_playwright

temp_dir = os.path.abspath("screen record/temp_v2")
os.makedirs(temp_dir, exist_ok=True)
final_mp4 = os.path.abspath("screen record/2_homepage_dashboard_7s.mp4")
ffmpeg_path = r"C:\Program Files (x86)\Labcenter Electronics\Proteus 8 Professional\BIN\ffmpeg.exe"

# 1. Obtain admin token
req = urllib.request.Request(
    'https://floodshield-ai-pro.vercel.app/backend-api/auth/login',
    data=json.dumps({'email': 'test.admin@floodshield-demo.com', 'password': 'UGT9Tja4RiAAD3'}).encode(),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req) as res:
    token = json.loads(res.read())['access_token']

print("Starting Video 2 recording (Homepage & Main Dashboard - 7s)...")

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        headless=True
    )
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        record_video_dir=temp_dir,
        record_video_size={"width": 1920, "height": 1080}
    )
    page = context.new_page()

    # Pre-inject token so dashboard is authenticated immediately
    page.goto('https://floodshield-ai-pro.vercel.app/login', wait_until='domcontentloaded')
    page.evaluate("(tok) => localStorage.setItem('floodshield_token', tok)", token)
    page.evaluate("() => sessionStorage.setItem('fs_splash_seen', 'true')")

    # --- PART 1: Homepage (3.5s) ---
    page.goto('https://floodshield-ai-pro.vercel.app', wait_until='networkidle')
    page.wait_for_timeout(500)
    
    # Smooth scroll down homepage to show features & stats
    t_start = time.time()
    while time.time() - t_start < 3.0:
        page.mouse.wheel(0, 150)
        time.sleep(0.15)
        page.mouse.move(960 + 50 * (time.time() - t_start), 540)

    # --- PART 2: Main Dashboard (3.5s) ---
    page.goto('https://floodshield-ai-pro.vercel.app/dashboard', wait_until='networkidle')
    page.wait_for_timeout(500)

    # Hover and explore map & cards
    t_dash = time.time()
    positions = [
        (650, 480), # Map area
        (720, 520), # District Feni
        (1450, 250), # Check flood risk card
        (1450, 450), # Live weather card
        (1450, 650), # Environmental monitoring card
    ]
    for x, y in positions:
        page.mouse.move(x, y, steps=10)
        time.sleep(0.6)

    context.close()
    video_path = page.video.path()
    browser.close()

print(f"Captured webm: {video_path}")

# Convert to exact 7.0s MP4
cmd = [
    ffmpeg_path,
    "-y",
    "-i", video_path,
    "-t", "7.0",
    "-r", "30",
    "-c:v", "libx264",
    "-pix_fmt", "yuv420p",
    "-preset", "fast",
    final_mp4
]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if res.returncode == 0:
    print(f"Successfully generated {final_mp4} (Duration: 7s, 1080p)")
else:
    print("FFmpeg error:", res.stderr.decode(errors="ignore"))

# Cleanup temp
import shutil
shutil.rmtree(temp_dir, ignore_errors=True)
