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

# ロギングの設定
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 環境変数の読み込み
load_dotenv()

# サイドバーでログイン情報を入力
st.sidebar.header("Login Info")
user_email = st.sidebar.text_input("Email", key="email")
user_password = st.sidebar.text_input("Password", type="password", key="password")

# セッションステートの初期化
if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'last_check' not in st.session_state:
    st.session_state.last_check = None

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

def generate_reply(message, persona, partner_name, model_choice):
    pass

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
        log_debug("YYCログインページへ遷移")
        page.goto("https://www.yyc.co.jp/login/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)
        display_screenshot(page, "YYCログインページ")
        
        # HTMLスニペットを出力
        html_snippet = page.content()[:1000]
        log_debug(f"YYCログインページHTMLスニペット: {html_snippet}")
        
        # メールアドレス欄
        email_input = page.query_selector("input[type='text'], input[type='email']")
        # パスワード欄
        password_input = page.query_selector("input[type='password']")
        # ログインボタン
        login_btn = page.query_selector("button, input[type='submit'], button:has-text('ログイン'), input[value*='ログイン']")
        
        if email_input and password_input and login_btn:
            email_input.fill(user_email)
            password_input.fill(user_password)
            log_debug("ログインフォーム入力完了")
            display_screenshot(page, "YYCログインフォーム入力後")
            login_btn.click()
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            time.sleep(2)
            display_screenshot(page, "YYCログイン後ページ")
            log_debug(f"ログイン後タイトル: {page.title()}")
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

def main():
    st.title("Resy Message Monitor")
    log_debug("Application started")
    
    st.write("---")
    st.write("Messages:")
    for message in st.session_state.messages:
        st.write(f"- {message}")
    
    if st.button("Refresh Messages"):
        try:
            check_messages()
            st.rerun()
        except Exception as e:
            log_error("Refresh error", e)

    # Streamlit UIにテストボタン追加
    st.write("---")
    st.write("YYCログインテスト:")
    if st.button("YYCログインテスト実行"):
        yyc_login_test()

if __name__ == "__main__":
    main() 