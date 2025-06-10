from playwright.sync_api import sync_playwright
import json
import os

email = "mmms.dy.23@gmail.com"  # ログイン用メールアドレス
COOKIES_DIR = "cookies"
os.makedirs(COOKIES_DIR, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.yyc.co.jp/login/")
    print("ブラウザでYYCに手動でログインしてください。\n追加認証（CAPTCHAやSMS認証）が出た場合も必ず突破してください。\nログイン後、マイページやメッセージ画面まで遷移してからEnterを押してください...")
    input()
    cookies = context.cookies()
    with open(f"{COOKIES_DIR}/{email}.json", "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"cookieファイルを {COOKIES_DIR}/{email}.json に保存しました。")
    browser.close()