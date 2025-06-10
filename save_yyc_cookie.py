from playwright.sync_api import sync_playwright
import json
import os
import time

email = "mmms.dy.23@gmail.com"  # ログイン用メールアドレス
password = "ここにパスワード"      # ログイン用パスワード
COOKIES_DIR = "cookies"
os.makedirs(COOKIES_DIR, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.yyc.co.jp/login/")
    time.sleep(2)

    # 自動入力
    page.fill("input[type='text'], input[type='email']", email)
    page.fill("input[type='password']", password)
    time.sleep(1)
    login_btn = page.query_selector("button, input[type='submit'], button:has-text('ログイン'), input[value*='ログイン']")
    if login_btn:
        login_btn.click()
    else:
        print("ログインボタンが見つかりません")
        browser.close()
        exit()

    time.sleep(5)  # ログイン後の遷移待ち

    # ログイン成功判定
    if "login" in page.url.lower() or page.query_selector("input[type='password']"):
        print("自動ログイン失敗または追加認証が必要です。手動でログインしてください。\nログインが完了したらEnterを押してください...")
        input()
    else:
        print("自動ログイン成功。cookieを保存します。")

    cookies = context.cookies()
    with open(f"{COOKIES_DIR}/{email}.json", "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"cookieファイルを {COOKIES_DIR}/{email}.json に保存しました。")
    browser.close()