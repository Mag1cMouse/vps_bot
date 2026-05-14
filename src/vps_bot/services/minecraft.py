import html
import os
import re
import shutil
import socket
import struct
import time
from datetime import datetime

from vps_bot.services.logs import ready_line
from vps_bot.services.systemd import run_command
from vps_bot.telegram.keyboards import BTN_LOGS

JOIN_RE = re.compile(r"^(.+?) joined the game$")
LOGIN_RE = re.compile(r"^(.+?)\[/[^\]]+\] logged in with entity id .*$")
LEAVE_RE = re.compile(r"^(.+?) left the game$")
LOST_RE = re.compile(r"^(.+?) lost connection.*$")
KICK_RE = re.compile(r"^(.+?) was kicked from the game(?:: .*)?$")
LIST_RE = re.compile(r"^There are (\d+) of a max(?: of)? (\d+) players online(?:: ?(.*))?$")


class MinecraftService:
    def __init__(self, settings, telegram, systemd, log):
        self.settings = settings
        self.telegram = telegram
        self.systemd = systemd
        self.log = log
        self.log_offset = 0
        self.rcon_host = settings.rcon_host
        self.rcon_port = settings.rcon_port
        self.rcon_password = settings.rcon_password

    def initialize_log_offset(self):
        self.log_offset = self.log.size() if self.log.exists() else 0

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

        player_state = self.player_state()
        if player_state is not None:
            count = player_state.get("count")
            players = player_state.get("players")
            if count is not None:
                lines.append("Игроков: <b>{}</b>".format(count))
            if players:
                lines.append("Ники: <code>{}</code>".format(html.escape(", ".join(players[:20]))))

        if ready:
            lines.append("")
            lines.append("<b>Готовность из latest.log:</b>")
            lines.append("<code>{}</code>".format(html.escape(ready[-300:])))

        return "\n".join(lines)

    def players_text(self):
        player_state = self.player_state()
        if not player_state:
            return "<b>Игроки:</b> данные недоступны. Проверь latest.log или дождись следующего входа/выхода."

        count = player_state.get("count")
        players = player_state.get("players")
        text = "<b>Игроки на сервере</b>\n"
        text += "Онлайн: <b>{}</b>\n".format(count)
        if players:
            text += "Ники: <code>{}</code>".format(html.escape(", ".join(players)))
        else:
            text += "Ники: <b>нет</b>"
        return text

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

    def process_log_events(self):
        if not self.log.exists() or not self.log.readable():
            return

        current_size = self.log.size()
        if current_size < self.log_offset:
            self.log_offset = 0
        if current_size == self.log_offset:
            return

        new_text = self.log.read_from(self.log_offset)
        self.log_offset = current_size
        if not new_text:
            return

        player_state = self.player_state()
        for event in self._parse_log_events(new_text):
            self._notify_player_event(event, player_state)

    def send_player_command(self, chat_id, raw_command):
        raw_command = raw_command.lstrip("/")
        if getattr(self.systemd, "is_mock", False):
            self.telegram.send_message(
                chat_id,
                "<b>DEV: команда не выполняется.</b>\nКоманда: <code>{}</code>".format(html.escape(raw_command)),
            )
            return

        if not self.rcon_password:
            self.telegram.send_message(
                chat_id,
                "<b>RCON не настроен.</b>\nДобавьте в .env.prod переменные MC_RCON_HOST, MC_RCON_PORT и MC_RCON_PASSWORD, затем перезапустите бота.",
            )
            return

        try:
            response = self._send_rcon_command(raw_command)
            if not response:
                response = "Команда отправлена."
            self.telegram.send_message(
                chat_id,
                "<b>Команда:</b> <code>{}</code>\n\n<pre>{}</pre>".format(html.escape(raw_command), html.escape(response[-2500:])),
            )
        except Exception as exc:
            self.telegram.send_message(chat_id, fail_text("Не удалось отправить команду", str(exc)))

    def player_state(self, text=None):
        if text is None:
            rcon_state = self._rcon_player_state()
            if rcon_state is not None:
                return rcon_state

        text = text or self.log.tail()
        if not text:
            return None

        players = self._rebuild_players_from_lines(text.splitlines())
        return {"count": len(players), "players": players}

    def _parse_log_events(self, text):
        events = []
        for line in text.splitlines():
            message = log_message(line)
            if match := JOIN_RE.match(message):
                events.append({"type": "join", "player": match.group(1)})
            elif match := LEAVE_RE.match(message):
                events.append({"type": "leave", "player": match.group(1)})
            elif match := LOST_RE.match(message):
                events.append({"type": "leave", "player": match.group(1)})
            elif match := KICK_RE.match(message):
                events.append({"type": "leave", "player": match.group(1)})
        return events

    def _notify_player_event(self, event, player_state):
        if not self.settings.admin_ids:
            return

        if event["type"] == "join":
            text = "<b>Игрок зашел на сервер</b>\n<code>{}</code>".format(html.escape(event["player"]))
        else:
            text = "<b>Игрок вышел с сервера</b>\n<code>{}</code>".format(html.escape(event["player"]))

        if player_state and player_state.get("count") is not None:
            text += "\nОнлайн: <b>{}</b>".format(player_state["count"])
        if player_state and player_state.get("players"):
            names = player_state["players"]
            text += "\nНики: <code>{}</code>".format(html.escape(", ".join(names[:20])))

        for admin_id in self.settings.admin_ids:
            self.telegram.send_message(admin_id, text)

    def _rebuild_players_from_lines(self, lines):
        players = []
        for line in lines:
            message = log_message(line)
            if match := LIST_RE.match(message):
                players = parse_player_list(match.group(3))
            elif match := JOIN_RE.match(message):
                name = match.group(1)
                if name not in players:
                    players.append(name)
            elif match := LOGIN_RE.match(message):
                name = match.group(1)
                if name not in players:
                    players.append(name)
            elif match := LEAVE_RE.match(message):
                name = match.group(1)
                if name in players:
                    players.remove(name)
            elif match := LOST_RE.match(message):
                name = match.group(1)
                if name in players:
                    players.remove(name)
            elif match := KICK_RE.match(message):
                name = match.group(1)
                if name in players:
                    players.remove(name)
        return players

    def _rcon_player_state(self):
        if getattr(self.systemd, "is_mock", False) or not self.rcon_password:
            return None

        try:
            response = self._send_rcon_command("list")
        except Exception as exc:
            print("RCON list failed:", repr(exc), flush=True)
            return None

        match = LIST_RE.search(response.strip())
        if not match:
            return None

        players = parse_player_list(match.group(3))
        return {"count": int(match.group(1)), "players": players}

    def _send_rcon_command(self, command):
        def recv_exact(sock, size):
            data = b""
            while len(data) < size:
                chunk = sock.recv(size - len(data))
                if not chunk:
                    raise RuntimeError("RCON: обрыв соединения")
                data += chunk
            return data

        with socket.create_connection((self.rcon_host, self.rcon_port), timeout=10) as sock:
            sock.settimeout(10)

            def send_packet(packet_id, packet_type, payload):
                payload_bytes = payload.encode("utf-8")
                packet = struct.pack("<iii", len(payload_bytes) + 10, packet_id, packet_type) + payload_bytes + b"\x00\x00"
                sock.sendall(packet)

                length_bytes = recv_exact(sock, 4)
                length = struct.unpack("<i", length_bytes)[0]
                body = recv_exact(sock, length) if length else b""
                response_id, response_type = struct.unpack("<ii", body[:8])
                payload = body[8:-2].decode("utf-8", errors="replace")
                return response_id, payload

            response_id, _ = send_packet(1, 3, self.rcon_password)
            if response_id == -1:
                raise RuntimeError("RCON: неверный пароль")

            response_id, payload = send_packet(2, 2, command)
            if response_id == -1:
                raise RuntimeError("RCON: команда отклонена")
            return payload


def fail_text(title, output):
    output = html.escape((output or "Нет вывода.")[-2500:])
    return "<b>{}</b>\n\n<pre>{}</pre>".format(html.escape(title), output)


def log_message(line):
    if "]: " in line:
        return line.rsplit("]: ", 1)[1].strip()
    return line.strip()


def parse_player_list(raw_players):
    if not raw_players:
        return []
    return [name.strip() for name in raw_players.split(",") if name.strip()]
