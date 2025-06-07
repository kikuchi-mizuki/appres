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
from flask import Flask, request

# 環境変数の読み込み
load_dotenv()

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'last_check' not in st.session_state:
    st.session_state.last_check = None

if 'browser' not in st.session_state:
    st.session_state.browser = None

if 'context' not in st.session_state:
    st.session_state.context = None

if 'playwright' not in st.session_state:
    st.session_state.playwright = None

def setup_browser():
    """Initialize browser with retry mechanism"""
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            context = browser.new_context()
            return playwright, browser, context
        except Exception as e:
            if attempt < max_retries - 1:
                st.warning(f"Browser setup attempt {attempt + 1} failed: {str(e)}. Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                st.error(f"Failed to setup browser after {max_retries} attempts: {str(e)}")
                raise

def cleanup_browser():
    """Cleanup browser resources"""
    if st.session_state.browser:
        st.session_state.browser.close()
    if st.session_state.playwright:
        st.session_state.playwright.stop()
    st.session_state.browser = None
    st.session_state.context = None
    st.session_state.playwright = None

def get_latest_message(page, url):
    """YYCから最新メッセージの本文を取得"""
    try:
        page.goto(url)
        page.wait_for_load_state('networkidle')
        
        # メッセージリンクを取得
        message_link = page.locator(".mdl_listBox_simple a").first
        if not message_link:
            st.error("メッセージリンクが見つかりませんでした。")
            return None
            
        message_url = message_link.get_attribute("href")
        page.goto(message_url)
        page.wait_for_load_state('networkidle')
        
        # メッセージ本文を取得
        try:
            body_element = page.locator(".msgCont.receiveCont .body .wrap .wrapinner")
            message_text = body_element.text_content().strip()
        except Exception as e:
            st.error(f"テキスト本文の取得に失敗: {traceback.format_exc()}")
            message_text = ""
            
        # スタンプ画像を取得
        try:
            img_element = page.locator(".msgCont.receiveCont .body .wrap .wrapinner .stamp.attach img").first
            stamp_url = img_element.get_attribute("src") if img_element else None
        except Exception as e:
            st.error(f"スタンプ画像の取得に失敗: {traceback.format_exc()}")
            stamp_url = None

        if message_text and stamp_url:
            return f"{message_text}\n[スタンプ画像]({stamp_url})"
        elif message_text:
            return message_text
        elif stamp_url:
            return f"[スタンプ画像]({stamp_url})"
        else:
            return "メッセージ本文が見つかりませんでした。"
    except Exception as e:
        st.error(f"メッセージの取得に失敗しました: {traceback.format_exc()}")
        return None

def get_latest_message_in_thread(page, url):
    """スレッド画面で一番下の最新メッセージを取得"""
    try:
        page.goto(url)
        page.wait_for_load_state('networkidle')
        
        # メッセージ本体のリストを全て取得
        message_elements = page.locator(".msgCont .body .wrap .wrapinner").all()
        if not message_elements:
            st.error("メッセージ本文が見つかりませんでした。")
            return None
            
        # 一番下（最新）のメッセージを取得
        latest_message = message_elements[-1].text_content().strip()
        return latest_message
    except Exception as e:
        st.error(f"メッセージの取得に失敗しました: {traceback.format_exc()}")
        return None

def get_all_thread_links(page, url):
    """スレッド一覧ページから全スレッドのリンクを取得"""
    page.goto(url)
    page.wait_for_load_state('networkidle')
    
    links = []
    elements = page.locator(".mdl_listBox_simple a").all()
    for elem in elements:
        link = elem.get_attribute("href")
        if link and "history" in link:
            links.append(link)
    return links

def get_partner_name_and_messages(page, url):
    page.goto(url)
    page.wait_for_load_state('networkidle')
    
    # 名前の取得
    try:
        name_elem = page.locator(".name strong").first
        partner_name = name_elem.text_content().strip()
    except Exception:
        partner_name = "不明"
        
    # メッセージ取得（全メッセージ）
    message_elements = page.locator(".msgCont .body .wrap .wrapinner").all()
    messages = []
    timestamps = []
    
    for elem in message_elements:
        text = elem.text_content().strip()
        # タイムスタンプ取得
        try:
            time_elem = elem.locator("xpath=..//.time").first
            timestamp = time_elem.text_content().strip()
        except Exception:
            timestamp = ""
            
        timestamps.append(timestamp)
        if text:
            messages.append(text)
        else:
            # テキストが空ならimg要素のaltまたはsrcを取得
            try:
                img = elem.locator("img").first
                alt = img.get_attribute("alt")
                src = img.get_attribute("src")
                if alt:
                    messages.append(f"[スタンプ] {alt}")
                elif src:
                    messages.append(f"[スタンプ画像]({src})")
                else:
                    messages.append("[スタンプ]")
            except Exception:
                messages.append("")
                
    latest_timestamp = timestamps[-1] if timestamps else ""
    return partner_name, messages, latest_timestamp

def send_reply(page, message):
    try:
        # 送信前の最新メッセージを取得
        try:
            message_elements = page.locator(".msgCont .body .wrap .wrapinner").all()
            before_texts = [elem.text_content().strip() for elem in message_elements if elem.text_content().strip()]
            before_latest = before_texts[-1] if before_texts else None
        except Exception:
            before_latest = None

        # 入力欄を探して入力
        input_field = page.locator("input[placeholder='メッセージを書く'], textarea[placeholder='メッセージを書く'], textarea[placeholder='メッセージを入力'], textarea, input[type='text'], [contenteditable='true']").first
        if not input_field:
            st.error("入力欄が見つかりませんでした。")
            return False
            
        input_field.fill(message)

        # 送信ボタンを探してクリック
        send_button = page.locator("button[type='submit'], button, input[type='submit'], .send-button, input[value='送信']").first
        if not send_button:
            st.error("送信ボタンが見つかりませんでした。")
            return False
            
        send_button.click()
        page.wait_for_load_state('networkidle')

        # 送信後の最新メッセージを取得
        try:
            message_elements = page.locator(".msgCont .body .wrap .wrapinner").all()
            after_texts = [elem.text_content().strip() for elem in message_elements if elem.text_content().strip()]
            after_latest = after_texts[-1] if after_texts else None
        except Exception:
            after_latest = None

        # 送信内容が最新メッセージとして反映されているか判定
        if after_latest and message.strip() in after_latest and after_latest != before_latest:
            print("[send_reply] 送信成功: 最新メッセージに反映されました。")
            return True
        else:
            print(f"[send_reply] 送信失敗: 最新メッセージ={after_latest} 送信内容={message}")
            return False
    except Exception as e:
        print(f"送信に失敗: {str(e)}")
        return False

def generate_reply(message, persona, partner_name, model_choice):
    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model=model_choice,
            messages=[
                {"role": "system", "content": f"あなたは{persona}の女性として振る舞ってください。相手の名前は『{partner_name}』です。"},
                {"role": "user", "content": f"以下のメッセージに対する自然な返信を生成してください（相手の名前を呼ぶ場合は『{partner_name}さん』としてください）：\n{message}"}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"返信の生成に失敗しました: {str(e)}")
        return None

def import_yyc_cookies_from_obj(driver, cookies):
    try:
        driver.get("https://www.yyc.co.jp/")
        for cookie in cookies:
            cookie_dict = {
                "name": cookie.get("name"),
                "value": cookie.get("value"),
                "domain": cookie.get("domain"),
                "path": cookie.get("path", "/"),
                "secure": cookie.get("secure", False),
                "httpOnly": cookie.get("httpOnly", False),
            }
            try:
                driver.add_cookie(cookie_dict)
                print(f"[Cookieセット成功] {cookie_dict}")
            except Exception as e:
                print(f"[Cookieセット失敗] {cookie_dict} エラー: {e}")
        # Cookieセット後にリロードして有効化
        driver.refresh()
        return True
    except Exception as e:
        st.error(f"Cookieのインポートに失敗しました: {e}")
        st.error(f"Cookie内容: {cookies}")
        return False

def check_messages():
    print("check_messages() called")
    try:
        if not st.session_state.browser:
            st.session_state.playwright, st.session_state.browser, st.session_state.context = setup_browser()
        
        page = st.session_state.context.new_page()
        page.goto('https://app.resy.com/')
        
        # Wait for the page to load
        page.wait_for_load_state('networkidle')
        
        # Get all messages
        messages = page.query_selector_all('.message')
        new_messages = []
        
        for message in messages:
            text = message.inner_text()
            if text not in [m['text'] for m in st.session_state.messages]:
                new_messages.append({
                    'text': text,
                    'timestamp': datetime.now(pytz.UTC).isoformat()
                })
        
        if new_messages:
            st.session_state.messages.extend(new_messages)
            st.session_state.last_check = datetime.now(pytz.UTC).isoformat()
        
        page.close()
        
    except Exception as e:
        st.error(f"Error checking messages: {str(e)}")
        cleanup_browser()

def main():
    print("main() started")
    st.title("Resy Message Monitor")
    try:
        # Check for new messages every 5 minutes
        if (not st.session_state.last_check or 
            datetime.now(pytz.UTC) - datetime.fromisoformat(st.session_state.last_check) > timedelta(minutes=5)):
            check_messages()
    except Exception as e:
        st.error(f"初期化エラー: {e}")
    # Display messages
    for message in st.session_state.messages:
        st.write(f"Message: {message['text']}")
        st.write(f"Time: {message['timestamp']}")
        st.write("---")
    # Add refresh button
    if st.button("Refresh Messages"):
        check_messages()
        st.experimental_rerun()

flask_app = Flask(__name__)

@flask_app.route('/webhook', methods=['POST'])
def webhook():
    print("LINE Webhook受信:", request.json)
    return "OK", 200

def app():
    st.markdown('''
        <style>
        .stApp {
            background: #fdf6f9;
            font-family: 'Noto Sans JP', 'Hiragino Kaku Gothic ProN', 'Rounded Mplus 1c', 'Arial Rounded MT Bold', 'Arial', sans-serif;
            color: #4a235a;
        }
        .stSidebar {
            background: #fff0f6;
            border-radius: 0 24px 24px 0;
            box-shadow: 2px 0 16px #F8BBD0;
            font-size: 16px;
            padding-top: 32px;
        }
        .stButton>button {
            background: linear-gradient(90deg, #F8BBD0 0%, #F48FB1 60%, #CE93D8 100%);
            color: white;
            border-radius: 18px;
            font-size: 18px;
            padding: 14px 32px;
            border: none;
            margin: 14px 0;
            box-shadow: 0 2px 8px #F8BBD0;
            font-weight: bold;
            letter-spacing: 1px;
            transition: background 0.2s, box-shadow 0.2s;
            min-width: 140px;
            min-height: 44px;
        }
        .stButton>button:hover {
            background: linear-gradient(90deg, #CE93D8 0%, #F8BBD0 100%);
            color: #fff;
            box-shadow: 0 4px 16px #CE93D8;
        }
        .stTextInput>div>input, .stTextArea>div>textarea {
            background: #fff;
            border-radius: 14px;
            border: 1.5px solid #F8BBD0;
            font-size: 16px;
            padding: 10px 16px;
            box-shadow: 0 1px 4px #F8BBD0;
            margin-bottom: 8px;
        }
        .stNumberInput>div>input {
            background: #fff;
            border-radius: 14px;
            border: 1.5px solid #F8BBD0;
            font-size: 16px;
            padding: 10px 16px;
            box-shadow: 0 1px 4px #F8BBD0;
            margin-bottom: 8px;
        }
        h1, h2, h3, h4 {
            color: #F48FB1;
            font-family: 'Noto Sans JP', 'Hiragino Kaku Gothic ProN', 'Rounded Mplus 1c', 'Arial Rounded MT Bold', 'Arial', sans-serif;
            font-size: 1.3em;
            font-weight: bold;
            letter-spacing: 1px;
        }
        .stSelectbox>div>div {
            border-radius: 14px;
            border: 1.5px solid #CE93D8;
            font-size: 16px;
            box-shadow: 0 1px 4px #F8BBD0;
        }
        .stSpinner>div {
            color: #F48FB1;
            font-size: 16px;
        }
        .stAlert {
            border-radius: 14px;
            font-size: 16px;
        }
        label, .css-1cpxqw2, .css-1n76uvr, .css-1offfwp, .css-1v0mbdj, .css-1y4p8pa, .css-1p05t8e {
            font-size: 16px;
        }
        /* レスポンシブ対応強化 */
        @media (max-width: 600px) {
            .stApp {
                font-size: 16px !important;
                padding: 0.5em !important;
            }
            .stSidebar, .stSidebarContent {
                font-size: 16px !important;
                padding: 0.5em 0.5em !important;
            }
            .stButton>button, .stFileUploader, .stTextInput>div>input, .stNumberInput>div>input, .stSelectbox>div>div {
                width: 100% !important;
                font-size: 1.2em !important;
                min-width: unset !important;
                min-height: 44px !important;
                padding: 1em !important;
                margin-bottom: 1em !important;
            }
            .st-bb, .st-cb, .st-eb {
                margin: 0.5em 0 !important;
                padding: 1em !important;
                border-radius: 18px !important;
            }
            h1, h2, h3, h4 {
                font-size: 1.3em !important;
            }
            label, .css-1cpxqw2, .css-1n76uvr, .css-1offfwp, .css-1v0mbdj, .css-1y4p8pa, .css-1p05t8e {
                font-size: 1.1em !important;
            }
        }
        /* さらにスマホで余白を詰める */
        @media (max-width: 400px) {
            .stApp {
                padding: 0.2em !important;
            }
            .stButton>button {
                padding: 0.5em !important;
                font-size: 1em !important;
            }
        }
        </style>
    ''', unsafe_allow_html=True)
    main()

if __name__ == "__main__":
    import sys
    if 'streamlit' in sys.argv[0]:
        app() 