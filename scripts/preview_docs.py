from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto("http://localhost:3000/docs", wait_until="networkidle")
    page.screenshot(path="d:/KnowledgeVault/Project/FloodShield/docs_page_preview.png")
    browser.close()
    print("Screenshot saved successfully!")
