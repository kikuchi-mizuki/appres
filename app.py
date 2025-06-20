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
import subprocess
import streamlit.components.v1 as components
import pyperclip
from streamlit_extras.copy_to_clipboard import copy_to_clipboard_button

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
    """最新のメッセージを取得（返信URLも含める）"""
    try:
        log_debug("メッセージページに移動します...")
        page.goto("https://www.yyc.co.jp/my/mail_box/round_trip?filter=not_res", wait_until="domcontentloaded", timeout=60000)
        time.sleep(2)
        log_debug(f"現在のURL: {page.url}")
        if "login" in page.url.lower():
            log_debug(f"ログインページにリダイレクトされました: {page.url}")
            st.error("cookieでログインできませんでした。再度保存してください。")
            return []
        log_debug("メッセージ要素を検索中...")
        message_list_wrap = page.query_selector(".message_listWrap")
        if message_list_wrap:
            log_debug("message_listWrap要素が見つかりました")
            children = message_list_wrap.query_selector_all("*")
            log_debug(f"message_listWrapの子要素数: {len(children)}")
        else:
            log_debug("message_listWrap要素が見つかりません")
        message_elements = page.query_selector_all(".mdl_listBox_simple, .message_listWrap > div")
        log_debug(f"見つかったメッセージ要素の数: {len(message_elements)}")
        if not message_elements:
            log_debug("メッセージ要素が見つかりません。HTMLの構造を確認します...")
            st.warning("メッセージ要素が見つかりません。セレクターが変更された可能性があります。")
            return []
        messages = []
        log_debug(f"メッセージ要素の解析を開始します（{len(message_elements)}件）")
        for i, element in enumerate(message_elements, 1):
            try:
                log_debug(f"メッセージ {i} の解析を開始")
                sender = element.query_selector(".name strong, .thumb + div strong")
                sender_name = sender.inner_text() if sender else "不明"
                log_debug(f"送信者: {sender_name}")
                content = element.query_selector(".message p, .thumb + div p")
                message_text = content.inner_text() if content else ""
                log_debug(f"メッセージ本文: {message_text[:50]}...")
                time_elem = element.query_selector(".date, .thumb + div .date")
                sent_time = time_elem.inner_text() if time_elem else ""
                log_debug(f"送信日時: {sent_time}")
                status = element.query_selector(".msgHistoryStatus.replied")
                is_unreplied = bool(status)
                log_debug(f"未返信ステータス: {is_unreplied}")
                # 返信URLの取得
                reply_a = element.query_selector("a[href^='/my/mail_box/history/?id=']")
                reply_url = reply_a.get_attribute("href") if reply_a else None
                log_debug(f"返信URL: {reply_url}")
                if message_text:
                    messages.append({
                        "sender": sender_name,
                        "content": message_text,
                        "time": sent_time,
                        "is_unreplied": is_unreplied,
                        "reply_url": reply_url
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

def send_reply(email, reply_url, reply_text):
    """Playwrightで指定メッセージに自動返信（タイムアウト延長＆デバッグ用スクリーンショット）"""
    try:
        request_log = []  # ここで必ず初期化
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = load_cookies(browser, email)
            if context is None:
                return False, "cookieファイルの読み込みに失敗しました"
            page = context.new_page()
            # YYCは相対パスなのでフルURLに
            if reply_url.startswith("/"):
                reply_url = f"https://www.yyc.co.jp{reply_url}"
            page.goto(reply_url, wait_until="domcontentloaded", timeout=60000)  # 60秒に延長
            time.sleep(2)
            # デバッグ用スクリーンショット
            try:
                # スクリーンショット保存用のディレクトリを作成
                screenshot_dir = os.path.join(os.getcwd(), "screenshots")
                os.makedirs(screenshot_dir, exist_ok=True)
                screenshot_path = os.path.join(screenshot_dir, "debug_reply.png")
                page.screenshot(path=screenshot_path)
                log_debug(f"スクリーンショットを保存しました: {screenshot_path}")
                
                # ページのHTMLを取得してログに出力
                html_content = page.content()
                log_debug("ページのHTML構造:")
                log_debug(html_content[:1000])  # 最初の1000文字だけ出力
                
                # 返信フォームの要素を確認
                textarea = page.query_selector("textarea[name='message']")
                if textarea:
                    log_debug("返信フォームが見つかりました")
                    log_debug(f"返信フォームの属性: {textarea.get_attribute('name')}")
                else:
                    log_debug("返信フォームが見つかりません")
                    # 代替のセレクターを試す
                    alternative_selectors = [
                        "textarea",
                        "input[type='text']",
                        ".message-form textarea",
                        "#message-form textarea"
                    ]
                    for selector in alternative_selectors:
                        element = page.query_selector(selector)
                        if element:
                            log_debug(f"代替セレクター '{selector}' で要素が見つかりました")
                
            except Exception as e:
                log_error(f"スクリーンショットの保存に失敗: {str(e)}", e)
            # 送信ボタンを探しておく
            send_btn = page.query_selector("input[type='submit'], button[type='submit']")
            if not send_btn:
                # 代替のセレクターを試す
                alternative_buttons = [
                    "button:has-text('送信')",
                    "input[value='送信']",
                    ".submit-button",
                    "#submit-button"
                ]
                for selector in alternative_buttons:
                    send_btn = page.query_selector(selector)
                    if send_btn:
                        log_debug(f"送信ボタンが見つかりました: {selector}")
                        break

            # --- 自動調査: フォーム構造・hiddenフィールド・イベント属性・関数名をログ出力 ---
            try:
                # フォーム要素
                form_handle = textarea.evaluate_handle('el => el.form')
                if form_handle:
                    form_html = form_handle.evaluate('form => form.outerHTML')
                    log_debug(f"[自動調査] 送信フォームのHTML:\n{form_html}")
                    # hiddenフィールド・input一覧
                    inputs = form_handle.evaluate('form => Array.from(form.querySelectorAll("input,textarea")).map(i => ({name: i.name, type: i.type, value: i.value, hidden: i.type==="hidden"}))')
                    for inp in inputs:
                        log_debug(f"[自動調査] input: name={inp['name']}, type={inp['type']}, value={inp['value']}, hidden={inp['hidden']}")
                else:
                    log_debug("[自動調査] textarea.formが取得できませんでした")
                # 送信ボタンのonclick属性・outerHTML
                if send_btn:
                    send_btn_html = send_btn.evaluate('el => el.outerHTML')
                    send_btn_onclick = send_btn.get_attribute('onclick')
                    log_debug(f"[自動調査] 送信ボタンouterHTML: {send_btn_html}")
                    log_debug(f"[自動調査] 送信ボタンonclick属性: {send_btn_onclick}")
                else:
                    log_debug("[自動調査] 送信ボタンが見つかりませんでした")
                # windowオブジェクトの関数名一覧
                window_keys = page.evaluate('() => Object.keys(window).filter(k => typeof window[k] === "function")')
                log_debug(f"[自動調査] windowオブジェクトの関数名一覧: {window_keys}")
            except Exception as e:
                log_debug(f"[自動調査] フォーム構造等の自動調査中にエラー: {str(e)}")
            
            # フォームの状態を確認
            is_disabled = textarea.get_attribute("disabled")
            is_readonly = textarea.get_attribute("readonly")
            log_debug(f"フォームの状態: disabled={is_disabled}, readonly={is_readonly}")
            
            # フォームが有効になるまで待機
            try:
                page.wait_for_selector("textarea[name='message']:not([disabled]):not([readonly])", timeout=5000)
            except Exception as e:
                log_debug(f"フォームの有効化待機中にタイムアウト: {str(e)}")
            
            # テキストを入力
            textarea.fill(reply_text)
            log_debug("返信テキストを入力しました")
            
            # 送信ボタンが有効になるまで待機
            try:
                page.wait_for_selector("input[type='submit']:not([disabled]), button[type='submit']:not([disabled])", timeout=5000)
            except Exception as e:
                log_debug(f"送信ボタンの有効化待機中にタイムアウト: {str(e)}")
            
            # クリック前の状態を確認しログ出力
            if send_btn:
                is_visible = send_btn.is_visible()
                is_enabled = send_btn.is_enabled()
                log_debug(f"送信ボタン: visible={is_visible}, enabled={is_enabled}")
            else:
                is_visible = False
                is_enabled = False
                log_debug("送信ボタンがNoneです")

            # クリックを試みる
            try:
                # クリック前に少し待機
                time.sleep(1)
                if send_btn and is_visible and is_enabled:
                    send_btn.scroll_into_view_if_needed()
                    try:
                        send_btn.click(timeout=10000)
                        log_debug("送信ボタンをクリックしました")
                    except Exception as e:
                        log_debug(f"通常のクリックに失敗: {str(e)}")
                        # outerHTMLをログ出力
                        try:
                            send_btn_html = send_btn.evaluate('el => el.outerHTML')
                            log_debug(f"送信ボタンouterHTML: {send_btn_html}")
                        except Exception as html_e:
                            log_debug(f"送信ボタンouterHTML取得失敗: {str(html_e)}")
                        # JavaScriptでクリックイベントを発火
                        try:
                            page.evaluate("(btn) => btn.click()", send_btn)
                            log_debug("JavaScriptでクリックイベントを発火しました")
                        except Exception as js_error:
                            log_debug(f"JavaScriptクリックに失敗: {str(js_error)}")
                            # デバッグ用にスクリーンショットとHTMLを保存
                            error_screenshot_path = os.path.join(screenshot_dir, "send_btn_error.png")
                            page.screenshot(path=error_screenshot_path)
                            log_debug(f"送信ボタンエラー時のスクリーンショットを保存: {error_screenshot_path}")
                            log_debug(page.content()[:1000])
                            context.close()
                            browser.close()
                            return False, "送信ボタンがクリックできませんでした（send_btn_error.pngを確認してください）"
                else:
                    log_debug("送信ボタンが非表示または無効です。クリックをスキップします。")
                    # デバッグ用にスクリーンショットとHTMLを保存
                    error_screenshot_path = os.path.join(screenshot_dir, "send_btn_error.png")
                    page.screenshot(path=error_screenshot_path)
                    log_debug(f"送信ボタンエラー時のスクリーンショットを保存: {error_screenshot_path}")
                    log_debug(page.content()[:1000])
                    context.close()
                    browser.close()
                    return False, "送信ボタンが非表示または無効です（send_btn_error.pngを確認してください）"
            except Exception as e:
                log_debug(f"クリック処理全体で予期せぬエラー: {str(e)}")
            
            # 送信後の状態を確認
            try:
                # 送信成功の確認（URLの変更を確認）
                if "history" in page.url and "id=" in page.url:
                    log_debug("送信成功を確認: URLが履歴ページに遷移")
                    # 履歴ページで自分の送信内容が直近に表示されているか確認
                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                        time.sleep(1)
                        # --- 追加: 履歴ページのHTMLを保存 ---
                        try:
                            os.makedirs(screenshot_dir, exist_ok=True)
                            history_html_path = os.path.join(screenshot_dir, "history_debug.html")
                            with open(history_html_path, "w", encoding="utf-8") as f:
                                content = page.content()
                                f.write(content)
                                f.flush()
                                os.fsync(f.fileno())
                            if os.path.exists(history_html_path):
                                log_debug(f"[保存確認] {history_html_path} が正常に保存されました")
                                log_debug(f"[保存内容先頭20000] {content[:20000]}")
                                # 送信ページ（返信ページ）のHTMLも保存・ログ出力
                                try:
                                    send_page_path = os.path.join(screenshot_dir, "send_page_debug.html")
                                    with open(send_page_path, "w", encoding="utf-8") as sf:
                                        send_page_content = page.content()
                                        sf.write(send_page_content)
                                        sf.flush()
                                        os.fsync(sf.fileno())
                                    log_debug(f"[送信ページHTML先頭20000] {send_page_content[:20000]}")
                                except Exception as e:
                                    log_debug(f"[送信ページHTML保存エラー] {str(e)}")
                            else:
                                log_debug(f"[保存確認] {history_html_path} が保存されていません！")
                                log_debug(f"[保存内容先頭20000] {content[:20000]}")
                        except Exception as e:
                            log_debug(f"[失敗時も保存] 履歴ページHTML保存に失敗: {str(e)} (パス: {history_html_path})")
                        # --- 追加: 送信時のPOSTリクエスト内容を保存 ---
                        if request_log:
                            post_debug_path = os.path.join(screenshot_dir, "post_debug.json")
                            import json as _json
                            with open(post_debug_path, "w", encoding="utf-8") as f:
                                _json.dump(request_log, f, ensure_ascii=False, indent=2)
                            log_debug(f"送信時のPOSTリクエスト内容を保存: {post_debug_path}")
                        # --- 追加ここまで ---
                        found = False
                        for reload_count in range(3):
                            if reload_count > 0:
                                log_debug(f"履歴ページをリロード: {reload_count}回目")
                                page.reload(wait_until="networkidle")
                                time.sleep(2)
                            # メッセージリストの一番下（または上）に自分の送信内容があるか確認
                            selectors = [
                                ".message_listWrap .message p",
                                ".mdl_listBox_simple .message p",
                                "div.message p"
                            ]
                            for selector in selectors:
                                elements = page.query_selector_all(selector)
                                for elem in elements[-3:]:  # 直近3件だけ見る
                                    text = elem.inner_text().strip()
                                    log_debug(f"履歴ページのメッセージ: {text}")
                                    if reply_text.strip()[:30] in text:
                                        found = True
                                        break
                                if found:
                                    break
                            if found:
                                break
                        if found:
                            log_debug("履歴ページで自分の送信内容を確認")
                            # --- 送信時のPOSTリクエストログも出力 ---
                            return True, "返信を送信しました"
                        else:
                            log_debug("履歴ページに自分の送信内容が見つかりません")
                            return False, "送信処理は完了しましたが、履歴ページに自分の送信内容が見つかりませんでした。手動でご確認ください。"
                    except Exception as e:
                        log_debug(f"履歴ページ確認中にエラー: {str(e)}")
                        return False, "送信後の履歴ページ確認中にエラーが発生しました"
                
                # 送信成功の確認（成功メッセージや特定の要素の出現を待機）
                success_selectors = [
                    ".success-message",
                    ".alert-success",
                    "div:has-text('送信しました')",
                    "div:has-text('送信完了')"
                ]
                
                for selector in success_selectors:
                    try:
                        element = page.wait_for_selector(selector, timeout=5000)
                        if element:
                            log_debug(f"送信成功を確認: {selector}")
                            break
                    except Exception:
                        continue
                
                # 現在のURLを確認
                current_url = page.url
                log_debug(f"送信後のURL: {current_url}")
                
                # エラーメッセージの確認
                error_selectors = [
                    ".error-message",
                    ".alert-danger",
                    "div:has-text('エラー')",
                    "div:has-text('失敗')"
                ]
                
                for selector in error_selectors:
                    try:
                        element = page.query_selector(selector)
                        if element:
                            error_text = element.inner_text()
                            # エラーメッセージの内容を検証
                            if any(keyword in error_text.lower() for keyword in ['エラー', '失敗', 'error', 'failed']):
                                log_debug(f"エラーメッセージを検出: {error_text}")
                                return False, f"送信に失敗しました: {error_text}"
                            else:
                                log_debug(f"誤検出を除外: {error_text}")
                    except Exception:
                        continue
                
                # 送信成功しなかった場合もHTMLを保存
                else:
                    try:
                        os.makedirs(screenshot_dir, exist_ok=True)
                        history_html_path = os.path.join(screenshot_dir, "history_debug.html")
                        with open(history_html_path, "w", encoding="utf-8") as f:
                            content = page.content()
                            f.write(content)
                            f.flush()
                            os.fsync(f.fileno())
                        if os.path.exists(history_html_path):
                            log_debug(f"[保存確認] {history_html_path} が正常に保存されました")
                            log_debug(f"[保存内容先頭20000] {content[:20000]}")
                            # 送信ページ（返信ページ）のHTMLも保存・ログ出力
                            try:
                                send_page_path = os.path.join(screenshot_dir, "send_page_debug.html")
                                with open(send_page_path, "w", encoding="utf-8") as sf:
                                    send_page_content = page.content()
                                    sf.write(send_page_content)
                                    sf.flush()
                                    os.fsync(sf.fileno())
                                log_debug(f"[送信ページHTML先頭20000] {send_page_content[:20000]}")
                            except Exception as e:
                                log_debug(f"[送信ページHTML保存エラー] {str(e)}")
                        else:
                            log_debug(f"[保存確認] {history_html_path} が保存されていません！")
                            log_debug(f"[保存内容先頭20000] {content[:20000]}")
                        # 直後にls -lとfindの結果も出力
                        try:
                            ls_result = subprocess.check_output(["ls", "-l", screenshot_dir], encoding="utf-8")
                            log_debug(f"[ls結果] {ls_result}")
                        except Exception as e:
                            log_debug(f"[ls結果エラー] {str(e)}")
                        try:
                            find_result = subprocess.check_output(["find", screenshot_dir, "-name", "history_debug.html"], encoding="utf-8")
                            log_debug(f"[find結果] {find_result}")
                        except Exception as e:
                            log_debug(f"[find結果エラー] {str(e)}")
                    except Exception as e:
                        log_debug(f"[失敗時も保存] 履歴ページHTML保存に失敗: {str(e)} (パス: {history_html_path})")
            except Exception as e:
                log_debug(f"ページ読み込み待機中にタイムアウト: {str(e)}")
            
            time.sleep(2)
            context.close()
            browser.close()
            return True, "返信を送信しました"
    except Exception as e:
        return False, f"返信送信エラー: {str(e)}"

def main():
    if 'user_email' not in st.session_state:
        st.session_state.user_email = ""
    if 'user_password' not in st.session_state:
        st.session_state.user_password = ""
    
    # --- 追加CSS ---
    st.markdown('''
    <style>
    body, .stApp {
      font-family: "Noto Sans JP", "Hiragino Sans", sans-serif;
      background: linear-gradient(180deg, #fefefe 0%, #fdf2f8 100%);
    }

    h1, .stMarkdown h1 { font-size: 1.8rem !important; color: #333 !important; }
    h2, .stMarkdown h2 { font-size: 1.4rem !important; color: #444 !important; }
    h3, .stMarkdown h3 { font-size: 1.2rem !important; color: #444 !important; }

    .user-card, .reply-box {
      max-width: 640px;
      margin: 1.2em auto;
      padding: 1.2em 1.5em;
      border-radius: 18px;
      background: #fff;
      box-shadow: 0 2px 12px rgba(249, 199, 209, 0.10);
      color: #555;
      line-height: 1.6;
    }
    .reply-box {
      border: 1.5px solid #f9c7d1;
      background: #fdf2f8;
      box-shadow: 0 2px 8px rgba(249, 199, 209, 0.13);
      margin-bottom: 1.2em;
    }
    .reply-actions {
      display: flex;
      gap: 1em;
      justify-content: center;
      margin-top: 0.7em;
    }
    .reply-actions button {
      background: linear-gradient(90deg, #f9c7d1, #f7e9f0);
      border-radius: 12px;
      padding: 0.8em 1.5em;
      font-size: 1rem;
      border: none;
      transition: 0.2s;
      box-shadow: 0 2px 4px rgba(0,0,0,0.08);
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0.5em;
    }
    .reply-actions button:hover {
      background: linear-gradient(90deg, #f7e9f0, #f9c7d1);
      color: #c94f7c;
    }
    .scrollable-chat {
      max-width: 640px;
      margin: auto;
    }
    @media (max-width: 700px) {
      .user-card, .reply-box, .scrollable-chat {
        max-width: 98vw;
        padding: 1em 0.5em;
      }
      .reply-actions { flex-direction: column; gap: 0.7em; }
    }
    </style>
    ''', unsafe_allow_html=True)

    # タイトルを親しみやすく小さめに
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
    if st.button("📥 最新メッセージを取得", key="fetch_messages", use_container_width=True):
        # メッセージ取得＆自動返信生成
        if not st.session_state.user_email:
            st.error("メールアドレスを入力してください")
        else:
            storage_file = os.path.join(COOKIES_DIR, f"{st.session_state.user_email}_storage.json")
            if not os.path.exists(storage_file):
                st.error("cookieファイルがありません。手動でcookieを保存してください")
            else:
                try:
                    with st.spinner("メッセージと返信を取得中..."):
                        with sync_playwright() as p:
                            browser = p.chromium.launch(headless=True)
                            context = load_cookies(browser, st.session_state.user_email)
                            if context is None:
                                st.error("cookieファイルの読み込みに失敗しました")
                                browser.close()
                            else:
                                page = context.new_page()
                                messages = get_latest_messages(page)
                                st.session_state.messages = messages if messages else []
                                # 返信候補を自動生成
                                st.session_state.replies = []
                                for msg in st.session_state.messages:
                                    reply = generate_reply(msg, st.session_state.persona)
                                    st.session_state.replies.append(reply)
                                context.close()
                                browser.close()
                except Exception as e:
                    st.error(f"エラーが発生しました: {str(e)}")

    st.subheader("メッセージ一覧")
    # スクロール可能なチャットエリア
    with st.container():
        st.markdown('<div class="scrollable-chat">', unsafe_allow_html=True)
        for i, message in enumerate(st.session_state.messages):
            st.markdown(f"<div class='user-card'><b>{message['sender']}</b> <span style='color:#888;font-size:0.9em;'>({message['time']})</span></div>", unsafe_allow_html=True)
            st.code(message['content'], language="")  # 本文を全文表示
            if 'replies' in st.session_state and i < len(st.session_state.replies):
                reply = st.session_state.replies[i]
                with st.container():
                    st.markdown("<div class='reply-box'>", unsafe_allow_html=True)
                    st.text_area("返信文", reply, key=f"reply_area_{i}", height=100)
                    copy_to_clipboard_button(reply, "📋 コピー", "✅ コピーしました！")
                    if st.button("🔄 再作成", key=f"regen_reply_{i}"):
                        st.session_state.replies[i] = generate_reply(message, st.session_state.persona)
                        st.experimental_rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
            if i < len(st.session_state.messages) - 1:
                st.markdown("<hr style='margin:0.5em 0;' />", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main() 