# 送信ボタンをクリック
try:
    # 送信フォームのHTML全体を保存
    send_form_html = await page.locator('form#send-mail-form').inner_html()
    with open('send_form_debug.html', 'w', encoding='utf-8') as f:
        f.write(send_form_html)
    logger.info(f"送信フォームHTML: {send_form_html[:1000]}...")  # 最初の1000文字をログ出力

    # 送信フォームのouterHTMLを保存
    send_form_outer_html = await page.locator('form#send-mail-form').evaluate('el => el.outerHTML')
    with open('send_form_outer_debug.html', 'w', encoding='utf-8') as f:
        f.write(send_form_outer_html)
    logger.info(f"送信フォームouterHTML: {send_form_outer_html[:2000]}...")  # 先頭2000文字

    # 送信ボタンを全て取得してログ出力
    send_buttons = page.locator('form#send-mail-form input[type="submit"], form#send-mail-form button[type="submit"]')
    count = await send_buttons.count()
    logger.info(f"送信ボタン候補の数: {count}")
    for i in range(count):
        btn = send_buttons.nth(i)
        btn_html = await btn.evaluate('el => el.outerHTML')
        logger.info(f"送信ボタン{i} outerHTML: {btn_html}")

    if count == 0:
        logger.warning("送信ボタンがフォーム内に見つかりません。2秒待って再取得します。")
        await page.wait_for_timeout(2000)
        # 再取得
        send_form_outer_html2 = await page.locator('form#send-mail-form').evaluate('el => el.outerHTML')
        with open('send_form_outer_debug_after_wait.html', 'w', encoding='utf-8') as f:
            f.write(send_form_outer_html2)
        logger.info(f"[再取得]送信フォームouterHTML: {send_form_outer_html2[:2000]}...")
        send_buttons2 = page.locator('form#send-mail-form input[type=\"submit\"], form#send-mail-form button[type=\"submit\"]')
        count2 = await send_buttons2.count()
        logger.info(f"[再取得]送信ボタン候補の数: {count2}")
        for i in range(count2):
            btn2 = send_buttons2.nth(i)
            btn_html2 = await btn2.evaluate('el => el.outerHTML')
            logger.info(f"[再取得]送信ボタン{i} outerHTML: {btn_html2}")
        if count2 == 0:
            logger.warning("[再取得]送信ボタンがフォーム内に見つかりません。スクロール後に再取得します。")
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.wait_for_timeout(1000)
            send_form_outer_html3 = await page.locator('form#send-mail-form').evaluate('el => el.outerHTML')
            with open('send_form_outer_debug_after_scroll.html', 'w', encoding='utf-8') as f:
                f.write(send_form_outer_html3)
            logger.info(f"[スクロール後]送信フォームouterHTML: {send_form_outer_html3[:2000]}...")
            send_buttons3 = page.locator('form#send-mail-form input[type=\"submit\"], form#send-mail-form button[type=\"submit\"]')
            count3 = await send_buttons3.count()
            logger.info(f"[スクロール後]送信ボタン候補の数: {count3}")
            for i in range(count3):
                btn3 = send_buttons3.nth(i)
                btn_html3 = await btn3.evaluate('el => el.outerHTML')
                logger.info(f"[スクロール後]送信ボタン{i} outerHTML: {btn_html3}")
            if count3 == 0:
                logger.warning("[スクロール後]送信ボタンがフォーム内に見つかりません。フォーム全体のスクリーンショットを保存します。")
                await page.locator('form#send-mail-form').screenshot(path='send_form_no_button_after_scroll.png')

    # 送信ボタンをクリック
    await send_buttons.click()
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

    # ページ全体のHTMLを保存
    full_html = await page.content()
    with open('page_full_debug.html', 'w', encoding='utf-8') as f:
        f.write(full_html)
    logger.info(f"ページ全体のHTMLを保存しました（先頭2000文字）: {full_html[:2000]}...")

    # ページ全体から送信ボタン候補を自動抽出
    import re
    submit_buttons = re.findall(r'<(input|button)[^>]*type=["\"]submit["\"][^>]*>', full_html)
    logger.info(f"ページ全体から抽出した送信ボタン候補の数: {len(submit_buttons)}")
    for i, btn_html in enumerate(submit_buttons):
        logger.info(f"[全体探索]送信ボタン候補{i}: {btn_html}")

except Exception as e:
    logger.error(f"送信ボタンのクリックに失敗: {str(e)}")
    # スクリーンショットを保存
    await page.screenshot(path='send_button_error.png')
    raise 