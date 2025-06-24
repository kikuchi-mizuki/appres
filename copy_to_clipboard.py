import streamlit as st
import streamlit.components.v1 as components
import uuid
from typing import Optional

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
    Displays a button that copies the given text to the clipboard when clicked.
    """
    if key is None:
        key = str(uuid.uuid4())
    button_id = f"copy-btn-{key}"
    success_id = f"copy-success-{key}"
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
    btn_style = style or f"""
        display:inline-block;padding:0.5em 1.2em;font-size:{size};color:{color};background:{background};border:none;border-radius:{border_radius};font-family:{font_family};cursor:pointer;transition:0.2s;"
    """
    html = f"""
    {js}
    <button id="{button_id}" data-copy-text="{text}" onclick="copyToClipboard_{key}()" style='{btn_style}'>
        {icon} {label}
    </button>
    """
    components.html(html, height=40) 