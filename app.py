import streamlit as st
import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from openai import OpenAI
import time
import json
import traceback
from streamlit_autorefresh import st_autorefresh
import requests
from datetime import datetime, timedelta
import pytz
import re
import base64
from io import BytesIO
import logging
import pickle
import os.path

# ロギングの設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 環境変数の読み込み
load_dotenv()

# OpenAI APIキーの設定
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

client = OpenAI(
    api_key=api_key,
    base_url="https://api.openai.com/v1"
)

# クッキー保存用のディレクトリ
COOKIES_DIR = "cookies"
if not os.path.exists(COOKIES_DIR):
    os.makedirs(COOKIES_DIR)

def save_cookies(context, email):
    """ブラウザのクッキーを保存"""
    try:
        cookies = context.cookies()
        cookie_file = os.path.join(COOKIES_DIR, f"{email}.pkl")
        with open(cookie_file, 'wb') as f:
            pickle.dump(cookies, f)
        log_debug(f"クッキーを保存しました: {cookie_file}")
    except Exception as e:
        log_error("クッキー保存エラー", e)

def load_cookies(context, email):
    """保存されたクッキーを読み込み"""
    try:
        cookie_file = os.path.join(COOKIES_DIR, f"{email}.pkl")
        if os.path.exists(cookie_file):
            with open(cookie_file, 'rb') as f:
                cookies = pickle.load(f)
            context.add_cookies(cookies)
            log_debug(f"クッキーを読み込みました: {cookie_file}")
            return True
        return False
    except Exception as e:
        log_error("クッキー読み込みエラー", e)
        return False

def check_session_valid(page):
    """セッションが有効かチェック"""
    try:
        # ログイン後のページで表示される要素をチェック
        selectors = [
            "a:has-text('マイページ')",
            "a:has-text('メッセージ')",
            "a:has-text('プロフィール')",
            ".user-menu",
            ".profile-menu"
        ]
        
        for selector in selectors:
            if page.query_selector(selector):
                log_debug(f"セッション有効: {selector}が見つかりました")
                return True
        
        # ログインページの要素が表示されていないかチェック
        login_form = page.query_selector("input[type='password']")
        if not login_form:
            log_debug("セッション有効: ログインフォームが見つかりません")
            return True
            
        log_debug("セッション無効: ログインが必要です")
        return False
    except Exception as e:
        log_error("セッションチェックエラー", e)
        return False

# サイドバーでログイン情報を入力
st.sidebar.header("Login Info")
user_email = st.sidebar.text_input("Email", key="email")
user_password = st.sidebar.text_input("Password", type="password", key="password")

# セッションステートの初期化
if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'last_check' not in st.session_state:
    st.session_state.last_check = None

if 'persona' not in st.session_state:
    st.session_state.persona = {
        "name": "優子",
        "age": 28,
        "occupation": "OL",
        "interests": ["カフェ巡り", "旅行", "料理"],
        "personality": "明るく、フレンドリー",
        "writing_style": "カジュアルで親しみやすい"
    }

# --- 関数定義のみ復元 ---
def setup_browser():
    pass

def cleanup_browser():
    pass

def get_latest_message(page, url):
    pass

def get_latest_message_in_thread(page, url):
    pass

def get_all_thread_links(page, url):
    pass

def get_partner_name_and_messages(page, url):
    pass

def send_reply(page, message):
    pass

def generate_reply(message, persona):
    """ChatGPTで返信文を生成"""
    try:
        # プロンプトの作成
        prompt = f"""
        以下のメッセージに対する返信を、以下のペルソナに基づいて生成してください。
        
        ペルソナ:
        - 名前: {persona['name']}
        - 年齢: {persona['age']}歳
        - 職業: {persona['occupation']}
        - 趣味: {', '.join(persona['interests'])}
        - 性格: {persona['personality']}
        - 文章スタイル: {persona['writing_style']}
        
        メッセージ:
        {message['content']}
        
        返信の条件:
        1. 自然で親しみやすい文章
        2. 相手のメッセージの内容に適切に反応
        3. 会話を発展させる要素を含める
        4. 短すぎず長すぎない適度な長さ
        5. 絵文字を適度に使用
        
        返信文のみを出力してください。
        """
        
        # ChatGPT APIを呼び出し
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "あなたは親しみやすい女性のペルソナで、マッチングアプリでの会話を担当します。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=200
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        log_error("返信生成エラー", e)
        return "返信の生成に失敗しました。"

def import_yyc_cookies_from_obj(driver, cookies):
    pass

def log_debug(message):
    """デバッグメッセージをログとStreamlitに出力"""
    logger.debug(message)
    st.write(f"DEBUG: {message}")
    print(f"DEBUG: {message}")

def log_error(message, error=None):
    """エラーメッセージをログとStreamlitに出力"""
    logger.error(message)
    st.error(f"ERROR: {message}")
    print(f"ERROR: {message}")
    if error:
        logger.error(traceback.format_exc())
        st.error(f"Error details:\n{traceback.format_exc()}")
        print(f"Error details:\n{traceback.format_exc()}")

def get_screenshot_as_base64(page):
    """ページのスクリーンショットをBase64エンコードして返す"""
    try:
        # ページの読み込み状態を確認
        try:
            # まずdomcontentloadedを確認
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            log_debug("Page is in domcontentloaded state")
        except Exception as e:
            log_debug(f"domcontentloaded timeout (non-critical): {str(e)}")
        
        # スクリーンショットを取得（タイムアウトは短めに）
        log_debug("Taking screenshot")
        screenshot = page.screenshot(timeout=10000)
        log_debug("Screenshot taken successfully")
        
        return base64.b64encode(screenshot).decode()
    except Exception as e:
        log_error("Screenshot error", e)
        return None

def display_screenshot(page, caption):
    """スクリーンショットをStreamlitで表示"""
    try:
        log_debug(f"Attempting to display screenshot: {caption}")
        screenshot_base64 = get_screenshot_as_base64(page)
        if screenshot_base64:
            st.image(f"data:image/png;base64,{screenshot_base64}", caption=caption)
            log_debug(f"Screenshot displayed successfully: {caption}")
        else:
            log_error(f"Could not capture screenshot for: {caption}")
    except Exception as e:
        log_error(f"Display screenshot error: {caption}", e)

def check_login_state(page):
    """ログイン状態を詳細にチェック"""
    log_debug("Checking login state...")
    
    # ユーザー要素のセレクタを拡充
    user_selectors = [
        "div:has-text('Welcome')",
        "div:has-text('My Reservations')",
        ".user",
        ".profile",
        "a:has-text('Sign Out')",
        "a:has-text('My Reservations')",
        "a:has-text('Profile')",
        "button:has-text('Sign Out')",
        "[data-test='user-menu']",
        "[data-test='profile-menu']",
        ".user-menu",
        ".profile-menu"
    ]
    
    # エラー要素のセレクタを拡充
    error_selectors = [
        ".error",
        ".alert",
        "div:has-text('Invalid')",
        "div:has-text('incorrect')",
        "div:has-text('failed')",
        "div:has-text('error')",
        "div:has-text('try again')",
        "span:has-text('error')",
        "span:has-text('invalid')",
        "[data-test='error-message']"
    ]
    
    # ユーザー要素のチェック
    for selector in user_selectors:
        element = page.query_selector(selector)
        if element:
            text = element.inner_text()
            log_debug(f"Found user element with selector '{selector}': {text}")
            return True, f"Login success! Found: {text}"
    
    # エラー要素のチェック
    for selector in error_selectors:
        element = page.query_selector(selector)
        if element:
            text = element.inner_text()
            log_debug(f"Found error element with selector '{selector}': {text}")
            return False, f"Login failed: {text}"
    
    # ログインフォームの存在チェック
    login_form = page.query_selector("input[type='email'], input[type='password']")
    if login_form:
        log_debug("Login form is still present")
        return False, "Login failed: login form still present"
    
    # ページのURLをチェック
    current_url = page.url
    log_debug(f"Current URL: {current_url}")
    if "login" in current_url.lower():
        return False, "Login failed: still on login page"
    
    return None, "Login result unclear: no definitive indicators found"

def check_messages():
    try:
        log_debug("Starting check_messages")
        playwright = sync_playwright().start()
        log_debug("Playwright started")
        
        browser = playwright.chromium.launch(headless=True, args=[
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled'
        ])
        log_debug("Browser launched")
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        log_debug("Browser context created")
        
        page = context.new_page()
        log_debug("New page created")
        
        log_debug("Navigating to app.resy.com")
        try:
            # まずdomcontentloadedを待つ
            page.goto("https://app.resy.com/", wait_until="domcontentloaded", timeout=60000)
            log_debug("Initial page load completed")
            
            # ページが完全に読み込まれるまで少し待機
            time.sleep(5)
            
        except Exception as e:
            log_error("Page navigation failed", e)
            raise
        
        display_screenshot(page, "Initial Page")
        
        title = page.title()
        log_debug(f"Page title: {title}")
        
        login_button = page.query_selector("text=Log In")
        if login_button:
            log_debug("Login button found")
            try:
                login_button.click()
                # クリック後の読み込みを待つ
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                    log_debug("Post-click page load completed")
                except Exception as e:
                    log_debug(f"Post-click load timeout (non-critical): {str(e)}")
                
                time.sleep(3)
                log_debug("Clicked login button and waited for navigation")
                
            except Exception as e:
                log_error("Login button click failed", e)
                raise
            
            display_screenshot(page, "Login Page")
        else:
            log_error("Login button not found")
        
        email_input = page.query_selector("input[type='email']")
        password_input = page.query_selector("input[type='password']")
        
        if email_input and password_input:
            log_debug("Login form found")
            if user_email and user_password:
                log_debug("Attempting to fill login form")
                display_screenshot(page, "Before Input")
                
                try:
                    email_input.fill(user_email)
                    password_input.fill(user_password)
                    log_debug("Login form filled")
                except Exception as e:
                    log_error("Failed to fill login form", e)
                    raise
                
                display_screenshot(page, "After Input")
                
                submit_btn = page.query_selector("button[type='submit'], button:has-text('Log In')")
                if submit_btn:
                    log_debug("Submit button found")
                    try:
                        submit_btn.wait_for_element_state("visible")
                        submit_btn.wait_for_element_state("enabled")
                        log_debug("Submit button is visible and enabled")
                        
                        display_screenshot(page, "Before Click")
                        
                        # クリック前のURLを記録
                        pre_click_url = page.url
                        log_debug(f"Pre-click URL: {pre_click_url}")
                        
                        submit_btn.click(force=True)
                        
                        # クリック後の読み込みを待つ
                        try:
                            page.wait_for_load_state("domcontentloaded", timeout=10000)
                            log_debug("Post-submit page load completed")
                        except Exception as e:
                            log_debug(f"Post-submit load timeout (non-critical): {str(e)}")
                        
                        # ページ遷移を待つ
                        try:
                            page.wait_for_url(lambda url: url != pre_click_url, timeout=10000)
                            log_debug("URL changed after login")
                        except Exception as e:
                            log_debug(f"URL change timeout (non-critical): {str(e)}")
                        
                        time.sleep(3)
                        log_debug("Submit button clicked")
                        
                    except Exception as e:
                        log_error("Submit button click failed", e)
                        raise
                    
                    display_screenshot(page, "After Click")
                    
                    post_login_title = page.title()
                    log_debug(f"Post-login page title: {post_login_title}")
                    
                    # ログイン状態を詳細にチェック
                    login_success, login_message = check_login_state(page)
                    if login_success is True:
                        log_debug(login_message)
                    elif login_success is False:
                        log_error(login_message)
                    else:
                        log_error(login_message)
                    
                    # HTMLスニペットの出力
                    html_snippet = page.content()[:1000]
                    log_debug(f"HTML snippet: {html_snippet}")
                    
                else:
                    log_error("Submit button not found")
            else:
                log_error("No email/password provided")
        else:
            log_error("Login form not found")
        
        context.close()
        browser.close()
        playwright.stop()
        log_debug("Browser and Playwright closed")
        
    except Exception as e:
        log_error("check_messages error", e)
        # エラー時もリソースを確実に解放
        try:
            if 'context' in locals():
                context.close()
            if 'browser' in locals():
                browser.close()
            if 'playwright' in locals():
                playwright.stop()
        except Exception as cleanup_error:
            log_error("Cleanup error", cleanup_error)

def yyc_login_test():
    """YYCにログインし、トップページのスクリーンショットを表示"""
    try:
        log_debug("YYCログインテスト開始")
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True, args=[
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled'
        ])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()
        
        # 保存されたクッキーを読み込み
        if load_cookies(context, user_email):
            log_debug("保存されたクッキーでセッションを復元")
            page.goto("https://www.yyc.co.jp/", wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)
            
            if check_session_valid(page):
                log_debug("セッションが有効です")
                display_screenshot(page, "セッション復元後のページ")
                context.close()
                browser.close()
                playwright.stop()
                return
        
        log_debug("YYCログインページへ遷移")
        page.goto("https://www.yyc.co.jp/login/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)
        display_screenshot(page, "YYCログインページ")
        
        # HTMLスニペットを出力
        html_snippet = page.content()[:1000]
        log_debug(f"YYCログインページHTMLスニペット: {html_snippet}")
        
        # メールアドレス欄
        email_input = page.query_selector("input[type='text'], input[type='email']")
        # すべてのパスワードinputを列挙
        pw_inputs = page.query_selector_all("input[type='password']")
        for i, pw in enumerate(pw_inputs):
            name = pw.get_attribute('name')
            log_debug(f"password_input[{i}]: name={name}")
        # ログインボタン
        login_btn = page.query_selector("button, input[type='submit'], button:has-text('ログイン'), input[value*='ログイン']")
        
        if email_input and pw_inputs and login_btn:
            email_input.fill(user_email)
            for pw in pw_inputs:
                pw.fill(user_password)
            log_debug("ログインフォーム入力完了（全パスワード欄に入力）")
            display_screenshot(page, "YYCログインフォーム入力後")
            login_btn.click()
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            time.sleep(2)
            display_screenshot(page, "YYCログイン後ページ")
            log_debug(f"ログイン後タイトル: {page.title()}")
            
            # ログイン成功時にクッキーを保存
            if check_session_valid(page):
                save_cookies(context, user_email)
                log_debug("ログイン成功: クッキーを保存しました")
            else:
                log_error("ログイン失敗: セッションが無効です")
            
            # ログイン後ページのbodyタグ内HTML（5000文字）
            try:
                body_elem = page.query_selector('body')
                if body_elem:
                    body_html = body_elem.inner_html()[:5000]
                    log_debug(f"YYCログイン後ページBODYスニペット: {body_html}")
                else:
                    log_debug("bodyタグが見つかりません")
            except Exception as e:
                log_debug(f"bodyタグ抽出エラー: {str(e)}")
            
            # フォーム内の全input値を出力
            try:
                inputs = page.query_selector_all('form input')
                for i, inp in enumerate(inputs):
                    name = inp.get_attribute('name')
                    value = inp.get_attribute('value')
                    log_debug(f"input[{i}]: name={name}, value={value}")
            except Exception as e:
                log_debug(f"input抽出エラー: {str(e)}")
            
            # エラー要素の検出
            error_elem = page.query_selector(".error, .alert, .formError, div[style*='color:red'], span[style*='color:red']")
            if error_elem:
                log_debug(f"エラー要素検出: {error_elem.inner_text()}")
            
            # CAPTCHA画像の検出
            captcha_img = page.query_selector("img[src*='captcha'], img[alt*='認証'], img[alt*='captcha']")
            if captcha_img:
                log_debug(f"CAPTCHA画像検出: {captcha_img.get_attribute('src')}")
            
            # CAPTCHA inputの存在チェック
            if page.query_selector("[name='cf-turnstile-response'], [name='g-recaptcha-response']"):
                log_debug("CAPTCHAが検出されました。自動ログインは困難です。手動認証が必要です。")
        else:
            log_error("ログインフォーム要素が見つかりません")
        
        context.close()
        browser.close()
        playwright.stop()
        log_debug("ブラウザ終了")
    except Exception as e:
        log_error("YYCログインテストでエラー", e)
        try:
            if 'context' in locals():
                context.close()
            if 'browser' in locals():
                browser.close()
            if 'playwright' in locals():
                playwright.stop()
        except Exception as cleanup_error:
            log_error("Cleanup error", cleanup_error)

def get_latest_messages(page):
    """最新のメッセージを取得"""
    try:
        # メッセージページに移動
        page.goto("https://www.yyc.co.jp/message/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)
        
        # メッセージ一覧を取得
        message_elements = page.query_selector_all(".message-item, .chat-item")
        messages = []
        
        for element in message_elements:
            try:
                # 送信者名
                sender = element.query_selector(".sender-name, .user-name")
                sender_name = sender.inner_text() if sender else "不明"
                
                # メッセージ本文
                content = element.query_selector(".message-content, .chat-content")
                message_text = content.inner_text() if content else ""
                
                # 送信日時
                time_elem = element.query_selector(".message-time, .chat-time")
                sent_time = time_elem.inner_text() if time_elem else ""
                
                if message_text:
                    messages.append({
                        "sender": sender_name,
                        "content": message_text,
                        "time": sent_time
                    })
            except Exception as e:
                log_error(f"メッセージ要素の解析エラー: {str(e)}")
                continue
        
        return messages
    except Exception as e:
        log_error("メッセージ取得エラー", e)
        return []

def main():
    st.title("YYC メッセージアシスタント")
    
    # サイドバーでペルソナ設定
    st.sidebar.header("ペルソナ設定")
    st.session_state.persona["name"] = st.sidebar.text_input("名前", value=st.session_state.persona["name"])
    st.session_state.persona["age"] = st.sidebar.number_input("年齢", min_value=18, max_value=100, value=st.session_state.persona["age"])
    st.session_state.persona["occupation"] = st.sidebar.text_input("職業", value=st.session_state.persona["occupation"])
    st.session_state.persona["interests"] = st.sidebar.text_input("趣味（カンマ区切り）", value=", ".join(st.session_state.persona["interests"])).split(", ")
    st.session_state.persona["personality"] = st.sidebar.text_input("性格", value=st.session_state.persona["personality"])
    st.session_state.persona["writing_style"] = st.sidebar.text_input("文章スタイル", value=st.session_state.persona["writing_style"])
    
    # メッセージ取得ボタン
    if st.button("最新メッセージを取得"):
        try:
            with st.spinner("メッセージを取得中..."):
                playwright = sync_playwright().start()
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                
                # 保存されたクッキーを読み込み
                if load_cookies(context, user_email):
                    messages = get_latest_messages(page)
                    if messages:
                        st.session_state.messages = messages
                        st.session_state.last_check = datetime.now()
                    else:
                        st.warning("メッセージが見つかりませんでした。")
                else:
                    st.error("ログインセッションが見つかりません。先にログインしてください。")
                
                context.close()
                browser.close()
                playwright.stop()
        except Exception as e:
            st.error(f"エラーが発生しました: {str(e)}")
    
    # メッセージ一覧の表示
    if st.session_state.messages:
        st.subheader("最新メッセージ")
        for i, message in enumerate(st.session_state.messages):
            with st.expander(f"{message['sender']} - {message['time']}"):
                st.write(message['content'])
                
                # 返信生成ボタン
                if st.button(f"返信を生成 ({i+1})"):
                    with st.spinner("返信を生成中..."):
                        reply = generate_reply(message, st.session_state.persona)
                        st.text_area("生成された返信", reply, height=150)
                        
                        # コピーボタン
                        if st.button("クリップボードにコピー"):
                            st.write("返信文をコピーしました！")
    
    # 最終更新時刻の表示
    if st.session_state.last_check:
        st.write(f"最終更新: {st.session_state.last_check.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main() 