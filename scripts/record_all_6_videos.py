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
    # VIDEO 1: 8 sec - Homepage থেকে Dashboard-এ প্রবেশ করবে
    # =========================================================================
    print("\n--- Recording 1: Homepage to Dashboard (8s) ---")
    tmp_v1 = os.path.join(output_dir, "temp_rec1")
    os.makedirs(tmp_v1, exist_ok=True)
    ctx1 = browser.new_context(viewport={"width": 1920, "height": 1080}, record_video_dir=tmp_v1, record_video_size={"width": 1920, "height": 1080})
    page1 = ctx1.new_page()
    page1.goto('https://floodshield-ai-pro.vercel.app/login', wait_until='domcontentloaded')
    page1.evaluate("(tok) => localStorage.setItem('floodshield_token', tok)", token)
    page1.evaluate("() => sessionStorage.setItem('fs_splash_seen', 'true')")

    page1.goto('https://floodshield-ai-pro.vercel.app', wait_until='networkidle')
    page1.wait_for_timeout(500)
    # 0s - 3.2s: Explore hero & move to View Dashboard button
    page1.mouse.move(700, 380, steps=20)
    page1.wait_for_timeout(800)
    dash_btn = page1.query_selector('a[href="/dashboard"]:has-text("View Dashboard")') or page1.query_selector('a[href="/dashboard"]')
    box = dash_btn.bounding_box() if dash_btn else {'x': 250, 'y': 520, 'width': 160, 'height': 45}
    btn_x = box['x'] + box['width'] / 2
    btn_y = box['y'] + box['height'] / 2
    page1.mouse.move(btn_x, btn_y, steps=25)
    page1.wait_for_timeout(1000)

    # Click View Dashboard
    page1.mouse.click(btn_x, btn_y)
    page1.wait_for_timeout(3500)
    page1.mouse.move(960, 540, steps=20)
    page1.wait_for_timeout(1000)

    ctx1.close()
    convert_to_mp4(page1.video.path(), 8.0, os.path.join(output_dir, "1_homepage_to_dashboard_8s.mp4"))
    shutil.rmtree(tmp_v1, ignore_errors=True)

    # =========================================================================
    # VIDEO 2: 10 sec - Bangladesh map থেকে District/Location নির্বাচন করবে
    # =========================================================================
    print("\n--- Recording 2: Map District Selection (10s) ---")
    tmp_v2 = os.path.join(output_dir, "temp_rec2")
    os.makedirs(tmp_v2, exist_ok=True)
    ctx2 = browser.new_context(viewport={"width": 1920, "height": 1080}, record_video_dir=tmp_v2, record_video_size={"width": 1920, "height": 1080})
    page2 = ctx2.new_page()
    page2.goto('https://floodshield-ai-pro.vercel.app/login', wait_until='domcontentloaded')
    page2.evaluate("(tok) => localStorage.setItem('floodshield_token', tok)", token)
    page2.evaluate("() => sessionStorage.setItem('fs_splash_seen', 'true')")

    page2.goto('https://floodshield-ai-pro.vercel.app/dashboard', wait_until='networkidle')
    page2.wait_for_timeout(1000)

    # 0s - 4.5s: Explore Bangladesh map hovering over various districts
    map_hovers = [
        (650, 400), # Center/Dhaka region
        (780, 320), # Sylhet region
        (560, 300), # Rangpur / Kurigram
        (720, 520), # Chittagong / Feni
    ]
    for x, y in map_hovers:
        page2.mouse.move(x, y, steps=15)
        page2.wait_for_timeout(800)

    # 4.5s - 7.0s: Move to District Dropdown in side panel and select Sylhet
    sel_box = page2.query_selector('#district-select').bounding_box()
    page2.mouse.move(sel_box['x'] + 50, sel_box['y'] + 15, steps=20)
    page2.wait_for_timeout(500)
    page2.select_option('#district-select', 'Sylhet')
    page2.wait_for_timeout(1500)

    # 7.0s - 10.5s: Now select Feni to show flyTo animation and live telemetry update
    page2.select_option('#district-select', 'Feni')
    page2.wait_for_timeout(1200)
    page2.mouse.move(680, 500, steps=20)
    page2.wait_for_timeout(1800)

    ctx2.close()
    convert_to_mp4(page2.video.path(), 10.0, os.path.join(output_dir, "2_map_district_selection_10s.mp4"))
    shutil.rmtree(tmp_v2, ignore_errors=True)

    # =========================================================================
    # VIDEO 3: 12 sec - Flood Prediction-এর input দেবে এবং result দেখাবে
    # =========================================================================
    print("\n--- Recording 3: Flood Prediction Input & Result (12s) ---")
    tmp_v3 = os.path.join(output_dir, "temp_rec3")
    os.makedirs(tmp_v3, exist_ok=True)
    ctx3 = browser.new_context(viewport={"width": 1920, "height": 1080}, record_video_dir=tmp_v3, record_video_size={"width": 1920, "height": 1080})
    page3 = ctx3.new_page()
    page3.goto('https://floodshield-ai-pro.vercel.app/login', wait_until='domcontentloaded')
    page3.evaluate("(tok) => localStorage.setItem('floodshield_token', tok)", token)
    page3.evaluate("() => sessionStorage.setItem('fs_splash_seen', 'true')")

    page3.goto('https://floodshield-ai-pro.vercel.app/dashboard', wait_until='networkidle')
    page3.wait_for_timeout(1000)

    # 0s - 2.5s: Hover around Quick Flood Check card
    page3.mouse.move(1500, 260, steps=20)
    page3.wait_for_timeout(800)

    # 2.5s - 5.5s: Move to slider and adjust value smoothly
    slider_box = page3.query_selector('#river-level').bounding_box()
    page3.mouse.move(slider_box['x'] + 50, slider_box['y'] + 10, steps=15)
    page3.wait_for_timeout(500)
    # Simulate slider dragging to 9.8m
    for v in [6.0, 7.2, 8.5, 9.8]:
        page3.evaluate(f"() => {{ const s = document.querySelector('#river-level'); s.value = {v}; s.dispatchEvent(new Event('input', {{bubbles: true}})); s.dispatchEvent(new Event('change', {{bubbles: true}})); }}")
        page3.mouse.move(slider_box['x'] + int((v / 15.0) * slider_box['width']), slider_box['y'] + 10, steps=8)
        page3.wait_for_timeout(400)

    # 5.5s - 7.0s: Move to "Check Flood Risk" button and click
    btn_box = page3.query_selector('button:has-text("Check Flood Risk")').bounding_box()
    page3.mouse.move(btn_box['x'] + btn_box['width'] / 2, btn_box['y'] + btn_box['height'] / 2, steps=15)
    page3.wait_for_timeout(500)
    page3.mouse.click(btn_box['x'] + btn_box['width'] / 2, btn_box['y'] + btn_box['height'] / 2)

    # 7.0s - 13.0s: Show "Predicting…" spinner then animated 3D gauge, Probability %, and Risk badge
    page3.wait_for_timeout(2000)
    page3.mouse.move(1420, 520, steps=15) # Gauge & prob area
    page3.wait_for_timeout(1500)
    page3.mouse.move(1550, 530, steps=15) # Risk badge & importance
    page3.wait_for_timeout(2500)

    ctx3.close()
    convert_to_mp4(page3.video.path(), 12.0, os.path.join(output_dir, "3_flood_prediction_input_output_12s.mp4"))
    shutil.rmtree(tmp_v3, ignore_errors=True)

    # =========================================================================
    # VIDEO 4: 12 sec - Disease Risk Prediction-এর input ও output দেখাবে
    # =========================================================================
    print("\n--- Recording 4: Disease Risk Prediction Input & Output (12s) ---")
    tmp_v4 = os.path.join(output_dir, "temp_rec4")
    os.makedirs(tmp_v4, exist_ok=True)
    ctx4 = browser.new_context(viewport={"width": 1920, "height": 1080}, record_video_dir=tmp_v4, record_video_size={"width": 1920, "height": 1080})
    page4 = ctx4.new_page()
    page4.goto('https://floodshield-ai-pro.vercel.app/login', wait_until='domcontentloaded')
    page4.evaluate("(tok) => localStorage.setItem('floodshield_token', tok)", token)
    page4.evaluate("() => sessionStorage.setItem('fs_splash_seen', 'true')")

    page4.goto('https://floodshield-ai-pro.vercel.app/dashboard/Feni', wait_until='networkidle')
    page4.wait_for_timeout(1000)

    # 0s - 3.5s: Top environmental inputs (Humidity, River level, Wind, Weeks of history)
    page4.mouse.move(500, 220, steps=20)
    page4.wait_for_timeout(800)
    page4.mouse.move(800, 220, steps=20)
    page4.wait_for_timeout(800)
    page4.mouse.move(1200, 220, steps=20)
    page4.wait_for_timeout(800)

    # 3.5s - 7.5s: Scroll down to Disease Outbreak Risk (Model 2)
    for _ in range(12):
        page4.evaluate("() => window.scrollBy({ top: 35, behavior: 'smooth' })")
        page4.wait_for_timeout(60)
    page4.wait_for_timeout(500)
    # Hover over Disease Outbreak Risk level badge and class probabilities
    page4.mouse.move(600, 480, steps=20)
    page4.wait_for_timeout(1200)
    page4.mouse.move(800, 520, steps=20)
    page4.wait_for_timeout(1000)

    # 7.5s - 13.0s: Scroll to Disease Breakdown (Model 2B) showing dominant disease & 6 diseases
    page4.mouse.move(1250, 480, steps=20)
    page4.wait_for_timeout(1200)
    page4.mouse.move(1400, 560, steps=20)
    page4.wait_for_timeout(2000)

    ctx4.close()
    convert_to_mp4(page4.video.path(), 12.0, os.path.join(output_dir, "4_disease_risk_prediction_12s.mp4"))
    shutil.rmtree(tmp_v4, ignore_errors=True)

    # =========================================================================
    # VIDEO 5: 10 sec - LSTM Forecast বা Future Trend Chart দেখাবে
    # =========================================================================
    print("\n--- Recording 5: LSTM Forecast & Future Trend Chart (10s) ---")
    tmp_v5 = os.path.join(output_dir, "temp_rec5")
    os.makedirs(tmp_v5, exist_ok=True)
    ctx5 = browser.new_context(viewport={"width": 1920, "height": 1080}, record_video_dir=tmp_v5, record_video_size={"width": 1920, "height": 1080})
    page5 = ctx5.new_page()
    page5.goto('https://floodshield-ai-pro.vercel.app/login', wait_until='domcontentloaded')
    page5.evaluate("(tok) => localStorage.setItem('floodshield_token', tok)", token)
    page5.evaluate("() => sessionStorage.setItem('fs_splash_seen', 'true')")

    page5.goto('https://floodshield-ai-pro.vercel.app/dashboard/Feni', wait_until='networkidle')
    page5.wait_for_timeout(1000)

    # 0s - 4.5s: Scroll to 7 / 14-day Forecast (Model 3 LSTM)
    page5.evaluate("() => window.scrollTo({ top: 480, behavior: 'smooth' })")
    page5.wait_for_timeout(700)
    page5.mouse.move(1350, 480, steps=20) # 7-day card
    page5.wait_for_timeout(1200)
    page5.mouse.move(1550, 480, steps=20) # 14-day card
    page5.wait_for_timeout(1200)

    # 4.5s - 10.5s: Scroll further down to the multi-week history / trend section
    page5.evaluate("() => window.scrollTo({ top: 1450, behavior: 'smooth' })")
    page5.wait_for_timeout(800)
    # Click "8-week history" tab
    hist_btn = page5.query_selector('button:has-text("8-week history")')
    if hist_btn:
        hb = hist_btn.bounding_box()
        page5.mouse.move(hb['x'] + hb['width'] / 2, hb['y'] + hb['height'] / 2, steps=15)
        page5.wait_for_timeout(400)
        page5.mouse.click(hb['x'] + hb['width'] / 2, hb['y'] + hb['height'] / 2)
        page5.wait_for_timeout(1200)

    page5.mouse.move(800, 600, steps=20)
    page5.wait_for_timeout(2000)

    ctx5.close()
    convert_to_mp4(page5.video.path(), 10.0, os.path.join(output_dir, "5_lstm_forecast_future_trend_10s.mp4"))
    shutil.rmtree(tmp_v5, ignore_errors=True)

    # =========================================================================
    # VIDEO 6: 8 sec - Recommendation module-এর output দেখাবে
    # =========================================================================
    print("\n--- Recording 6: Recommendation Module Output (8s) ---")
    tmp_v6 = os.path.join(output_dir, "temp_rec6")
    os.makedirs(tmp_v6, exist_ok=True)
    ctx6 = browser.new_context(viewport={"width": 1920, "height": 1080}, record_video_dir=tmp_v6, record_video_size={"width": 1920, "height": 1080})
    page6 = ctx6.new_page()
    page6.goto('https://floodshield-ai-pro.vercel.app/login', wait_until='domcontentloaded')
    page6.evaluate("(tok) => localStorage.setItem('floodshield_token', tok)", token)
    page6.evaluate("() => sessionStorage.setItem('fs_splash_seen', 'true')")

    page6.goto('https://floodshield-ai-pro.vercel.app/dashboard/Feni', wait_until='networkidle')
    page6.wait_for_timeout(1000)

    # 0s - 2.5s: Scroll directly to Recommendation card
    page6.evaluate("() => { const el = Array.from(document.querySelectorAll('h3')).find(h => h.innerText.includes('Recommendation')); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' }); }")
    page6.wait_for_timeout(800)

    # 2.5s - 8.5s: Smooth hover over operational guidelines and action directives
    rec_hovers = [
        (650, 420),
        (850, 460),
        (1100, 500),
        (750, 540),
    ]
    for x, y in rec_hovers:
        page6.mouse.move(x, y, steps=15)
        page6.wait_for_timeout(1100)

    ctx6.close()
    convert_to_mp4(page6.video.path(), 8.0, os.path.join(output_dir, "6_recommendation_module_8s.mp4"))
    shutil.rmtree(tmp_v6, ignore_errors=True)

    browser.close()

print("\nAll 6 videos successfully recorded and processed!")
