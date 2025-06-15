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

# サイドバーにデバッグ表示切り替え（開発者用）
with st.sidebar:
    show_debug = st.checkbox("🔧 開発者用: デバッグ表示", value=False)
    st.session_state["show_debug"] = show_debug

def log_debug(message):
    logger.debug(message)
    if st.session_state.get("show_debug"):
        st.text(f"DEBUG: {message}")

def log_error(message, error=None):
    logger.error(message)
    if st.session_state.get("show_debug"):
        st.text(f"ERROR: {message}")
        if error:
            st.text(f"Error details:\n{traceback.format_exc()}")
    if error:
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
    if 'user_email' not in st.session_state:
        st.session_state.user_email = ""
    if 'user_password' not in st.session_state:
        st.session_state.user_password = ""
    
    # 柔らかい・スマホ対応の追加CSS
    st.markdown("""
    <style>
    body, .stApp {
        font-family: 'Noto Sans JP', sans-serif;
        background-color: #fff6fa;
    }

    h1, h2, .stMarkdown h1, .stMarkdown h2 {
        color: #444 !important;
    }

    .user-card, .assistant-card {
        white-space: pre-wrap !important;
        word-break: break-word;
        overflow-wrap: break-word;
    }

    .stButton > button {
        width: 100% !important;
        white-space: normal !important;
        font-size: 1.1em;
        padding: 0.9em;
        border-radius: 20px;
        background: linear-gradient(90deg, #f9c7d1 0%, #f7e9f0 100%);
        border: none;
        box-shadow: 0 2px 8px rgba(249, 199, 209, 0.3);
    }
    </style>
    """, unsafe_allow_html=True)

    # タイトルを親しみやすく
    st.title("📨 YYCで届いたメッセージに楽しく返信しよう♪")
    
    # サイドバーをセクションごとに区切る
    with st.sidebar:
        with st.container():
            st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
            st.header("🔐 ログイン設定")
            st.session_state.user_email = st.text_input("メールアドレス", value=st.session_state.user_email)
            uploaded_file = st.file_uploader("cookieファイルをアップロード", type=["json"])
            if uploaded_file is not None:
                email = st.session_state.user_email
                if not email:
                    st.warning("先にメールアドレスを入力してください")
                else:
                    cookies_dir = COOKIES_DIR if 'COOKIES_DIR' in globals() else "cookies"
                    os.makedirs(cookies_dir, exist_ok=True)
                    file_path = os.path.join(cookies_dir, f"{email}_storage.json")
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.read())
                    st.success("✅ cookieファイルを保存しました")
                    # バリデーション
                    if check_cookie_valid(email):
                        st.success("✅ cookieは有効です")
                    else:
                        st.error("❌ cookieは無効です")
            st.markdown('</div>', unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
            st.header("👤 ペルソナ設定")
            st.text_input("名前", value=st.session_state.persona["name"], key="persona_name")
            st.number_input("年齢", min_value=18, max_value=100, value=st.session_state.persona["age"], key="persona_age")
            st.text_input("職業", value=st.session_state.persona["occupation"], key="persona_occupation")
            st.text_input("趣味（カンマ区切り）", value=", ".join(st.session_state.persona["interests"]), key="persona_interests")
            st.text_input("性格", value=st.session_state.persona["personality"], key="persona_personality")
            st.text_input("文章スタイル", value=st.session_state.persona["writing_style"], key="persona_writing_style")
            st.markdown('</div>', unsafe_allow_html=True)

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
    # スクロール可能なチャットエリア
    with st.container():
        st.markdown('<div class="scrollable-chat">', unsafe_allow_html=True)
        for i, message in enumerate(st.session_state.messages):
            # 送信者のメッセージ（色分けカード）
            st.markdown(f"<div class='user-card'><b>{message['sender']}</b> <span style='color:#888;font-size:0.9em;'>({message['time']})</span><br>{message['content']}</div>", unsafe_allow_html=True)
            # 返信生成ボタン（大きめ＆タッチしやすい）
            if st.button("✍️ 返信を生成", key=f"generate_reply_{i}", use_container_width=True):
                with st.spinner("返信を生成中..."):
                    reply = generate_reply(message, st.session_state.persona)
                    # 返信はアシスタント色のカードで表示
                    st.markdown(f"<div class='assistant-card'><b>アシスタント</b><br>{reply}</div>", unsafe_allow_html=True)
                    if st.button("📋 クリップボードにコピー", key=f"copy_reply_{i}", use_container_width=True):
                        st.success("✅ 返信文をコピーしました")
            if i < len(st.session_state.messages) - 1:
                st.markdown("<hr style='margin:0.5em 0;' />", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main() 