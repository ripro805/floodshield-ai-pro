import os
import subprocess
import time
import json
import urllib.request
import shutil
from playwright.sync_api import sync_playwright

temp_dir = os.path.abspath("screen record/temp_v3")
os.makedirs(temp_dir, exist_ok=True)
final_mp4 = os.path.abspath("screen record/3_flood_disease_prediction_8s.mp4")
ffmpeg_path = r"C:\Program Files (x86)\Labcenter Electronics\Proteus 8 Professional\BIN\ffmpeg.exe"

# 1. Obtain admin token
req = urllib.request.Request(
    'https://floodshield-ai-pro.vercel.app/backend-api/auth/login',
    data=json.dumps({'email': 'test.admin@floodshield-demo.com', 'password': 'UGT9Tja4RiAAD3'}).encode(),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req) as res:
    token = json.loads(res.read())['access_token']

print("Starting Video 3 recording (Flood Prediction & Disease Prediction - 8s)...")

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

    # Inject auth
    page.goto('https://floodshield-ai-pro.vercel.app/login', wait_until='domcontentloaded')
    page.evaluate("(tok) => localStorage.setItem('floodshield_token', tok)", token)
    page.evaluate("() => sessionStorage.setItem('fs_splash_seen', 'true')")

    # Navigate to Feni Detailed Assessment
    page.goto('https://floodshield-ai-pro.vercel.app/dashboard/Feni', wait_until='networkidle')
    page.wait_for_timeout(1000)

    # 0s - 3.5s: Top View (Flood Risk, Water Level, Probability)
    # Move cursor gracefully across the key flood risk cards
    page.mouse.move(500, 380, steps=25)
    page.wait_for_timeout(800)
    page.mouse.move(960, 420, steps=25)
    page.wait_for_timeout(800)
    page.mouse.move(1400, 400, steps=25)
    page.wait_for_timeout(800)

    # 3.5s - 5.5s: Smooth scroll to Disease Outbreak Risk & Disease Breakdown
    # Scroll by steps of 25px
    for _ in range(20):
        page.evaluate("() => window.scrollBy({ top: 25, behavior: 'smooth' })")
        page.wait_for_timeout(80)

    # 5.5s - 8.5s: Explore Disease Breakdown & Forecast chart
    page.mouse.move(600, 450, steps=20)
    page.wait_for_timeout(1000)
    page.mouse.move(1200, 500, steps=20)
    page.wait_for_timeout(1200)

    context.close()
    video_path = page.video.path()
    browser.close()

print(f"Captured webm: {video_path}")

# Convert to exact 8.0s MP4
cmd = [
    ffmpeg_path,
    "-y",
    "-i", video_path,
    "-t", "8.0",
    "-r", "30",
    "-c:v", "libx264",
    "-pix_fmt", "yuv420p",
    "-preset", "fast",
    final_mp4
]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if res.returncode == 0:
    print(f"Successfully generated {final_mp4} (Duration: 8s, 1080p)")
else:
    print("FFmpeg error:", res.stderr.decode(errors="ignore"))

shutil.rmtree(temp_dir, ignore_errors=True)
