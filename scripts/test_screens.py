import urllib.request
import json
import time
from playwright.sync_api import sync_playwright

# 1. Login
req = urllib.request.Request(
    'https://floodshield-ai-pro.vercel.app/backend-api/auth/login',
    data=json.dumps({'email': 'test.admin@floodshield-demo.com', 'password': 'UGT9Tja4RiAAD3'}).encode(),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req) as res:
    token = json.loads(res.read())['access_token']

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless=True)
    context = browser.new_context(viewport={'width': 1920, 'height': 1080})
    page = context.new_page()

    # Pre-populate token
    page.goto('https://floodshield-ai-pro.vercel.app/login')
    page.evaluate("(tok) => localStorage.setItem('floodshield_token', tok)", token)

    routes = [
        ('dashboard', 'https://floodshield-ai-pro.vercel.app/dashboard'),
        ('feni_assessment', 'https://floodshield-ai-pro.vercel.app/dashboard/Feni'),
        ('citizen', 'https://floodshield-ai-pro.vercel.app/dashboard/citizen'),
        ('field', 'https://floodshield-ai-pro.vercel.app/dashboard/field'),
        ('hospital', 'https://floodshield-ai-pro.vercel.app/dashboard/hospital'),
        ('ngo', 'https://floodshield-ai-pro.vercel.app/dashboard/ngo'),
    ]

    for name, url in routes:
        page.goto(url, wait_until='networkidle')
        page.wait_for_timeout(2000)
        page.screenshot(path=f'screen record/test_{name}.png')
        print(f'Captured {name}')

    browser.close()
