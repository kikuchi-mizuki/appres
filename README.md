# YYCメッセージ返信アシスタント（Railwayデプロイ用）

YYCのメッセージを自動で取得し、ChatGPTを使用して返信を生成する半自動返信アシスタントです。

## 機能

- YYCのメッセージページから最新メッセージを取得
- ChatGPTを使用した自然な返信の生成
- カスタマイズ可能なペルソナ設定
- コピー＆ペースト可能な返信文

## セットアップ

1. 必要なパッケージのインストール:
```bash
pip install -r requirements.txt
```

2. 環境変数の設定:
`.env`ファイルを作成し、以下の内容を追加:
```
OPENAI_API_KEY=your_api_key_here
```

## 使用方法

1. アプリケーションの起動:
```bash
streamlit run app.py
```

2. ブラウザで表示されるインターフェースで:
   - サイドバーでペルソナを設定
   - YYCのメッセージページのURLを入力
   - 「メッセージを取得」ボタンをクリック
   - 生成された返信を確認し、必要に応じてコピー

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