import json
import os
import urllib.parse
import urllib.request
import uuid


class TelegramClient:
    def __init__(self, token):
        self.api_url = "https://api.telegram.org/bot{}/".format(token)

    def request(self, method, data=None, timeout=40):
        body = urllib.parse.urlencode(data or {}).encode()
        request = urllib.request.Request(self.api_url + method, data=body)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read())

        if not result.get("ok"):
            raise RuntimeError(result)
        return result["result"]

    def request_multipart(self, method, fields, file_field, path, timeout=120):
        boundary = "----CodexBoundary" + uuid.uuid4().hex
        body = bytearray()

        def add(part):
            body.extend(part if isinstance(part, bytes) else part.encode())

        for name, value in fields.items():
            add("--{}\r\n".format(boundary))
            add('Content-Disposition: form-data; name="{}"\r\n\r\n'.format(name))
            add(str(value))
            add("\r\n")

        filename = os.path.basename(path)
        add("--{}\r\n".format(boundary))
        add('Content-Disposition: form-data; name="{}"; filename="{}"\r\n'.format(file_field, filename))
        add("Content-Type: text/plain\r\n\r\n")
        with open(path, "rb") as file:
            body.extend(file.read())
        add("\r\n--{}--\r\n".format(boundary))

        request = urllib.request.Request(
            self.api_url + method,
            data=bytes(body),
            headers={"Content-Type": "multipart/form-data; boundary={}".format(boundary)},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read())

        if not result.get("ok"):
            raise RuntimeError(result)
        return result["result"]

    def delete_webhook(self, drop_pending_updates=False):
        return self.request(
            "deleteWebhook",
            {"drop_pending_updates": "true" if drop_pending_updates else "false"},
        )

    def set_my_commands(self, commands):
        return self.request("setMyCommands", {"commands": json.dumps(commands, ensure_ascii=False)})

    def get_updates(self, offset, timeout=30, allowed_updates=None):
        return self.request(
            "getUpdates",
            {
                "offset": offset,
                "timeout": timeout,
                "allowed_updates": json.dumps(allowed_updates or ["message", "callback_query"]),
            },
            timeout=timeout + 15,
        )

    def send_message(self, chat_id, text, reply_markup=None):
        data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
        return self.request("sendMessage", data)

    def edit_message(self, chat_id, message_id, text, reply_markup=None):
        data = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)

        try:
            return self.request("editMessageText", data)
        except Exception as exc:
            print("Edit failed:", repr(exc), flush=True)
            return None

    def answer_callback_query(self, callback_query_id, text=None, show_alert=False):
        data = {"callback_query_id": callback_query_id}
        if text is not None:
            data["text"] = text
        if show_alert:
            data["show_alert"] = "true"
        return self.request("answerCallbackQuery", data)

    def send_document(self, chat_id, path, caption=None):
        self.request("sendChatAction", {"chat_id": chat_id, "action": "upload_document"})
        fields = {"chat_id": chat_id}
        if caption:
            fields["caption"] = caption
        return self.request_multipart("sendDocument", fields, "document", path)
