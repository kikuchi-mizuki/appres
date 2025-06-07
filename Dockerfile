FROM python:3.12-slim

# 必要なパッケージをインストール（分割して実行）
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    gnupg \
    curl \
    netcat \
    && rm -rf /var/lib/apt/lists/*

# X11関連パッケージのインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
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
ENV PORT=8501

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
EXPOSE $PORT

# 起動スクリプトを作成
RUN echo '#!/bin/bash\n\
set -e\n\
echo "Starting Xvfb..."\n\
Xvfb :99 -screen 0 1024x768x16 &\n\
sleep 5\n\
echo "Starting Streamlit..."\n\
streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 &\n\
echo "Waiting for Streamlit to start..."\n\
for i in {1..30}; do\n\
  echo "Attempt $i: Checking Streamlit..."\n\
  if nc -z localhost $PORT; then\n\
    echo "Port $PORT is open"\n\
    if curl -s http://localhost:$PORT/_stcore/health > /dev/null; then\n\
      echo "Streamlit is ready!"\n\
      exit 0\n\
    fi\n\
  fi\n\
  echo "Waiting 10 seconds..."\n\
  sleep 10\n\
done\n\
echo "Streamlit failed to start"\n\
exit 1' > /app/start.sh \
    && chmod +x /app/start.sh

# ヘルスチェック用のスクリプトを作成
RUN echo '#!/bin/bash\n\
nc -z localhost $PORT && curl -s http://localhost:$PORT/_stcore/health > /dev/null' > /app/healthcheck.sh \
    && chmod +x /app/healthcheck.sh

# アプリケーションを起動
CMD ["/app/start.sh"] 