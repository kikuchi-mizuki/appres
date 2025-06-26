import streamlit as st
import streamlit.components.v1 as components
import uuid
from typing import Optional

# クリップボードにテキストをコピーするボタンを表示する関数
# text: コピーしたいテキスト
# label: ボタンに表示するラベル
# success_label: コピー成功時に表示するラベル
# key: 複数ボタンを使う場合の一意なキー
# timeout: コピー成功表示の持続時間（ミリ秒）
# icon: ボタンに表示するアイコン
# success_icon: コピー成功時のアイコン
# size, color, border_radius, font_family, background, style: ボタンのデザイン調整用

def copy_to_clipboard_button(
    text: str,
    label: str = "Copy",
    success_label: str = "Copied!",
    key: Optional[str] = None,
    timeout: int = 2000,
    icon: str = "📋",
    success_icon: str = "✅",
    size: str = "1.1em",
    color: str = "#c94f7c",
    border_radius: str = "8px",
    font_family: str = "inherit",
    background: str = "#f9c7d1",
    style: Optional[str] = None,
):
    """
    指定したテキストをクリップボードにコピーするボタンをStreamlit上に表示します。
    ボタンをクリックすると、テキストがクリップボードにコピーされ、一定時間ラベルが変化します。
    """
    # keyが未指定ならランダムなUUIDを使う（複数ボタン対応）
    if key is None:
        key = str(uuid.uuid4())
    button_id = f"copy-btn-{key}"
    success_id = f"copy-success-{key}"
    # JavaScriptでクリップボードにコピーし、ラベルを一時的に変更
    js = f"""
    <script>
    function copyToClipboard_{key}() {{
        var text = document.getElementById('{button_id}').getAttribute('data-copy-text');
        navigator.clipboard.writeText(text).then(function() {{
            var btn = document.getElementById('{button_id}');
            var original = btn.innerHTML;
            btn.innerHTML = '{success_icon} {success_label}';
            setTimeout(function() {{ btn.innerHTML = '{icon} {label}'; }}, {timeout});
        }});
    }}
    </script>
    """
    # ボタンのCSSスタイル
    btn_style = style or f"""
        display:inline-block;padding:0.5em 1.2em;font-size:{size};color:{color};background:{background};border:none;border-radius:{border_radius};font-family:{font_family};cursor:pointer;transition:0.2s;"
    """
    # HTMLとしてボタン＋JSを埋め込む
    html = f"""
    {js}
    <button id="{button_id}" data-copy-text="{text}" onclick="copyToClipboard_{key}()" style='{btn_style}'>
        {icon} {label}
    </button>
    """
    # StreamlitのcomponentsでHTMLを表示
    components.html(html, height=40) 