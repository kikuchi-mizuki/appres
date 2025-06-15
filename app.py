import streamlit as st
import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import openai
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

# OpenAIクライアントの設定
openai.api_key = api_key

# クッキー保存用のディレクトリ
COOKIES_DIR = "cookies"
os.makedirs(COOKIES_DIR, exist_ok=True)

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

def save_cookies(context, email):
    """ブラウザのセッションストレージを保存（storage_stateを使う）"""
    try:
        storage_file = os.path.join(COOKIES_DIR, f"{email}_storage.json")
        context.storage_state(path=storage_file)
        log_debug(f"storage_state を保存しました: {storage_file}")
    except Exception as e:
        log_error("セッション保存エラー（storage_state）", e)

def fix_storage_state_format(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    changed = False
    for cookie in data.get("cookies", []):
        same_site = cookie.get("sameSite")
        if same_site not in ["Strict", "Lax", "None"]:
            cookie["sameSite"] = "None"
            changed = True
    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return filepath

def load_cookies(browser, email):
    """保存された storage_state を読み込んで新しい context を生成"""
    try:
        storage_file = os.path.join(COOKIES_DIR, f"{email}_storage.json")
        if os.path.exists(storage_file):
            fix_storage_state_format(storage_file)
            return browser.new_context(storage_state=storage_file)
        else:
            return None
    except Exception as e:
        log_error("セッション復元エラー（storage_state）", e)
        return None

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

def get_latest_messages(page):
    """最新のメッセージを取得"""
    try:
        # メッセージページに移動
        log_debug("メッセージページに移動します...")
        page.goto("https://www.yyc.co.jp/my/mail_box/round_trip?filter=not_res", wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)
        log_debug(f"現在のURL: {page.url}")
        
        # ログインページにリダイレクトされているかチェック
        if "login" in page.url.lower():
            log_debug(f"ログインページにリダイレクトされました: {page.url}")
            st.error("cookieでログインできませんでした。再度保存してください。")
            return []
        
        # メッセージ一覧を取得
        log_debug("メッセージ要素を検索中...")
        
        # まず親要素の存在を確認
        message_list_wrap = page.query_selector(".message_listWrap")
        if message_list_wrap:
            log_debug("message_listWrap要素が見つかりました")
            # 子要素の数を確認
            children = message_list_wrap.query_selector_all("*")
            log_debug(f"message_listWrapの子要素数: {len(children)}")
        else:
            log_debug("message_listWrap要素が見つかりません")
        
        # メッセージ要素を検索（複数のセレクターを試す）
        message_elements = page.query_selector_all(".mdl_listBox_simple, .message_listWrap > div")
        log_debug(f"見つかったメッセージ要素の数: {len(message_elements)}")
        
        if not message_elements:
            log_debug("メッセージ要素が見つかりません。HTMLの構造を確認します...")
            st.warning("メッセージ要素が見つかりません。セレクターが変更された可能性があります。")
            
            # デバッグ用にHTMLの構造を出力
            log_debug("ページのHTML構造:")
            html_content = page.content()
            st.text("ページHTMLの先頭一部:")
            st.code(html_content[:8000])
            
            return []
        
        messages = []
        log_debug(f"メッセージ要素の解析を開始します（{len(message_elements)}件）")
        
        for i, element in enumerate(message_elements, 1):
            try:
                log_debug(f"メッセージ {i} の解析を開始")
                
                # 送信者名
                sender = element.query_selector(".name strong, .thumb + div strong")
                sender_name = sender.inner_text() if sender else "不明"
                log_debug(f"送信者: {sender_name}")
                
                # メッセージ本文
                content = element.query_selector(".message p, .thumb + div p")
                message_text = content.inner_text() if content else ""
                log_debug(f"メッセージ本文: {message_text[:50]}...")
                
                # 送信日時
                time_elem = element.query_selector(".date, .thumb + div .date")
                sent_time = time_elem.inner_text() if time_elem else ""
                log_debug(f"送信日時: {sent_time}")
                
                # 未返信ステータス
                status = element.query_selector(".msgHistoryStatus.replied")
                is_unreplied = bool(status)
                log_debug(f"未返信ステータス: {is_unreplied}")
                
                if message_text:
                    messages.append({
                        "sender": sender_name,
                        "content": message_text,
                        "time": sent_time,
                        "is_unreplied": is_unreplied
                    })
                    log_debug(f"メッセージ {i} の解析が完了")
                else:
                    log_debug(f"メッセージ {i} は本文が空のためスキップ")
                    
            except Exception as e:
                log_error(f"メッセージ {i} の解析中にエラーが発生: {str(e)}")
                continue
        
        log_debug(f"合計 {len(messages)} 件のメッセージを取得しました")
        return messages
    except Exception as e:
        log_error("メッセージ取得エラー", e)
        return []

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
        response = openai.ChatCompletion.create(
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

def check_cookie_valid(email):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = load_cookies(browser, email)
            if context is not None:
                page = context.new_page()
                page.goto("https://www.yyc.co.jp/mypage/", wait_until="domcontentloaded", timeout=15000)
                time.sleep(2)
                # マイページに遷移できれば有効
                if "mypage" in page.url:
                    context.close()
                    browser.close()
                    return True
                context.close()
                browser.close()
        return False
    except Exception as e:
        return False

def main():
    if 'user_password' not in st.session_state:
        st.session_state.user_password = ""
    
    # メインタイトル
    st.title("YYC メッセージアシスタント")
    
    # 柔らかいパステル調のカスタムCSSを挿入
    st.markdown('''
        <style>
        body, .stApp {
            background: #fff6fa;
            font-family: 'Noto Sans JP', 'Rounded M+ 1c', sans-serif;
        }
        .stButton>button {
            background: linear-gradient(90deg, #f9c7d1 0%, #f7e9f0 100%);
            color: #fff;
            border-radius: 24px;
            font-size: 1.1em;
            padding: 0.7em 2em;
            box-shadow: 0 2px 8px #f9c7d155;
            border: none;
            margin-bottom: 0.7em;
            transition: 0.2s;
        }
        .stButton>button:hover {
            background: linear-gradient(90deg, #f7e9f0 0%, #f9c7d1 100%);
            color: #d96c9c;
        }
        .stChatMessage, .stMarkdown {
            background: #fff;
            border-radius: 18px;
            margin-bottom: 1em;
            padding: 1em;
            box-shadow: 0 2px 8px #f9c7d122;
        }
        .stTextInput>div>input, .stFileUploader>div {
            border-radius: 16px;
            background: #f7e9f0;
        }
        .stFileUploader>div>div>button {
            background: #f9c7d1;
            color: #fff;
            border-radius: 16px;
            font-size: 1em;
            border: none;
        }
        .stTextInput>div>input {
            font-size: 1.1em;
            padding: 0.7em 1em;
        }
        .stSidebarContent {
            background: #fff6fa;
        }
        hr {
            border: none;
            border-top: 1.5px dashed #f9c7d1;
            margin: 1em 0;
        }
        </style>
    ''', unsafe_allow_html=True)

    # サイドバーの設定
    with st.sidebar:
        st.header("🔐 ログイン設定")
        
        # メールアドレス入力
        if 'user_email' not in st.session_state:
            st.session_state.user_email = ""
        st.session_state.user_email = st.text_input("📧 メールアドレス", value=st.session_state.user_email, key="login_email")
        
        # cookieファイルアップロード
        uploaded_file = st.file_uploader("📁 cookieファイルをアップロード", type=["json"])
        if uploaded_file is not None:
            email = st.session_state.user_email
            if not email:
                st.error("先にメールアドレスを入力してください")
            else:
                cookies_dir = COOKIES_DIR if 'COOKIES_DIR' in globals() else "cookies"
                os.makedirs(cookies_dir, exist_ok=True)
                file_path = os.path.join(cookies_dir, f"{email}_storage.json")
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.read())
                st.success("✅ cookieファイルを保存しました")
                with st.spinner("cookieの有効性を確認中..."):
                    if check_cookie_valid(email):
                        st.success("✅ cookieは有効です")
                    else:
                        st.error("❌ cookieは無効です")
        
        st.divider()
        
        # YYCログインフォーム
        st.header("🔑 YYCログイン")
        with st.form("yyc_login_form"):
            login_email = st.text_input("📧 YYCのメールアドレス", value=st.session_state.user_email, key="yyc_login_email_form")
            login_password = st.text_input("🔒 YYCのパスワード", type="password", key="yyc_login_pw_form")
            login_submit = st.form_submit_button("ログインしてcookie保存")

            if login_submit:
                if not login_email or not login_password:
                    st.error("メールアドレスとパスワードを入力してください")
                else:
                    try:
                        with sync_playwright() as p:
                            browser = p.chromium.launch(headless=True)
                            context = browser.new_context(
                                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                                locale="ja-JP"
                            )
                            page = context.new_page()
                            page.set_extra_http_headers({
                                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
                            })
                            page.goto("https://www.yyc.co.jp/login", wait_until="domcontentloaded", timeout=60000)

                            try:
                                page.wait_for_selector("input[name='account']", timeout=10000)
                                page.wait_for_selector("input[name='password']", timeout=10000)
                                page.wait_for_selector("input[type='submit'][data-testid='login-btn']", timeout=10000)
                            except Exception as e:
                                st.write("--- デバッグ用: 取得したHTML ---")
                                st.write(page.content())
                                raise e

                            email_input = page.query_selector("input[name='account']")
                            password_input = page.query_selector("input[name='password']")
                            login_btn = page.query_selector("input[type='submit'][data-testid='login-btn']")

                            if email_input and password_input and login_btn:
                                email_input.fill(login_email)
                                password_input.fill(login_password)
                                login_btn.click()
                                page.wait_for_load_state("domcontentloaded", timeout=10000)
                                time.sleep(2)

                                if check_session_valid(page):
                                    save_cookies(context, login_email)
                                    st.session_state.user_email = login_email
                                    st.success("✅ ログイン成功＆cookieを保存しました")
                                else:
                                    st.error("❌ ログイン失敗：IDかパスワードが間違っているか、画像認証が必要かもしれません")
                            else:
                                st.error("❌ ログインフォームの要素が見つかりませんでした")

                            context.close()
                            browser.close()
                    except Exception as e:
                        log_error("Playwrightログイン処理中のエラー", e)
        
        st.divider()
        
        # ペルソナ設定
        st.header("👤 ペルソナ設定")
        st.session_state.persona["name"] = st.text_input("名前", value=st.session_state.persona["name"], key="persona_name")
        st.session_state.persona["age"] = st.number_input("年齢", min_value=18, max_value=100, value=st.session_state.persona["age"], key="persona_age")
        st.session_state.persona["occupation"] = st.text_input("職業", value=st.session_state.persona["occupation"], key="persona_occupation")
        st.session_state.persona["interests"] = st.text_input("趣味（カンマ区切り）", value=", ".join(st.session_state.persona["interests"]), key="persona_interests").split(", ")
        st.session_state.persona["personality"] = st.text_input("性格", value=st.session_state.persona["personality"], key="persona_personality")
        st.session_state.persona["writing_style"] = st.text_input("文章スタイル", value=st.session_state.persona["writing_style"], key="persona_writing_style")
    
    # メインコンテンツ
    # スマホでも見やすいように1カラムに

    # 最新メッセージ取得ボタン（必ず表示）
    if st.button("📥 最新メッセージを取得", key="fetch_messages", use_container_width=True):
        if not st.session_state.user_email:
            st.error("メールアドレスを入力してください")
        else:
            storage_file = os.path.join(COOKIES_DIR, f"{st.session_state.user_email}_storage.json")
            if not os.path.exists(storage_file):
                st.error("cookieファイルがありません。手動でcookieを保存してください")
            else:
                try:
                    with st.spinner("メッセージを取得中..."):
                        with sync_playwright() as p:
                            browser = p.chromium.launch(headless=True)
                            context = load_cookies(browser, st.session_state.user_email)
                            if context is None:
                                st.error("cookieファイルの読み込みに失敗しました")
                                browser.close()
                            else:
                                page = context.new_page()
                                messages = get_latest_messages(page)
                                if messages:
                                    st.session_state.messages = messages
                                else:
                                    st.warning("メッセージが見つからないか、cookieが無効です。再度cookieを保存してください")
                                context.close()
                                browser.close()
                except Exception as e:
                    st.error(f"エラーが発生しました: {str(e)}")

    st.subheader("メッセージ一覧")
    chat_container = st.container()
    with chat_container:
        for i, message in enumerate(st.session_state.messages):
            # 送信者のメッセージ（全文表示）
            with st.chat_message("user", avatar="👤"):
                st.markdown(f"<div style='font-size:1.1em;line-height:1.6;word-break:break-all;'><b>{message['sender']}</b> <span style='color:#888;font-size:0.9em;'>({message['time']})</span><br>{message['content']}</div>", unsafe_allow_html=True)

            # 返信生成ボタン（大きめ＆タッチしやすい）
            if st.button("✍️ 返信を生成", key=f"generate_reply_{i}", use_container_width=True):
                with st.spinner("返信を生成中..."):
                    reply = generate_reply(message, st.session_state.persona)
                    # 返信は「アシスタント」名で表示
                    with st.chat_message("assistant", avatar="🤖"):
                        st.markdown(f"<div style='font-size:1.1em;line-height:1.6;word-break:break-all;'><b>アシスタント</b><br>{reply}</div>", unsafe_allow_html=True)
                    if st.button("📋 クリップボードにコピー", key=f"copy_reply_{i}", use_container_width=True):
                        st.success("✅ 返信文をコピーしました")
            if i < len(st.session_state.messages) - 1:
                st.markdown("<hr style='margin:0.5em 0;' />", unsafe_allow_html=True)

if __name__ == "__main__":
    main() 