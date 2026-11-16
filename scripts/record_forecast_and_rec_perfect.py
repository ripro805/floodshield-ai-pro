import os
import subprocess
import time
import json
import urllib.request
import shutil
from playwright.sync_api import sync_playwright

output_dir = os.path.abspath("screen record")
os.makedirs(output_dir, exist_ok=True)
ffmpeg_path = r"C:\Program Files (x86)\Labcenter Electronics\Proteus 8 Professional\BIN\ffmpeg.exe"

# 1. Login to get token
req = urllib.request.Request(
    'https://floodshield-ai-pro.vercel.app/backend-api/auth/login',
    data=json.dumps({'email': 'test.admin@floodshield-demo.com', 'password': 'UGT9Tja4RiAAD3'}).encode(),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req) as res:
    token = json.loads(res.read())['access_token']

print("Token obtained successfully.")

def convert_to_mp4(webm_path, duration_sec, final_mp4_path):
    cmd = [
        ffmpeg_path,
        "-y",
        "-i", webm_path,
        "-t", f"{duration_sec:.1f}",
        "-r", "30",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        final_mp4_path
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode == 0:
        print(f"  [OK] Generated {os.path.basename(final_mp4_path)} ({duration_sec}s, 1080p)")
    else:
        print(f"  [ERR] FFmpeg error: {res.stderr.decode(errors='ignore')}")

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        headless=True
    )

    # =========================================================================
    # VIDEO 5: 10 sec - LSTM Forecast বা Future Trend Chart দেখাবে
    # Dedicated page: /dashboard/reports
    # =========================================================================
    print("\n--- Recording 5 (Proper Dedicated LSTM Forecast Chart - 10s) ---")
    tmp_v5 = os.path.join(output_dir, "temp_rec5_new")
    os.makedirs(tmp_v5, exist_ok=True)
    ctx5 = browser.new_context(viewport={"width": 1920, "height": 1080}, record_video_dir=tmp_v5, record_video_size={"width": 1920, "height": 1080})
    page5 = ctx5.new_page()
    page5.goto('https://floodshield-ai-pro.vercel.app/login', wait_until='domcontentloaded')
    page5.evaluate("(tok) => localStorage.setItem('floodshield_token', tok)", token)
    page5.evaluate("() => sessionStorage.setItem('fs_splash_seen', 'true')")

    page5.goto('https://floodshield-ai-pro.vercel.app/dashboard/reports', wait_until='networkidle')
    page5.wait_for_timeout(1000)

    # 0s - 2.5s: Hover over district dropdown and move to Run Forecast button
    page5.mouse.move(500, 220, steps=20)
    page5.wait_for_timeout(600)
    btn_forecast = page5.query_selector('button:has-text("Run Forecast")')
    fb_box = btn_forecast.bounding_box()
    page5.mouse.move(fb_box['x'] + fb_box['width'] / 2, fb_box['y'] + fb_box['height'] / 2, steps=20)
    page5.wait_for_timeout(600)

    # 2.5s: Click Run Forecast
    page5.mouse.click(fb_box['x'] + fb_box['width'] / 2, fb_box['y'] + fb_box['height'] / 2)
    # Wait for forecast cards (+142, +198) and chart to render
    page5.wait_for_timeout(1800)

    # 4.3s - 10.5s: Interactively inspect the chart with tooltips
    # Chart area is approximately x=450 to x=1450, y=360 to y=520
    chart_points = [
        (480, 420),   # W-8
        (620, 430),   # W-6
        (780, 410),   # W-4
        (940, 390),   # W-2
        (1080, 370),  # W-1 (Forecast separator)
        (1220, 350),  # W+1 (7d forecast point)
        (1360, 330),  # W+2 (14d forecast point)
    ]
    for x, y in chart_points:
        page5.mouse.move(x, y, steps=12)
        page5.wait_for_timeout(800)

    ctx5.close()
    convert_to_mp4(page5.video.path(), 10.0, os.path.join(output_dir, "5_lstm_forecast_future_trend_10s.mp4"))
    shutil.rmtree(tmp_v5, ignore_errors=True)

    # =========================================================================
    # VIDEO 6: 8 sec - Recommendation module-এর output দেখাবে
    # Dedicated page: /dashboard/resources (tab: AI Recommendations)
    # =========================================================================
    print("\n--- Recording 6 (Proper Dedicated AI Recommendation Module - 8s) ---")
    tmp_v6 = os.path.join(output_dir, "temp_rec6_new")
    os.makedirs(tmp_v6, exist_ok=True)
    ctx6 = browser.new_context(viewport={"width": 1920, "height": 1080}, record_video_dir=tmp_v6, record_video_size={"width": 1920, "height": 1080})
    page6 = ctx6.new_page()
    page6.goto('https://floodshield-ai-pro.vercel.app/login', wait_until='domcontentloaded')
    page6.evaluate("(tok) => localStorage.setItem('floodshield_token', tok)", token)
    page6.evaluate("() => sessionStorage.setItem('fs_splash_seen', 'true')")

    page6.goto('https://floodshield-ai-pro.vercel.app/dashboard/resources', wait_until='networkidle')
    page6.wait_for_timeout(800)

    # Select Feni and Critical risk level
    page6.select_option('#resources-district', 'Feni')
    page6.wait_for_timeout(300)
    page6.select_option('#resources-risk', 'Critical')
    page6.wait_for_timeout(400)

    # 0s - 2.0s: Move to Get Recommendations button
    btn_rec = page6.query_selector('button:has-text("Get Recommendations")')
    rb_box = btn_rec.bounding_box()
    page6.mouse.move(rb_box['x'] + rb_box['width'] / 2, rb_box['y'] + rb_box['height'] / 2, steps=15)
    page6.wait_for_timeout(500)

    # 2.0s: Click Get Recommendations
    page6.mouse.click(rb_box['x'] + rb_box['width'] / 2, rb_box['y'] + rb_box['height'] / 2)
    # Results appear with RecommendationCard and HospitalStockCard
    page6.wait_for_timeout(1500)

    # 3.5s - 8.5s: Move smoothly over the AI recommendations, beds occupancy bar, and supply stock
    rec_points = [
        (650, 390),  # AI Recommendations - Feni header & CRITICAL badge
        (650, 440),  # Bed capacity (2076 beds) & animated occupancy progress bar
        (680, 520),  # Checklist: Deploy Emergency Medical Team
        (680, 560),  # Checklist: Prepare Emergency Shelter
        (680, 600),  # Checklist: Distribute Emergency Kits & ORS
        (1100, 440), # Hospital Stock Card (ORS & IV Saline gauges)
    ]
    for x, y in rec_points:
        page6.mouse.move(x, y, steps=15)
        page6.wait_for_timeout(750)

    ctx6.close()
    convert_to_mp4(page6.video.path(), 8.0, os.path.join(output_dir, "6_recommendation_module_8s.mp4"))
    shutil.rmtree(tmp_v6, ignore_errors=True)

    browser.close()

print("\nFinished generating dedicated Video 5 and Video 6!")
