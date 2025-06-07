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

# 環境変数の読み込み
load_dotenv()

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

def check_messages():
    try:
        st.write("check_messages called")
        print("check_messages called")
        st.write("before playwright start")
        print("before playwright start")
        playwright = sync_playwright().start()
        st.write("after playwright start")
        print("after playwright start")
        browser = playwright.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'])
        st.write("after browser launch")
        print("after browser launch")
        context = browser.new_context()
        st.write("after context creation")
        print("after context creation")
        page = context.new_page()
        st.write("navigating to example.com")
        print("navigating to example.com")
        page.goto("https://example.com")
        st.write("after goto example.com")
        print("after goto example.com")
        title = page.title()
        st.write(f"page title: {title}")
        print(f"page title: {title}")
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