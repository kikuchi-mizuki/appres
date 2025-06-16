import subprocess
import sys
import os

# 1. venv作成
def run(cmd):
    print(f"実行: {cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print("エラーが発生しました。手動でコマンドを実行してください。")
        sys.exit(1)

if not os.path.exists(".venv"):
    print("仮想環境を作成します...")
    run("python3 -m venv .venv")

# 2. venv有効化案内
if os.name == "nt":
    activate_cmd = ".venv\\Scripts\\activate"
else:
    activate_cmd = "source .venv/bin/activate"
print(f"仮想環境を有効化してください: {activate_cmd}")

# 3. 必要パッケージのインストール
print("必要なパッケージをインストールします...")
run(".venv/bin/pip install --upgrade pip")
run(".venv/bin/pip install playwright")
run(".venv/bin/python -m playwright install")

# 4. メールアドレス入力
email = input("YYCログイン用メールアドレスを入力してください: ").strip()

# 5. cookie取得スクリプトを生成
cookie_script = f'''
from playwright.sync_api import sync_playwright
import json
import os

email = "{email}"
COOKIES_DIR = "cookies"
os.makedirs(COOKIES_DIR, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://www.yyc.co.jp/login/")
    print("ブラウザでYYCに手動でログインしてください。\\n追加認証（CAPTCHAやSMS認証）が出た場合も必ず突破してください。\\nログイン後、マイページやメッセージ画面まで遷移してからEnterを押してください...")
    input()
    cookies = context.cookies()
    with open(f"{{COOKIES_DIR}}/{{email}}.json", "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"cookieファイルを {{COOKIES_DIR}}/{{email}}.json に保存しました。")
    browser.close()
'''
with open("get_yyc_cookie.py", "w", encoding="utf-8") as f:
    f.write(cookie_script)

# 6. cookie取得スクリプトの実行
print("cookie取得スクリプトを実行します...")
run(f".venv/bin/python get_yyc_cookie.py")

print("\n--- 完了！ ---")
print(f"できあがった cookie ファイル: cookies/{email}.json")
print("このファイルを Streamlit アプリの「cookieファイルをアップロード」からアップロードしてください。") 