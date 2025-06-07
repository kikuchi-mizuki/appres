# YYC Auto Reply Assistant

This is a Streamlit application that automates message replies using Selenium and OpenAI.

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/kikuchi-mizuki/appres.git
   cd appres
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the root directory and add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

4. Run the application:
   ```bash
   streamlit run app.py
   ```

## Usage

- Upload your cookie file to start the automated reply process.
- The application will automatically check for new messages and generate replies using OpenAI.
- Use the sidebar to configure settings like model selection and notification preferences.

## Deployment

This application is configured for deployment on Railway. Follow the deployment instructions provided by Railway to deploy the application.

## 機能

- YYCのメッセージページから最新メッセージを取得
- ChatGPTを使用した自然な返信の生成
- カスタマイズ可能なペルソナ設定
- コピー＆ペースト可能な返信文

## 注意事項

- このアプリケーションは自動ログインや自動送信を行いません
- 生成された返信は必ず確認してから使用してください
- YYCの利用規約に従って使用してください

## デプロイ手順

1. このリポジトリをGitHubにpush
2. RailwayでNew Project → GitHubリポジトリを選択
3. `OPENAI_API_KEY` などの環境変数をRailwayのVariablesに追加
4. デプロイ後、発行されたURLでアクセス

## 必要ファイル
- requirements.txt
- Procfile
- .env（.env.exampleを参考に）

## 注意
- Selenium/ChromeDriverはchromedriver-autoinstallerで自動インストールされます
- Cookieファイルのアップロードやストレージの扱いに注意 