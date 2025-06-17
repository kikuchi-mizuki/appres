#!/bin/bash

# コンテナIDを取得
CONTAINER_ID=$(docker ps -qf "name=appres")

if [ -z "$CONTAINER_ID" ]; then
    echo "Error: appresコンテナが見つかりません"
    exit 1
fi

# デバッグファイルをコンテナからローカルにコピー
echo "デバッグファイルを取得中..."
docker cp $CONTAINER_ID:/app/send_form_outer_debug.html ./send_form_outer_debug.html
docker cp $CONTAINER_ID:/app/send_form_outer_debug_after_wait.html ./send_form_outer_debug_after_wait.html
docker cp $CONTAINER_ID:/app/send_form_outer_debug_after_scroll.html ./send_form_outer_debug_after_scroll.html
docker cp $CONTAINER_ID:/app/send_form_no_button.png ./send_form_no_button.png
docker cp $CONTAINER_ID:/app/send_form_no_button_after_wait.png ./send_form_no_button_after_wait.png
docker cp $CONTAINER_ID:/app/send_form_no_button_after_scroll.png ./send_form_no_button_after_scroll.png
docker cp $CONTAINER_ID:/app/page_full_debug.html ./page_full_debug.html

echo "完了！" 