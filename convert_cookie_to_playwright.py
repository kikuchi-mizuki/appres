import json

# 入力ファイル名（Chrome拡張でエクスポートしたjson）
INPUT_FILE = "chrome_export.json"
# 出力ファイル名（Playwright用）
OUTPUT_FILE = "playwright_cookies.json"

def convert_cookie(c):
    return {
        "name": c["name"],
        "value": c["value"],
        "domain": c["domain"],
        "path": c.get("path", "/"),
        "expires": int(c["expirationDate"]) if "expirationDate" in c else -1,
        "httpOnly": c.get("httpOnly", False),
        "secure": c.get("secure", False),
        "sameSite": (
            "None" if c.get("sameSite") in (None, "no_restriction") else
            "Lax" if c.get("sameSite") == "lax" else
            "Strict" if c.get("sameSite") == "strict" else "Lax"
        )
    }

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    chrome_cookies = json.load(f)

playwright_cookies = [convert_cookie(c) for c in chrome_cookies]

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(playwright_cookies, f, ensure_ascii=False, indent=2)

print(f"変換完了: {OUTPUT_FILE}") 