import html
import os
import re
import shutil
import time
from datetime import datetime

from vps_bot.services.logs import ready_line
from vps_bot.services.systemd import run_command
from vps_bot.telegram.keyboards import BTN_LOGS


class MinecraftService:
    def __init__(self, settings, telegram, systemd, log):
        self.settings = settings
        self.telegram = telegram
        self.systemd = systemd
        self.log = log

    def status_text(self):
        active, state = self.systemd.is_active()
        info = self.systemd.show_info()
        ready = ready_line(self.log.tail()) if active else None
        port = self.port_listening()

        lines = ["<b>Minecraft server</b>"]
        if getattr(self.systemd, "is_mock", False):
            lines.append("Режим: <b>dev/mock</b>, systemd-команды не выполняются")

        lines.append("Сервис: <b>{}</b> ({})".format("запущен" if active else "остановлен", html.escape(state)))

        if active and ready:
            lines.append("Ядро: <b>готово</b>")
        elif active:
            lines.append("Ядро: <b>загружается или latest.log недоступен</b>")
        else:
            lines.append("Ядро: не запущено")

        if info.get("MainPID") and info["MainPID"] != "0":
            lines.append("PID: <code>{}</code>".format(html.escape(info["MainPID"])))
        if info.get("ActiveEnterTimestamp"):
            lines.append("Запущен с: <code>{}</code>".format(html.escape(info["ActiveEnterTimestamp"])))

        if port is True:
            lines.append("Порт {}: слушается".format(self.settings.mc_port))
        elif port is False:
            lines.append("Порт {}: не слушается".format(self.settings.mc_port))

        if ready:
            lines.append("")
            lines.append("<b>Готовность из latest.log:</b>")
            lines.append("<code>{}</code>".format(html.escape(ready[-300:])))

        return "\n".join(lines)

    def port_listening(self):
        if getattr(self.systemd, "is_mock", False):
            return None

        ss = shutil.which("ss") or "/usr/sbin/ss"
        code, output = run_command([ss, "-ltn"], timeout=5)
        if code != 0:
            return None
        return re.search(r"[:.]{}\s".format(self.settings.mc_port), output) is not None

    def start(self, chat_id):
        active, _ = self.systemd.is_active()
        if active:
            self.telegram.send_message(chat_id, "<b>Сервер уже запущен.</b>\n\n" + self.status_text())
            return

        if getattr(self.systemd, "is_mock", False):
            self.systemd.systemctl("start", timeout=1)
            self.telegram.send_message(
                chat_id,
                "<b>DEV: запуск сымитирован.</b>\n"
                "Команда systemd не выполнялась. Этот режим подходит для проверки тестового Telegram-бота с компьютера.",
            )
            return

        offset = self.log.size()
        message = self.telegram.send_message(chat_id, "<b>Запуск Minecraft</b>\nОтправил команду systemd, жду процесс Java.")
        code, output = self.systemd.systemctl("start", timeout=30)
        if code != 0:
            self.telegram.edit_message(message["chat"]["id"], message["message_id"], fail_text("Не удалось запустить сервер", output))
            return

        self.wait_ready(chat_id, message["message_id"], offset, "Запуск Minecraft")

    def stop(self, chat_id, message_id=None):
        active, _ = self.systemd.is_active()
        if not active:
            text = "<b>Сервер уже остановлен.</b>"
            if message_id:
                self.telegram.edit_message(chat_id, message_id, text)
            else:
                self.telegram.send_message(chat_id, text)
            return

        if getattr(self.systemd, "is_mock", False):
            self.systemd.systemctl("stop", timeout=1)
            text = "<b>DEV: остановка сымитирована.</b>\nКоманда systemd не выполнялась."
            if message_id:
                self.telegram.edit_message(chat_id, message_id, text)
            else:
                self.telegram.send_message(chat_id, text)
            return

        if message_id:
            self.telegram.edit_message(chat_id, message_id, "<b>Остановка Minecraft</b>\nЖду корректное завершение и сохранение мира.")
        else:
            message = self.telegram.send_message(chat_id, "<b>Остановка Minecraft</b>\nЖду корректное завершение и сохранение мира.")
            message_id = message["message_id"]

        code, output = self.systemd.systemctl("stop", timeout=self.settings.stop_timeout)
        active, _ = self.systemd.is_active()

        if code == 0 and not active:
            self.telegram.edit_message(chat_id, message_id, "<b>Остановка завершена.</b>\nMinecraft-сервис остановлен.")
        elif not active:
            self.telegram.edit_message(
                chat_id,
                message_id,
                "<b>Сервис остановлен.</b>\nSystemd ответил: <code>{}</code>".format(html.escape(output[-800:])),
            )
        else:
            self.telegram.edit_message(chat_id, message_id, fail_text("Не удалось остановить сервер", output or self.systemd.journal_tail()))

    def restart(self, chat_id, message_id=None):
        if getattr(self.systemd, "is_mock", False):
            self.systemd.systemctl("restart", timeout=1)
            text = "<b>DEV: перезапуск сымитирован.</b>\nКоманда systemd не выполнялась."
            if message_id:
                self.telegram.edit_message(chat_id, message_id, text)
            else:
                self.telegram.send_message(chat_id, text)
            return

        offset = self.log.size()

        if message_id:
            self.telegram.edit_message(chat_id, message_id, "<b>Перезапуск Minecraft</b>\nОстанавливаю сервер и жду новый старт.")
        else:
            message = self.telegram.send_message(chat_id, "<b>Перезапуск Minecraft</b>\nОстанавливаю сервер и жду новый старт.")
            message_id = message["message_id"]

        code, output = self.systemd.systemctl("restart", timeout=self.settings.stop_timeout + 30)
        if code != 0:
            self.telegram.edit_message(chat_id, message_id, fail_text("Не удалось перезапустить сервер", output))
            return

        self.wait_ready(chat_id, message_id, offset, "Перезапуск Minecraft")

    def wait_ready(self, chat_id, message_id, offset, title):
        started = time.monotonic()
        last_edit = 0

        if not self.log.readable():
            time.sleep(3)
            active, state = self.systemd.is_active()
            message = (
                "<b>{}</b>\n"
                "Сервис: <b>{}</b>\n"
                "Не могу прочитать <code>{}</code>, поэтому не вижу строку готовности ядра."
            ).format(title, "запущен" if active else html.escape(state), html.escape(self.log.path))
            self.telegram.edit_message(chat_id, message_id, message)
            return

        while time.monotonic() - started < self.settings.start_timeout:
            active, _ = self.systemd.is_active()
            if not active:
                self.telegram.edit_message(
                    chat_id,
                    message_id,
                    fail_text("{}: сервер остановился во время запуска".format(title), self.systemd.journal_tail()),
                )
                return

            new_log = self.log.read_from(offset)
            line = ready_line(new_log)
            if line:
                elapsed = int(time.monotonic() - started)
                self.telegram.edit_message(
                    chat_id,
                    message_id,
                    "<b>{}: готово</b>\n"
                    "Ядро загрузилось за <code>{} сек.</code>\n\n"
                    "<code>{}</code>".format(title, elapsed, html.escape(line[-400:])),
                )
                return

            now = time.monotonic()
            if now - last_edit >= 8:
                elapsed = int(now - started)
                self.telegram.edit_message(
                    chat_id,
                    message_id,
                    "<b>{}</b>\n"
                    "Сервис запущен, жду полной загрузки Arclight.\n"
                    "Прошло: <code>{} сек.</code>\n"
                    "Таймаут: <code>{} сек.</code>".format(title, elapsed, self.settings.start_timeout),
                )
                last_edit = now

            time.sleep(3)

        self.telegram.edit_message(
            chat_id,
            message_id,
            "<b>{}: таймаут ожидания</b>\n"
            "Systemd считает сервис активным, но строка <code>Done (...)</code> не появилась за {} сек.\n"
            "Проверь кнопку <b>{}</b>.".format(title, self.settings.start_timeout, BTN_LOGS),
        )

    def send_latest_log(self, chat_id):
        if not self.log.exists():
            self.telegram.send_message(chat_id, "Файл логов не найден:\n<code>{}</code>".format(html.escape(self.log.path)))
            return

        if not self.log.readable():
            self.telegram.send_message(chat_id, "Нет доступа к файлу:\n<code>{}</code>".format(html.escape(self.log.path)))
            return

        size = os.path.getsize(self.log.path)
        if size > self.settings.max_log_mb * 1024 * 1024:
            self.telegram.send_message(chat_id, "Файл latest.log слишком большой: <code>{:.1f} MB</code>.".format(size / 1024**2))
            return

        caption = "latest.log, {:.1f} KB, {}".format(size / 1024, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.telegram.send_document(chat_id, self.log.path, caption=caption)


def fail_text(title, output):
    output = html.escape((output or "Нет вывода.")[-2500:])
    return "<b>{}</b>\n\n<pre>{}</pre>".format(html.escape(title), output)
