from vps_bot.services.resources import resources_text
from vps_bot.telegram.keyboards import (
    BTN_HELP,
    BTN_LOGS,
    BTN_RESOURCES,
    BTN_RESTART,
    BTN_START,
    BTN_STATUS,
    BTN_STOP,
    confirmation_keyboard,
    main_menu,
)


class BotHandlers:
    def __init__(self, settings, telegram, minecraft):
        self.settings = settings
        self.telegram = telegram
        self.minecraft = minecraft

    def handle_update(self, update):
        if "message" in update:
            self.handle_text(update["message"])
        elif "callback_query" in update:
            self.handle_callback(update["callback_query"])

    def is_admin(self, user_id):
        return user_id in self.settings.admin_ids

    def handle_text(self, message):
        chat_id = message["chat"]["id"]
        user_id = message.get("from", {}).get("id")
        text = message.get("text", "").strip()
        command = text.split()[0].split("@")[0].lower() if text else ""
        key = text.casefold()

        if not self.is_admin(user_id):
            self.telegram.send_message(chat_id, "Нет доступа.")
            print("Denied user_id={}".format(user_id), flush=True)
            return

        if command in ("/start", "/help") or key in (BTN_HELP.casefold(), "меню"):
            self.telegram.send_message(chat_id, help_text(), reply_markup=main_menu())
        elif command == "/status" or key == BTN_STATUS.casefold():
            self.telegram.send_message(chat_id, self.minecraft.status_text(), reply_markup=main_menu())
        elif command == "/resources" or key == BTN_RESOURCES.casefold():
            self.telegram.send_message(chat_id, resources_text(), reply_markup=main_menu())
        elif command == "/mc_start" or key == BTN_START.casefold():
            self.minecraft.start(chat_id)
        elif command == "/mc_stop" or key == BTN_STOP.casefold():
            self.telegram.send_message(
                chat_id,
                "<b>Остановить Minecraft?</b>\nИгроков лучше предупредить заранее.",
                reply_markup=confirmation_keyboard("stop"),
            )
        elif command == "/mc_restart" or key == BTN_RESTART.casefold():
            self.telegram.send_message(
                chat_id,
                "<b>Перезапустить Minecraft?</b>\nСервер будет остановлен и запущен заново.",
                reply_markup=confirmation_keyboard("restart"),
            )
        elif command == "/logs" or key == BTN_LOGS.casefold():
            self.minecraft.send_latest_log(chat_id)
        else:
            self.telegram.send_message(chat_id, help_text(), reply_markup=main_menu())

    def handle_callback(self, callback):
        user_id = callback.get("from", {}).get("id")
        message = callback.get("message") or {}
        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")
        data = callback.get("data")

        if not self.is_admin(user_id):
            self.telegram.answer_callback_query(callback["id"], text="Нет доступа.", show_alert=True)
            return

        self.telegram.answer_callback_query(callback["id"])

        if data == "cancel":
            self.telegram.edit_message(chat_id, message_id, "Действие отменено.")
        elif data == "do_stop":
            self.minecraft.stop(chat_id, message_id)
        elif data == "do_restart":
            self.minecraft.restart(chat_id, message_id)


def help_text():
    return (
        "<b>Arclight Console</b>\n"
        "Управление сервером теперь через кнопки ниже.\n\n"
        "<b>{}</b> - состояние systemd, ядра и порта\n"
        "<b>{}</b> - CPU, RAM и диск VPS\n"
        "<b>{}</b> - запуск с ожиданием строки Done\n"
        "<b>{}</b> - остановка с подтверждением\n"
        "<b>{}</b> - перезапуск с подтверждением\n"
        "<b>{}</b> - отправить latest.log файлом"
    ).format(BTN_STATUS, BTN_RESOURCES, BTN_START, BTN_STOP, BTN_RESTART, BTN_LOGS)
