from vps_bot.services.build_info import build_info_text
from vps_bot.services.resources import resources_text
from vps_bot.telegram.keyboards import (
    BTN_BACKUP,
    BTN_HELP,
    BTN_LOGS,
    BTN_PLAYERS,
    BTN_RESOURCES,
    BTN_RESTART,
    BTN_START,
    BTN_STATUS,
    BTN_STOP,
    BTN_TPS,
    BTN_VERSION,
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
        elif command == "/players" or key == BTN_PLAYERS.casefold():
            self.telegram.send_message(chat_id, self.minecraft.players_text(), reply_markup=main_menu())
        elif command == "/tps" or key == BTN_TPS.casefold():
            self.minecraft.send_rcon_command(chat_id, "tps", title="TPS")
        elif command == "/backup" or key == BTN_BACKUP.casefold():
            self.minecraft.backup(chat_id)
        elif command == "/version" or key == BTN_VERSION.casefold():
            self.telegram.send_message(chat_id, build_info_text(self.settings.project_root), reply_markup=main_menu())
        elif command == "/say":
            argument = command_argument(text)
            if not argument:
                self.telegram.send_message(chat_id, "<b>Использование:</b> /say <текст>", reply_markup=main_menu())
                return
            self.minecraft.send_rcon_command(chat_id, "say {}".format(argument), title="Say")
        elif command == "/cmd":
            argument = command_argument(text)
            if not argument:
                self.telegram.send_message(chat_id, "<b>Использование:</b> /cmd <команда Minecraft>", reply_markup=main_menu())
                return
            self.minecraft.send_rcon_command(chat_id, argument, title="RCON")
        elif command in ("/whitelist_add", "/whitelist_remove"):
            argument = command_argument(text)
            if not argument:
                self.telegram.send_message(
                    chat_id,
                    "<b>Использование:</b> /{} <ник>".format(command.lstrip("/")),
                    reply_markup=main_menu(),
                )
                return
            action = "add" if command == "/whitelist_add" else "remove"
            self.minecraft.send_rcon_command(chat_id, "whitelist {} {}".format(action, argument), title="Whitelist")
        elif command == "/whitelist_list":
            self.minecraft.send_rcon_command(chat_id, "whitelist list", title="Whitelist")
        elif command in ("/kill", "/kick"):
            if len(text.split()) < 2:
                self.telegram.send_message(
                    chat_id,
                    "<b>Использование:</b> /{} <ник> [причина]".format(command.lstrip("/")),
                    reply_markup=main_menu(),
                )
                return
            raw_command = text[1:]
            self.minecraft.send_player_command(chat_id, raw_command)
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
        "<b>{}</b> - список игроков на сервере\n"
        "<b>{}</b> - TPS/MSPT через RCON\n"
        "<b>{}</b> - бэкап мира\n"
        "<b>{}</b> - текущий build/commit\n"
        "<b>{}</b> - запуск с ожиданием строки Done\n"
        "<b>{}</b> - остановка с подтверждением\n"
        "<b>{}</b> - перезапуск с подтверждением\n"
        "<b>{}</b> - отправить latest.log файлом\n\n"
        "<b>/say <текст></b> - написать в чат Minecraft\n"
        "<b>/cmd <команда></b> - выполнить RCON-команду\n"
        "<b>/whitelist_add <ник></b> - добавить игрока в whitelist\n"
        "<b>/whitelist_remove <ник></b> - удалить игрока из whitelist\n"
        "<b>/whitelist_list</b> - показать whitelist\n"
        "<b>/kill <ник></b> - отправить команду kill на сервер\n"
        "<b>/kick <ник> [причина]</b> - отправить команду kick на сервер"
    ).format(
        BTN_STATUS,
        BTN_RESOURCES,
        BTN_PLAYERS,
        BTN_TPS,
        BTN_BACKUP,
        BTN_VERSION,
        BTN_START,
        BTN_STOP,
        BTN_RESTART,
        BTN_LOGS,
    )


def command_argument(text):
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()
