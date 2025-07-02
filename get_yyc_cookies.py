from playwright.sync_api import sync_playwright

EMAIL = input("YYCのメールアドレスを入力してください: ")
PASSWORD = input("YYCのパスワードを入力してください: ")
STORAGE_PATH = "yyc_storage.json"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.yyc.co.jp/login/", wait_until="domcontentloaded")
    # メールアドレス欄のセレクターを複数試す
    selectors = ["input[type='email']", "input[name='mail']", "input[type='text']", "input[name='login_id']"]
    for sel in selectors:
        try:
            page.wait_for_selector(sel, timeout=5000)
            page.fill(sel, EMAIL)
            break
        except:
            continue
    # パスワード欄も同様に
    pw_selectors = ["input[type='password']", "input[name='password']"]
    for sel in pw_selectors:
        try:
            page.wait_for_selector(sel, timeout=5000)
            page.fill(sel, PASSWORD)
            break
        except:
            continue
    # ログインボタン
    btn_selectors = ["button[type='submit']", "input[type='submit']", "button", "input[type='button']"]
    for sel in btn_selectors:
        try:
            page.wait_for_selector(sel, timeout=5000)
            page.click(sel)
            break
        except:
            continue
    page.wait_for_load_state("networkidle")
    input("YYCのマイページまで遷移し、Cloudflare認証や画像認証も突破し、ログインが完了したらEnterを押してください...")
    context.storage_state(path=STORAGE_PATH)
    print(f"保存しました: {STORAGE_PATH}")
    browser.close() 