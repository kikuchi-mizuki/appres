import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headless=TrueでもOK
        page = await browser.new_page()
        await page.goto("https://www.yyc.co.jp/login")
        await page.screenshot(path="debug.png")
        html = await page.content()
        with open("debug.html", "w", encoding="utf-8") as f:
            f.write(html)
        await browser.close()

asyncio.run(main())