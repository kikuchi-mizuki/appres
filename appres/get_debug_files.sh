#!/bin/bash

# コンテナIDを取得
CONTAINER_ID=$(docker ps -qf "name=appres")

if [ -z "$CONTAINER_ID" ]; then
    echo "Error: appresコンテナが見つかりません"
    exit 1
fi

# デバッグファイルをローカルにコピー
echo "デバッグファイルをコピー中..."
docker cp $CONTAINER_ID:/app/send_form_debug.html ./send_form_debug.html
docker cp $CONTAINER_ID:/app/send_form_outer_debug.html ./send_form_outer_debug.html
docker cp $CONTAINER_ID:/app/send_button_error.png ./send_button_error.png
docker cp $CONTAINER_ID:/app/send_form_no_button.png ./send_form_no_button.png

echo "デバッグファイルのコピーが完了しました" 