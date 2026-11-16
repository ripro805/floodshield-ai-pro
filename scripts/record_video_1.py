import os
import subprocess
import time
from playwright.sync_api import sync_playwright

html_file = os.path.abspath("scripts/logo_animation.html")
temp_dir = os.path.abspath("screen record/temp_v1")
os.makedirs(temp_dir, exist_ok=True)
final_mp4 = os.path.abspath("screen record/1_logo_animation_5s.mp4")
ffmpeg_path = r"C:\Program Files (x86)\Labcenter Electronics\Proteus 8 Professional\BIN\ffmpeg.exe"

print("Starting Video 1 recording (5 seconds)...")

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        headless=True,
        args=["--autoplay-policy=no-user-gesture-required"]
    )
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        record_video_dir=temp_dir,
        record_video_size={"width": 1920, "height": 1080}
    )
    page = context.new_page()
    page.goto(f"file:///{html_file.replace(os.sep, '/')}")
    
    # Wait for exactly 5.2 seconds
    time.sleep(5.2)
    
    context.close()
    video_path = page.video.path()
    browser.close()

print(f"Captured webm: {video_path}")

# Convert to 5s MP4 using ffmpeg
cmd = [
    ffmpeg_path,
    "-y",
    "-i", video_path,
    "-t", "5.0",
    "-r", "30",
    "-c:v", "libx264",
    "-pix_fmt", "yuv420p",
    "-preset", "fast",
    final_mp4
]
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
if res.returncode == 0:
    print(f"Successfully generated {final_mp4} (Duration: 5s, 1080p)")
else:
    print("FFmpeg error:", res.stderr.decode(errors="ignore"))

# Cleanup temp webm
if os.path.exists(temp_dir):
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)
