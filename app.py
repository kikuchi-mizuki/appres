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

# 環境変数の読み込み
load_dotenv()

def setup_browser():
    """Playwrightブラウザのセットアップ"""
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=True,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-dev-shm-usage'
        ]
    )
    context = browser.new_context(
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    )
    # Selenium検知回避
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)
    return playwright, browser, context

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

def main():
    st.title("YYCメッセージ返信アシスタント")
    st.sidebar.header("あなたのプロフィール")
    persona = st.sidebar.text_input("あなたのペルソナを入力してください", "25歳のOLで、明るく社交的な性格")
    # サイドバー: モデル選択
    model_choice = st.sidebar.selectbox("使用するモデル", ["gpt-3.5-turbo", "gpt-4o"])

    # サイドバー: Slack/LINE通知設定
    slack_webhook = st.sidebar.text_input("Slack Webhook URL", "")
    line_token = st.sidebar.text_input("LINE Notifyトークン", "")

    # サイドバー: 複数Cookie管理
    if "cookie_files" not in st.session_state:
        st.session_state["cookie_files"] = {}

    uploaded_cookie = st.sidebar.file_uploader("Cookieファイルを追加", type=["json"], key="cookie_upload")
    if uploaded_cookie is not None:
        cookies = json.load(uploaded_cookie)
        cookie_name = st.sidebar.text_input("このCookieの名前", value=f"user_{len(st.session_state['cookie_files'])+1}")
        if st.sidebar.button("Cookieを保存", key="save_cookie"):
            st.session_state["cookie_files"][cookie_name] = cookies
            st.sidebar.success(f"{cookie_name} を保存しました")

    cookie_names = list(st.session_state["cookie_files"].keys())
    selected_cookie = st.sidebar.selectbox("使用するCookie", cookie_names) if cookie_names else None
    if selected_cookie:
        cookies = st.session_state["cookie_files"][selected_cookie]
        st.sidebar.success(f"{selected_cookie} を使用中")
    else:
        cookies = None

    # サイドバー: auto_check, interval, num_threads
    auto_check = st.sidebar.checkbox("定期チェックを有効にする", value=False)
    interval = st.sidebar.number_input("チェック間隔（秒）", min_value=10, max_value=600, value=30, step=10)
    num_threads = st.sidebar.number_input("取得するスレッド数", min_value=1, max_value=50, value=5, step=1)
    yyc_url = "https://www.yyc.co.jp/my/mail_box/?filter=not_res"

    # 高度な差分検知: スレッドURL+最新メッセージ本文
    last_message_texts = st.session_state.get("last_message_texts", {})
    current_message_texts = {}
    new_messages = {}

    def send_notification(text):
        if slack_webhook:
            try:
                requests.post(slack_webhook, json={"text": text})
            except Exception as e:
                st.sidebar.error(f"Slack通知失敗: {e}")
        if line_token:
            try:
                requests.post(
                    "https://notify-api.line.me/api/notify",
                    headers={"Authorization": f"Bearer {line_token}"},
                    data={"message": text}
                )
            except Exception as e:
                st.sidebar.error(f"LINE通知失敗: {e}")

    if auto_check and cookies:
        count = st_autorefresh(interval=interval * 1000, limit=None, key="auto_refresh")
        playwright, browser, context = setup_browser()
        page = context.new_page()
        
        # Cookieを設定
        for cookie in cookies:
            context.add_cookies([{
                "name": cookie.get("name"),
                "value": cookie.get("value"),
                "domain": cookie.get("domain"),
                "path": cookie.get("path", "/"),
                "secure": cookie.get("secure", False),
                "httpOnly": cookie.get("httpOnly", False),
            }])
            
        thread_links = get_all_thread_links(page, yyc_url)[:num_threads]
        for link in thread_links:
            partner_name, messages, latest_timestamp = get_partner_name_and_messages(page, link)
            latest_msg = messages[-1] if messages else ""
            current_message_texts[link] = latest_msg
            if link not in last_message_texts or last_message_texts[link] != latest_msg:
                new_messages[link] = (partner_name, latest_msg)
                
        browser.close()
        playwright.stop()
        
        if new_messages:
            st.session_state["last_message_texts"] = current_message_texts
            for link, (partner_name, msg) in new_messages.items():
                st.success(f"新着: {partner_name} - {msg}")
            # 通知送信
            notify_text = "\n".join([f"{partner_name}: {msg}" for partner_name, msg in new_messages.values()])
            send_notification(f"YYC新着メッセージ:\n{notify_text}")
        else:
            st.session_state["last_message_texts"] = current_message_texts

    if st.button("全スレッドの最新メッセージを取得・返信生成", use_container_width=True):
        if yyc_url and cookies is not None:
            playwright, browser, context = setup_browser()
            page = context.new_page()
            
            # Cookieを設定
            for cookie in cookies:
                context.add_cookies([{
                    "name": cookie.get("name"),
                    "value": cookie.get("value"),
                    "domain": cookie.get("domain"),
                    "path": cookie.get("path", "/"),
                    "secure": cookie.get("secure", False),
                    "httpOnly": cookie.get("httpOnly", False),
                }])
                
            with st.spinner("スレッド一覧を取得中..."):
                thread_links = get_all_thread_links(page, yyc_url)[:num_threads]
                results = []
                for link in thread_links:
                    partner_name, messages, latest_timestamp = get_partner_name_and_messages(page, link)
                    if messages:
                        reply = generate_reply(messages[-1], persona, partner_name, model_choice)
                        results.append((link, partner_name, messages, reply, latest_timestamp))
                        
            browser.close()
            playwright.stop()
            st.session_state["results"] = results
        else:
            st.warning("Cookieファイルをアップロードしてください")

    # メッセージ一覧の表示・コピー＆削除
    if "results" in st.session_state:
        results = st.session_state["results"]
        for idx, (link, partner_name, messages, reply, latest_timestamp) in enumerate(results):
            st.write(f"スレッド: {link}")
            st.write(f"相手: {partner_name}")
            latest_msg = messages[-1] if messages else ""
            st.markdown(f"**最新メッセージ：**\n{latest_msg}")
            st.markdown(f"**返信案：**\n{reply}")
            key_suffix = f"{idx}_{link}_{partner_name}_{latest_timestamp}"
            copied = st.session_state.get(f"copied_copy_{key_suffix}", False)
            sent = st.session_state.get(f"sent_{key_suffix}", False)
            if st.button("コピー", key=f"copy_{key_suffix}", use_container_width=True):
                st.session_state[f"copied_copy_{key_suffix}"] = True
                st.success("コピーしました！")
            if st.button("送信", key=f"send_{key_suffix}", use_container_width=True):
                playwright, browser, context = setup_browser()
                page = context.new_page()
                
                # Cookieを設定
                for cookie in cookies:
                    context.add_cookies([{
                        "name": cookie.get("name"),
                        "value": cookie.get("value"),
                        "domain": cookie.get("domain"),
                        "path": cookie.get("path", "/"),
                        "secure": cookie.get("secure", False),
                        "httpOnly": cookie.get("httpOnly", False),
                    }])
                    
                try:
                    result = send_reply(page, reply)
                    if result:
                        st.session_state[f"sent_{key_suffix}"] = True
                        st.success("送信しました！")
                    else:
                        st.error("送信失敗（ポイント不足等）")
                except Exception as e:
                    st.error(f"送信に失敗: {e}")
                finally:
                    browser.close()
                    playwright.stop()
            if copied:
                st.info("コピー済み")
            if sent:
                st.info("送信済み")

if __name__ == "__main__":
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