BTN_STATUS = "Статус"
BTN_RESOURCES = "Ресурсы"
BTN_PLAYERS = "Игроки"
BTN_START = "Запустить"
BTN_STOP = "Остановить"
BTN_RESTART = "Перезапустить"
BTN_LOGS = "Логи файлом"
BTN_HELP = "Помощь"


def main_menu():
    return {
        "keyboard": [
            [BTN_STATUS, BTN_RESOURCES],
            [BTN_PLAYERS, BTN_LOGS],
            [BTN_START, BTN_STOP],
            [BTN_RESTART, BTN_HELP],
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
        {"command": "kill", "description": "Убить игрока"},
        {"command": "kick", "description": "Кикнуть игрока"},
        {"command": "logs", "description": "Отправить latest.log"},
    ]
