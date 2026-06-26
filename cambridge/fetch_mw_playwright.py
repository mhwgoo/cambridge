# playwright._impl._errors.Error: BrowserType.launch: Executable doesn't exist at /Users/kate/Library/Caches/ms-playwright/chromium-1223/chrome-mac-x64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing

import time, random, asyncio
from playwright.async_api import async_playwright, Playwright

async def human_move_and_click(page, x, y, steps=10):
    sx = x + random.uniform(-120, 120)
    sy = y + random.uniform(-60, 60)
    for i in range(steps):
        t = (i + 1) / steps
        ix = sx + (x - sx) * t + random.uniform(-1, 1)
        iy = sy + (y - sy) * t + random.uniform(-1, 1)
        await page.mouse.move(ix, iy)
        time.sleep(random.uniform(0.01, 0.04))
    time.sleep(random.uniform(0.03, 0.12))
    await page.mouse.click(x, y, delay=int(random.uniform(20, 80)))

async def fetch_page(url):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, args=[
            "--disable-blink-features=AutomationControlled",
            "--window-size=1366,768"
        ])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            viewport={"width":1366,"height":768}
        )
        page = await context.new_page()
        await page.goto(url, timeout=60000)
        # wait for iframe
        iframe_el = None
        for _ in range(40):
            iframe_el = await page.query_selector("iframe")
            if iframe_el:
                src = await iframe_el.get_attribute("src") or ""
                if "cloudflare" in src or "cf" in src:
                    break
            time.sleep(0.25)
        if not iframe_el:
            iframe_el = await page.query_selector("iframe")
        if not iframe_el:
            await browser.close(); raise SystemExit("No iframe found")
        box = await iframe_el.bounding_box()
        if not box:
            await browser.close(); raise SystemExit("No iframe box")
        cx = box["x"] + box["width"]/2
        cy = box["y"] + box["height"]/2
        await human_move_and_click(page, cx, cy, steps=10)
        await page.wait_for_timeout(9000)
        await browser.close()
        return await page.content()
