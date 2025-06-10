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
    """保存されたクッキーを読み込み（pkl/json両対応）"""
    try:
        cookie_file_pkl = os.path.join(COOKIES_DIR, f"{email}.pkl")
        cookie_file_json = os.path.join(COOKIES_DIR, f"{email}.json")
        if os.path.exists(cookie_file_json):
            with open(cookie_file_json, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            context.add_cookies(cookies)
            log_debug(f"クッキー（json）を読み込みました: {cookie_file_json}")
            return True
        elif os.path.exists(cookie_file_pkl):
            with open(cookie_file_pkl, 'rb') as f:
                cookies = pickle.load(f)
            context.add_cookies(cookies)
            log_debug(f"クッキー（pkl）を読み込みました: {cookie_file_pkl}")
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

def get_latest_messages(page):
    """最新のメッセージを取得"""
    try:
        # メッセージページに移動
        page.goto("https://www.yyc.co.jp/message/", wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)
        
        # ログインページにリダイレクトされているかチェック
        if "login" in page.url.lower():
            log_debug("ログインページにリダイレクトされました。ログインを実行します。")
            # ログインページでフォームを入力
            email_input = page.query_selector("input[type='text'], input[type='email']")
            pw_inputs = page.query_selector_all("input[type='password']")
            login_btn = page.query_selector("button, input[type='submit'], button:has-text('ログイン'), input[value*='ログイン']")
            
            if email_input and pw_inputs and login_btn:
                email_input.fill(st.session_state.user_email)
                for pw in pw_inputs:
                    pw.fill(st.session_state.user_password)
                log_debug("ログインフォーム入力完了")
                login_btn.click()
                page.wait_for_load_state("domcontentloaded", timeout=10000)
                time.sleep(2)
                
                # ログイン成功時にクッキーを保存
                if check_session_valid(page):
                    save_cookies(page.context, st.session_state.user_email)
                    log_debug("ログイン成功: クッキーを保存しました")
                else:
                    log_error("ログイン失敗: セッションが無効です")
                    return []
            else:
                log_error("ログインフォーム要素が見つかりません")
                return []
        
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
            context = browser.new_context()
            # cookie読み込み（json/pkl両対応）
            cookie_file_json = os.path.join(COOKIES_DIR, f"{email}.json")
            cookie_file_pkl = os.path.join(COOKIES_DIR, f"{email}.pkl")
            cookies = None
            if os.path.exists(cookie_file_json):
                with open(cookie_file_json, "r", encoding="utf-8") as f:
                    cookies = json.load(f)
            elif os.path.exists(cookie_file_pkl):
                with open(cookie_file_pkl, "rb") as f:
                    cookies = pickle.load(f)
            if cookies:
                context.add_cookies(cookies)
                page = context.new_page()
                page.goto("https://www.yyc.co.jp/message/", wait_until="domcontentloaded", timeout=15000)
                time.sleep(2)
                # ログイン状態の判定（例：メッセージページの要素が見えるか）
                if page.query_selector("a:has-text('マイページ'), a:has-text('メッセージ'), .user-menu, .profile-menu"):
                    context.close()
                    browser.close()
                    return True
                context.close()
                browser.close()
        return False
    except Exception as e:
        return False

def main():
    st.title("YYC メッセージアシスタント")
    
    # サイドバーでログイン情報を入力
    st.sidebar.header("Login Info")
    if 'user_email' not in st.session_state:
        st.session_state.user_email = ""
    
    st.session_state.user_email = st.sidebar.text_input("Email", value=st.session_state.user_email, key="login_email")

    # cookieファイルアップロード機能
    uploaded_file = st.sidebar.file_uploader("cookieファイルをアップロード", type=["pkl", "json"])
    if uploaded_file is not None:
        email = st.session_state.user_email
        if not email:
            st.sidebar.error("先にメールアドレスを入力してください")
        else:
            cookies_dir = COOKIES_DIR if 'COOKIES_DIR' in globals() else "cookies"
            os.makedirs(cookies_dir, exist_ok=True)
            # 拡張子判定
            if uploaded_file.name.endswith('.json'):
                file_path = os.path.join(cookies_dir, f"{email}.json")
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.read())
                # バリデーション
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        cookies = json.load(f)
                    if not isinstance(cookies, list) or not all(isinstance(c, dict) for c in cookies):
                        st.sidebar.error("cookieファイルの形式が不正です（リスト形式の辞書である必要があります）")
                    elif not all("name" in c and "value" in c and "domain" in c for c in cookies):
                        st.sidebar.error("cookie情報に必要なキー（name, value, domain）がありません")
                    else:
                        st.sidebar.success("cookieファイル（json）を保存しました！")
                        # 有効性チェック
                        with st.spinner("cookieの有効性を確認中..."):
                            if check_cookie_valid(email):
                                st.sidebar.success("cookieは有効です（YYCにログインできます）")
                            else:
                                st.sidebar.error("cookieは無効です（YYCにログインできません）")
                except Exception as e:
                    st.sidebar.error(f"cookieファイルの読み込みに失敗しました: {e}")
            else:
                file_path = os.path.join(cookies_dir, f"{email}.pkl")
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.read())
                # バリデーション
                try:
                    with open(file_path, "rb") as f:
                        cookies = pickle.load(f)
                    if not isinstance(cookies, list) or not all(isinstance(c, dict) for c in cookies):
                        st.sidebar.error("cookieファイルの形式が不正です（リスト形式の辞書である必要があります）")
                    elif not all("name" in c and "value" in c and "domain" in c for c in cookies):
                        st.sidebar.error("cookie情報に必要なキー（name, value, domain）がありません")
                    else:
                        st.sidebar.success("cookieファイル（pkl）を保存しました！")
                        # 有効性チェック
                        with st.spinner("cookieの有効性を確認中..."):
                            if check_cookie_valid(email):
                                st.sidebar.success("cookieは有効です（YYCにログインできます）")
                            else:
                                st.sidebar.error("cookieは無効です（YYCにログインできません）")
                except Exception as e:
                    st.sidebar.error(f"cookieファイルの読み込みに失敗しました: {e}")
    
    # サイドバーでペルソナ設定
    st.sidebar.header("ペルソナ設定")
    st.session_state.persona["name"] = st.sidebar.text_input("名前", value=st.session_state.persona["name"], key="persona_name")
    st.session_state.persona["age"] = st.sidebar.number_input("年齢", min_value=18, max_value=100, value=st.session_state.persona["age"], key="persona_age")
    st.session_state.persona["occupation"] = st.sidebar.text_input("職業", value=st.session_state.persona["occupation"], key="persona_occupation")
    st.session_state.persona["interests"] = st.sidebar.text_input("趣味（カンマ区切り）", value=", ".join(st.session_state.persona["interests"]), key="persona_interests").split(", ")
    st.session_state.persona["personality"] = st.sidebar.text_input("性格", value=st.session_state.persona["personality"], key="persona_personality")
    st.session_state.persona["writing_style"] = st.sidebar.text_input("文章スタイル", value=st.session_state.persona["writing_style"], key="persona_writing_style")
    
    # --- YYCログインフォーム: cookieを自動保存するUI ---
    st.sidebar.header("YYCにログインしてcookieを保存")
    with st.sidebar.form("yyc_login_form"):
        login_email = st.text_input("YYCのメールアドレス", value=st.session_state.user_email, key="yyc_login_email_form")
        login_password = st.text_input("YYCのパスワード", type="password", key="yyc_login_pw_form")
        login_submit = st.form_submit_button("ログインしてcookie保存")

        if login_submit:
            if not login_email or not login_password:
                st.sidebar.error("メールアドレスとパスワードを入力してください")
            else:
                from playwright.sync_api import sync_playwright
                import time
                try:
                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=True)
                        context = browser.new_context()
                        page = context.new_page()
                        page.goto("https://www.yyc.co.jp/login", wait_until="domcontentloaded", timeout=60000)

                        # フォーム入力 & ログイン実行
                        email_input = page.query_selector("input[type='text'], input[type='email']")
                        pw_inputs = page.query_selector_all("input[type='password']")
                        login_btn = page.query_selector("button, input[type='submit'], button:has-text('ログイン'), input[value*='ログイン']")

                        if email_input and pw_inputs and login_btn:
                            email_input.fill(login_email)
                            for pw in pw_inputs:
                                pw.fill(login_password)
                            login_btn.click()
                            page.wait_for_load_state("domcontentloaded", timeout=10000)
                            time.sleep(2)

                            if check_session_valid(page):
                                save_cookies(context, login_email)
                                st.session_state.user_email = login_email
                                st.sidebar.success("ログイン成功＆cookieを保存しました！")
                            else:
                                st.sidebar.error("ログイン失敗：IDかパスワードが間違っているか、画像認証が必要かもしれません。")
                        else:
                            st.sidebar.error("ログインフォームの要素が見つかりませんでした")

                        context.close()
                        browser.close()
                except Exception as e:
                    log_error("Playwrightログイン処理中のエラー", e)
    
    # メッセージ取得ボタン
    if st.button("最新メッセージを取得", key="fetch_messages"):
        if not st.session_state.user_email:
            st.error("メールアドレスを入力してください。")
            return
        
        # cookieファイルの存在チェック
        cookie_file = os.path.join(COOKIES_DIR, f"{st.session_state.user_email}.pkl")
        if not os.path.exists(cookie_file):
            st.error("cookieファイルがありません。手動でcookieを保存してください。")
            return
        
        try:
            with st.spinner("メッセージを取得中..."):
                playwright = sync_playwright()
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                
                # 保存されたクッキーを読み込み
                if load_cookies(context, st.session_state.user_email):
                    log_debug("保存されたクッキーでセッションを復元")
                else:
                    st.error("cookieファイルの読み込みに失敗しました。")
                    context.close()
                    browser.close()
                    playwright.stop()
                    return
                
                messages = get_latest_messages(page)
                if messages:
                    st.session_state.messages = messages
                    st.session_state.last_check = datetime.now()
                else:
                    st.warning("メッセージが見つからないか、cookieが無効です。再度cookieを保存してください。")
                
                context.close()
                browser.close()
                playwright.stop()
        except Exception as e:
            st.error(f"エラーが発生しました: {str(e)}")
    
    # メッセージ一覧の表示
    if st.session_state.messages:
        st.subheader("最新メッセージ")
        for i, message in enumerate(st.session_state.messages):
            with st.expander(f"{message['sender']} - {message['time']}", key=f"message_{i}"):
                st.write(message['content'])
                
                # 返信生成ボタン
                if st.button(f"返信を生成 ({i+1})", key=f"generate_reply_{i}"):
                    with st.spinner("返信を生成中..."):
                        reply = generate_reply(message, st.session_state.persona)
                        st.text_area("生成された返信", reply, height=150, key=f"reply_text_{i}")
                        
                        # コピーボタン
                        if st.button("クリップボードにコピー", key=f"copy_reply_{i}"):
                            st.write("返信文をコピーしました！")
    
    # 最終更新時刻の表示
    if st.session_state.last_check:
        st.write(f"最終更新: {st.session_state.last_check.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main() 