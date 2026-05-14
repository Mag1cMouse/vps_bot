import json
import os
import sys
from urllib.error import HTTPError
import urllib.parse
import urllib.request


def main():
    token = os.environ.get("TELEGRAM_STATUS_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_STATUS_CHAT_ID")
    text = os.environ.get("TELEGRAM_MESSAGE")

    if not token or not chat_id:
        print("::warning::Telegram notification skipped: TELEGRAM_STATUS_BOT_TOKEN or TELEGRAM_STATUS_CHAT_ID is empty")
        return 0

    if not text:
        print("::error::Telegram notification failed: TELEGRAM_MESSAGE is empty")
        return 1

    body = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    url = "https://api.telegram.org/bot{}/sendMessage".format(token)

    try:
        with urllib.request.urlopen(url, data=body, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        print("::error::Telegram notification request failed: HTTP {} {}".format(exc.code, details))
        return 1
    except Exception as exc:
        print("::error::Telegram notification request failed: {}".format(exc))
        return 1

    if not payload.get("ok"):
        print("::error::Telegram notification rejected: {}".format(payload))
        return 1

    print("Telegram notification sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
