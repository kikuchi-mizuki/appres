# 送信ボタンをクリック
try:
    # 送信フォームのHTML全体を保存
    send_form_html = await page.locator('form#send-mail-form').inner_html()
    with open('send_form_debug.html', 'w', encoding='utf-8') as f:
        f.write(send_form_html)
    logger.info(f"送信フォームHTML: {send_form_html[:1000]}...")  # 最初の1000文字をログ出力

    # 送信ボタンの状態を確認
    send_button = page.locator('form#send-mail-form input[type="submit"], form#send-mail-form button[type="submit"]')
    is_visible = await send_button.is_visible()
    is_enabled = await send_button.is_enabled()
    button_html = await send_button.evaluate('el => el.outerHTML')
    logger.info(f"送信ボタン: visible={is_visible}, enabled={is_enabled}")
    logger.info(f"送信ボタンouterHTML: {button_html}")

    # 送信ボタンをクリック
    await send_button.click()
    logger.info("送信ボタンをクリックしました")

    # 送信後の状態を確認
    await page.wait_for_load_state('networkidle')
    current_url = page.url
    logger.info(f"送信後のURL: {current_url}")

    # 送信成功を確認
    if '/my/mail_box/history/' in current_url:
        logger.info("送信成功を確認: URLが履歴ページに遷移")
    else:
        logger.warning(f"送信後のURLが想定外: {current_url}")

except Exception as e:
    logger.error(f"送信ボタンのクリックに失敗: {str(e)}")
    # スクリーンショットを保存
    await page.screenshot(path='send_button_error.png')
    raise 