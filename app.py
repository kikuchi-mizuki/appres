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

def get_screenshot_as_base64(page):
    """ページのスクリーンショットをBase64エンコードして返す"""
    try:
        # ページの読み込み完了を待つ
        page.wait_for_load_state("networkidle", timeout=60000)
        # スクリーンショットを取得
        screenshot = page.screenshot(timeout=60000)
        return base64.b64encode(screenshot).decode()
    except Exception as e:
        st.error(f"Screenshot error: {str(e)}")
        return None

def display_screenshot(page, caption):
    """スクリーンショットをStreamlitで表示"""
    try:
        screenshot_base64 = get_screenshot_as_base64(page)
        if screenshot_base64:
            st.image(f"data:image/png;base64,{screenshot_base64}", caption=caption)
        else:
            st.warning(f"Could not capture screenshot for: {caption}")
    except Exception as e:
        st.error(f"Display screenshot error: {str(e)}")

def check_messages():
    try:
        st.write("check_messages called")
        print("check_messages called")
        st.write("before playwright start")
        print("before playwright start")
        playwright = sync_playwright().start()
        st.write("after playwright start")
        print("after playwright start")
        browser = playwright.chromium.launch(headless=True, args=[
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled'
        ])
        st.write("after browser launch")
        print("after browser launch")
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        st.write("after context creation")
        print("after context creation")
        page = context.new_page()
        st.write("navigating to app.resy.com")
        print("navigating to app.resy.com")
        
        # ページ遷移のタイムアウトを延長
        page.goto("https://app.resy.com/", timeout=60000)
        page.wait_for_load_state("networkidle", timeout=60000)
        
        st.write("after goto app.resy.com")
        print("after goto app.resy.com")
        
        # 初期ページのスクリーンショット
        display_screenshot(page, "Initial Page")
        
        title = page.title()
        st.write(f"page title: {title}")
        print(f"page title: {title}")
        
        # ログインページに遷移
        login_button = page.query_selector("text=Log In")
        if login_button:
            login_button.click()
            # クリック後の読み込みを待つ
            page.wait_for_load_state("networkidle", timeout=60000)
            time.sleep(3)
            st.write("navigated to login page")
            print("navigated to login page")
            
            # ログインページのスクリーンショット
            display_screenshot(page, "Login Page")
        else:
            st.write("Log In button not found.")
            print("Log In button not found.")
        
        # ログインフォームの有無を確認
        email_input = page.query_selector("input[type='email']")
        password_input = page.query_selector("input[type='password']")
        if email_input and password_input:
            st.session_state.messages.append("Login form found!")
            st.write("Login form found!")
            print("Login form found!")
            
            # 入力値があれば自動入力してログイン
            if user_email and user_password:
                # 入力前のスクリーンショット
                display_screenshot(page, "Before Input")
                
                email_input.fill(user_email)
                password_input.fill(user_password)
                
                # 入力後のスクリーンショット
                display_screenshot(page, "After Input")
                
                submit_btn = page.query_selector("button[type='submit'], button:has-text('Log In')")
                if submit_btn:
                    submit_btn.wait_for_element_state("visible")
                    submit_btn.wait_for_element_state("enabled")
                    
                    # クリック前のスクリーンショット
                    display_screenshot(page, "Before Click")
                    
                    # クリックを試みる
                    submit_btn.click(force=True)
                    time.sleep(3)
                    
                    # クリック後のスクリーンショット
                    display_screenshot(page, "After Click")
                    
                    st.session_state.messages.append("Login attempted!")
                    st.write("Login attempted!")
                    print("Login attempted!")
                    
                    # ログイン後のページタイトルを取得
                    post_login_title = page.title()
                    st.session_state.messages.append(f"Post-login page title: {post_login_title}")
                    st.write(f"Post-login page title: {post_login_title}")
                    print(f"Post-login page title: {post_login_title}")
                    
                    # ログイン後のエラーやユーザー名要素をチェック
                    error_elem = page.query_selector(".error, .alert, div:has-text('Invalid'), div:has-text('incorrect'), div:has-text('failed')")
                    user_elem = page.query_selector("div:has-text('Welcome'), div:has-text('My Reservations'), .user, .profile")
                    login_form_still = page.query_selector("input[type='email']")
                    
                    if error_elem:
                        error_text = error_elem.inner_text()
                        st.session_state.messages.append(f"Login failed: {error_text}")
                        st.write(f"Login failed: {error_text}")
                        print(f"Login failed: {error_text}")
                    elif login_form_still:
                        st.session_state.messages.append("Login failed: login form still present.")
                        st.write("Login failed: login form still present.")
                        print("Login failed: login form still present.")
                    elif user_elem:
                        user_text = user_elem.inner_text()
                        st.session_state.messages.append(f"Login success! User element: {user_text}")
                        st.write(f"Login success! User element: {user_text}")
                        print(f"Login success! User element: {user_text}")
                    else:
                        st.session_state.messages.append("Login result unclear: no error or user element found.")
                        st.write("Login result unclear: no error or user element found.")
                        print("Login result unclear: no error or user element found.")
                    
                    # デバッグ用: HTMLスニペットをmessagesに表示
                    html_snippet = page.content()[:1000]
                    st.session_state.messages.append(f"HTML snippet: {html_snippet}")
                    st.write("HTML snippet (first 1000 chars):")
                    st.code(html_snippet)
                    print(f"HTML snippet: {html_snippet}")
                    
                    # 追加のユーザー要素検出
                    user_elem2 = page.query_selector("a:has-text('Sign Out'), a:has-text('My Reservations'), a:has-text('Profile'), button:has-text('Sign Out')")
                    if user_elem2:
                        user2_text = user_elem2.inner_text()
                        st.session_state.messages.append(f"Login success! User element2: {user2_text}")
                        st.write(f"Login success! User element2: {user2_text}")
                        print(f"Login success! User element2: {user2_text}")
                    
                    # <body>以降のHTMLスニペットを出力
                    body_match = re.search(r'<body.*?>.*', page.content(), re.DOTALL)
                    if body_match:
                        body_snippet = body_match.group(0)[:2000]
                        st.session_state.messages.append(f"Body snippet: {body_snippet}")
                        st.write("Body snippet (first 2000 chars):")
                        st.code(body_snippet)
                        print(f"Body snippet: {body_snippet}")
                    
                    # さらに多様なエラー要素を探す
                    error_elem2 = page.query_selector("div:has-text('incorrect'), div:has-text('error'), div:has-text('try again'), div:has-text('Invalid'), span:has-text('error'), span:has-text('invalid')")
                    if error_elem2:
                        error2_text = error_elem2.inner_text()
                        st.session_state.messages.append(f"Login failed (extra check): {error2_text}")
                        st.write(f"Login failed (extra check): {error2_text}")
                        print(f"Login failed (extra check): {error2_text}")
                else:
                    st.session_state.messages.append("Login submit button not found.")
                    st.write("Login submit button not found.")
                    print("Login submit button not found.")
            else:
                st.session_state.messages.append("No email/password provided.")
                st.write("No email/password provided.")
                print("No email/password provided.")
        else:
            st.session_state.messages.append("Login form not found.")
            st.write("Login form not found.")
            print("Login form not found.")
        
        st.session_state.messages.append(f"Page title: {title}")
        context.close()
        browser.close()
        playwright.stop()
    except Exception as e:
        import traceback
        st.error(f"check_messages error: {e}\n{traceback.format_exc()}")
        print(f"check_messages error: {e}\n{traceback.format_exc()}")

def main():
    st.title("Resy Message Monitor")
    st.write("main OK")
    # メッセージリストの表示
    st.write("---")
    st.write("Messages:")
    for message in st.session_state.messages:
        st.write(f"- {message}")
    # リフレッシュボタンでcheck_messagesを呼ぶ
    if st.button("Refresh Messages"):
        try:
            check_messages()
            st.rerun()
        except Exception as e:
            st.error(f"Refresh error: {e}")

main() 