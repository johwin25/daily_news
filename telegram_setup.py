"""Read bot identity and private chat candidates; never send or select a chat."""
import json
import re
from news_delivery import DeliveryError, telegram_call


def main():
    try:
        bot = telegram_call("getMe", {})
        username = bot.get("username", "")
        if not re.fullmatch(r"[A-Za-z0-9_]{5,64}", username):
            raise DeliveryError("telegram_bot_identity_unavailable")
        print("Your bot: https://t.me/" + username)
        updates = telegram_call("getUpdates", {"limit": 100, "timeout": 0,
                                                "allowed_updates": ["message"]})
        candidates = {}
        for update in updates:
            chat = update.get("message", {}).get("chat", {})
            if chat.get("type") == "private" and type(chat.get("id")) is int:
                candidates[chat["id"]] = {"id": chat["id"], "first_name": chat.get("first_name", ""),
                                          "username": chat.get("username", "")}
        if not candidates:
            print("Open your bot in Telegram, tap Start, then run this setup again.")
            return 1
        for chat in candidates.values():
            print("Private chat candidate: " + json.dumps(chat, ensure_ascii=True))
        print("Choose your own chat ID and save it as TELEGRAM_CHAT_ID in GitHub Actions secrets.")
        print("No recipient was selected and no message was sent.")
        return 0
    except DeliveryError as error:
        print("FAIL: " + str(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
