BTN_STATUS = "Статус"
BTN_RESOURCES = "Ресурсы"
BTN_PLAYERS = "Игроки"
BTN_TPS = "TPS"
BTN_BACKUP = "Бэкап"
BTN_VERSION = "Версия"
BTN_START = "Запустить"
BTN_STOP = "Остановить"
BTN_RESTART = "Перезапустить"
BTN_LOGS = "Логи файлом"
BTN_HELP = "Помощь"


def main_menu():
    return {
        "keyboard": [
            [BTN_STATUS, BTN_RESOURCES],
            [BTN_PLAYERS, BTN_TPS],
            [BTN_BACKUP, BTN_LOGS],
            [BTN_START, BTN_STOP],
            [BTN_RESTART, BTN_VERSION],
            [BTN_HELP],
        ],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def confirmation_keyboard(action):
    if action == "stop":
        text, data = "Да, остановить", "do_stop"
    else:
        text, data = "Да, перезапустить", "do_restart"

    return {
        "inline_keyboard": [
            [{"text": text, "callback_data": data}],
            [{"text": "Отмена", "callback_data": "cancel"}],
        ]
    }


def default_commands():
    return [
        {"command": "start", "description": "Открыть кнопки"},
        {"command": "status", "description": "Статус Minecraft"},
        {"command": "resources", "description": "Ресурсы VPS"},
        {"command": "players", "description": "Список игроков"},
        {"command": "tps", "description": "TPS/MSPT сервера"},
        {"command": "backup", "description": "Сделать бэкап мира"},
        {"command": "version", "description": "Версия задеплоенного бота"},
        {"command": "say", "description": "Сообщение в чат Minecraft"},
        {"command": "cmd", "description": "RCON-команда"},
        {"command": "whitelist_add", "description": "Добавить игрока в whitelist"},
        {"command": "whitelist_remove", "description": "Удалить игрока из whitelist"},
        {"command": "whitelist_list", "description": "Показать whitelist"},
        {"command": "kill", "description": "Убить игрока"},
        {"command": "kick", "description": "Кикнуть игрока"},
        {"command": "logs", "description": "Отправить latest.log"},
    ]
