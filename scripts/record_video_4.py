import os
import subprocess
import time
import json
import urllib.request
import shutil
from playwright.sync_api import sync_playwright

temp_dir = os.path.abspath("screen record/temp_v4")
os.makedirs(temp_dir, exist_ok=True)
final_mp4 = os.path.abspath("screen record/4_citizen_health_hospital_ngo_10s.mp4")
ffmpeg_path = r"C:\Program Files (x86)\Labcenter Electronics\Proteus 8 Professional\BIN\ffmpeg.exe"

# 1. Login
req = urllib.request.Request(
    'https://floodshield-ai-pro.vercel.app/backend-api/auth/login',
    data=json.dumps({'email': 'test.admin@floodshield-demo.com', 'password': 'UGT9Tja4RiAAD3'}).encode(),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req) as res:
    token = json.loads(res.read())['access_token']

print("Starting Video 4 recording (Citizen, Health Worker, Hospital, NGO - 10s)...")

roles = [
    {
        "name": "citizen",
        "url": "https://floodshield-ai-pro.vercel.app/dashboard/citizen/reports",
        "duration": 2.5,
        "actions": [
            (600, 240, 0.4),  # Alert banner
            (650, 420, 0.5),  # Incident category
            (850, 520, 0.6),  # Report form
            (700, 680, 0.5),
        ]
    },
    {
        "name": "field",
        "url": "https://floodshield-ai-pro.vercel.app/dashboard/field",
        "duration": 2.5,
        "actions": [
            (550, 260, 0.4),  # Assigned Tasks
            (800, 320, 0.5),  # Offline-safe field logging
            (1100, 420, 0.5), # Field task card
            (600, 580, 0.5),  # Record visit
        ]
    },
    {
        "name": "hospital",
        "url": "https://floodshield-ai-pro.vercel.app/dashboard/hospital",
        "duration": 2.5,
        "actions": [
            (600, 280, 0.4),  # Bed capacity
            (850, 320, 0.5),  # Occupancy meter
            (1150, 350, 0.5), # Pharmacy / ORS stock
            (800, 600, 0.5),  # Surge indicators
        ]
    },
    {
        "name": "ngo",
        "url": "https://floodshield-ai-pro.vercel.app/dashboard/ngo",
        "duration": 2.5,
        "actions": [
            (580, 270, 0.4),  # Relief Campaigns
            (900, 300, 0.5),  # AI-Assisted Allocation
            (1200, 400, 0.5), # Active distribution points
            (750, 550, 0.5),  # Warehouse inventory
        ]
    }
]

segment_files = []

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        headless=True
    )

    for i, role in enumerate(roles):
        sub_dir = os.path.join(temp_dir, f"sub_{i}")
        os.makedirs(sub_dir, exist_ok=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=sub_dir,
            record_video_size={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        page.goto('https://floodshield-ai-pro.vercel.app/login', wait_until='domcontentloaded')
        page.evaluate("(tok) => localStorage.setItem('floodshield_token', tok)", token)
        page.evaluate("() => sessionStorage.setItem('fs_splash_seen', 'true')")

        page.goto(role["url"], wait_until='networkidle')
        page.wait_for_timeout(1000)

        # Smooth interactive movement
        for x, y, delay in role["actions"]:
            page.mouse.move(x, y, steps=15)
            page.wait_for_timeout(int(delay * 1000))

        context.close()
        vpath = page.video.path()
        out_seg = os.path.join(temp_dir, f"seg_{i}.mp4")

        # Trim each to exact 2.5s
        cmd_trim = [
            ffmpeg_path,
            "-y",
            "-i", vpath,
            "-t", "2.5",
            "-r", "30",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            out_seg
        ]
        subprocess.run(cmd_trim, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        segment_files.append(out_seg)
        print(f"Recorded segment {i+1}/4: {role['name']} (2.5s)")

    browser.close()

# Create concat list
concat_list_path = os.path.join(temp_dir, "concat.txt")
with open(concat_list_path, "w", encoding="utf-8") as f:
    for sf in segment_files:
        escaped = sf.replace("\\", "/")
        f.write(f"file '{escaped}'\n")

# Concatenate all 4 segments into final 10.0s video
cmd_concat = [
    ffmpeg_path,
    "-y",
    "-f", "concat",
    "-safe", "0",
    "-i", concat_list_path,
    "-c", "copy",
    final_mp4
]
res = subprocess.run(cmd_concat, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if res.returncode == 0:
    print(f"Successfully generated {final_mp4} (Duration: 10s, 1080p)")
else:
    print("FFmpeg concat error:", res.stderr.decode(errors="ignore"))

shutil.rmtree(temp_dir, ignore_errors=True)
