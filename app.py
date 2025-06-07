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

st.write("Hello, world! (init OK)") 