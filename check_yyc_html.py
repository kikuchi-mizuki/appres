from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # headless=False で画面が出る
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.yyc.co.jp/login/")
    input("ブラウザで画面を確認したらEnterを押してください...")
    # HTMLをファイルに保存
    with open("yyc_login_page.html", "w", encoding="utf-8") as f:
        f.write(page.content())
    browser.close()