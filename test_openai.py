import openai
import os

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
response = client.chat.completions.create(
    model="gpt-4-turbo-preview",
    messages=[
        {"role": "system", "content": "あなたはYYCのメッセージ返信アシスタントです。ユーザーからのメッセージに対して、YYCのブランドイメージに合わせた丁寧で親切な返信を作成してください。返信は簡潔で分かりやすく、必要に応じて具体的な情報や提案を含めてください。"},
        {"role": "user", "content": "YYCのサービスについて詳しく知りたいです。"}
    ],
    temperature=0.7,
    max_tokens=1000
)
print(response.choices[0].message.content) 