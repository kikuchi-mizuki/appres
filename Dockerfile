FROM python:3.12-slim

# 必要なパッケージをインストール
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxcb1 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリを設定
WORKDIR /app

# 環境変数を設定
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99

# 依存関係ファイルをコピー
COPY requirements.txt .

# 依存関係をインストール
RUN pip install --no-cache-dir -r requirements.txt

# Playwrightのブラウザをインストール
RUN playwright install chromium
RUN playwright install-deps

# アプリケーションのファイルをコピー
COPY . .

# ポートを公開
ENV PORT=8501
EXPOSE $PORT

# ヘルスチェック用のスクリプトを作成
RUN echo '#!/bin/bash\nfor i in {1..30}; do\n  curl -f http://localhost:$PORT/_stcore/health && exit 0\n  sleep 2\ndone\nexit 1' > /app/healthcheck.sh \
    && chmod +x /app/healthcheck.sh

# アプリケーションを起動
CMD Xvfb :99 -screen 0 1024x768x16 & sleep 10 && streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 