FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    unzip \
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
    libxshmfence1 \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright
RUN pip install --no-cache-dir playwright

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Playwrightのブラウザを必ずインストール
RUN playwright install chromium

# Create healthcheck script
RUN echo '#!/bin/bash\nnc -z localhost $PORT && curl -s http://localhost:$PORT/ > /dev/null' > /app/healthcheck.sh \
    && chmod +x /app/healthcheck.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE $PORT

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD /app/healthcheck.sh

# Create start script with direct environment variable handling
RUN echo '#!/bin/bash\n\
echo "=== Environment Variables ==="\n\
env | grep PORT\n\
echo "==========================="\n\
\n\
PORT=${PORT:-8501}\n\
echo "Using PORT=$PORT"\n\
\n\
exec streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0' > /app/start.sh \
    && chmod +x /app/start.sh

# Start Streamlit application (using explicit bash path)
CMD ["/bin/bash", "/app/start.sh"] 