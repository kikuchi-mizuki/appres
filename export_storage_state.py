from playwright.sync_api import sync_playwright
import os

# メールアドレスを設定
email = "mmms.dy.23@gmail.com"  # あなたのメールアドレスに変更してください
COOKIES_DIR = "cookies"

def main():
    # cookiesディレクトリが存在しない場合は作成
    if not os.path.exists(COOKIES_DIR):
        os.makedirs(COOKIES_DIR)
        print(f"Created directory: {COOKIES_DIR}")

    with sync_playwright() as p:
        try:
            # 既存のChromeに接続
            print("Chromeに接続中...")
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            
            # 既存のウィンドウのcontextを取得
            context = browser.contexts[0]
            
            # storage_stateを保存
            storage_path = f"{COOKIES_DIR}/{email}_storage.json"
            context.storage_state(path=storage_path)
            print(f"storage_stateを {storage_path} に保存しました。")
            
            browser.close()
            print("完了！")
            
        except Exception as e:
            print(f"エラーが発生しました: {str(e)}")
            print("\n以下の点を確認してください：")
            print("1. Chromeがリモートデバッグモードで起動しているか")
            print("2. YYCにログインしているか")
            print("3. ポート9222が使用可能か")

if __name__ == "__main__":
    main() 