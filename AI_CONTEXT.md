# AI Project Context

Этот файл предназначен для передачи контекста другим AI-ассистентам без повторного объяснения проекта.

## Назначение проекта

Проект `vps_bot` - Telegram-бот для управления Minecraft-сервером на VPS.

Бот работает через Telegram long polling, поэтому не открывает входящий HTTP-порт. Управление Minecraft выполняется через `systemd`, чтение `latest.log`, проверку TCP-порта Minecraft и опционально через RCON для прямых игровых команд.

Основные сценарии:

- посмотреть статус Minecraft-сервера;
- посмотреть ресурсы системы;
- запустить, остановить или перезапустить Minecraft systemd-сервис;
- отправить `latest.log` файлом;
- посмотреть игроков онлайн;
- получать уведомления о входе/выходе игроков по `latest.log`;
- отправлять `/kill` и `/kick` через RCON, если RCON настроен.

## Текущий технологический стек

- Python 3, только стандартная библиотека.
- Telegram Bot API через `urllib`.
- Linux/systemd на VPS.
- GitHub Actions для CI и деплоя `master`.
- Локальный `dev`-режим использует mock-управление Minecraft без вызова `systemctl`.

## Структура репозитория

```text
bot.py
src/vps_bot/
  __init__.py
  app.py
  config.py
  handlers.py
  telegram/
    __init__.py
    client.py
    keyboards.py
  services/
    __init__.py
    logs.py
    minecraft.py
    resources.py
    systemd.py
.github/workflows/
  ci.yml
  deploy-master.yml
deploy/systemd/
  vps-bot.service.example
scripts/
  run_dev.ps1
  run_prod.sh
.env.example
.env.dev.example
.env.prod.example
README.md
pyproject.toml
```

В рабочей папке могут появляться `__pycache__` и `.pyc` после проверок Python. Они не являются частью логики проекта.

## Логика файлов

### `bot.py`

Совместимая точка входа. Добавляет `src/` в `sys.path` и запускает `vps_bot.app.main(project_root=ROOT_DIR)`.

Старый способ запуска сохранён:

```bash
python3 bot.py
```

### `src/vps_bot/app.py`

Собирает приложение:

- загружает настройки через `load_settings`;
- создаёт `TelegramClient`;
- выбирает `SystemdService` или `MockSystemdService` по `MC_CONTROL_MODE`;
- создаёт `MinecraftService`;
- создаёт `BotHandlers`;
- на старте вызывает `deleteWebhook`, `setMyCommands`, `initialize_log_offset`;
- запускает бесконечный polling-loop через `getUpdates`;
- после обработки пачки updates вызывает `minecraft.process_log_events()`.

Поддерживает CLI-флаги:

```bash
python3 bot.py --profile dev
python3 bot.py --profile prod
python3 bot.py --env-file .env.prod
```

### `src/vps_bot/config.py`

Отвечает за конфигурацию:

- читает `.env`, `.env.dev`, `.env.prod` или явный `--env-file`;
- не загрязняет `os.environ` значениями из файлов;
- нормализует профили: `master/main/production -> prod`, `dev/develop/local -> dev`;
- если проект является git-репозиторием, может определить профиль по ветке;
- возвращает dataclass `Settings`.

Основные env-переменные:

```text
BOT_PROFILE
BOT_TOKEN
ADMIN_IDS
MC_CONTROL_MODE
MC_SERVICE
MC_LATEST_LOG
MC_PORT
MC_RCON_HOST
MC_RCON_PORT
MC_RCON_PASSWORD
MC_START_TIMEOUT
MC_STOP_TIMEOUT
MAX_LOG_SEND_MB
```

`MC_CONTROL_MODE=mock` используется для локального dev.  
`MC_CONTROL_MODE=systemd` используется на VPS.

### `src/vps_bot/handlers.py`

Маршрутизирует входящие Telegram messages и callback_query.

Проверяет администратора через `ADMIN_IDS`. Если пользователь не админ, отвечает `Нет доступа.`

Поддерживаемые команды и кнопки:

```text
/start, /help
/status
/resources
/players
/mc_start
/mc_stop
/mc_restart
/logs
/kill <ник>
/kick <ник> [причина]
```

Остановка и перезапуск идут через inline confirmation keyboard.

### `src/vps_bot/telegram/client.py`

Низкоуровневый клиент Telegram Bot API:

- `request`;
- `request_multipart`;
- `delete_webhook`;
- `set_my_commands`;
- `get_updates`;
- `send_message`;
- `edit_message`;
- `answer_callback_query`;
- `send_document`.

Внешние зависимости не используются.

### `src/vps_bot/telegram/keyboards.py`

Содержит текст кнопок, основную reply keyboard, inline confirmation keyboard и список slash-команд для `setMyCommands`.

Если добавляется новая кнопка, сначала обновлять этот файл, затем routing в `handlers.py`.

### `src/vps_bot/services/systemd.py`

Содержит:

- `run_command` - безопасная обёртка над `subprocess.run`;
- `SystemdService` - реальное управление через `/usr/bin/sudo -n /usr/bin/systemctl`;
- `MockSystemdService` - локальный mock для dev.

`SystemdService` управляет сервисом из `MC_SERVICE`. Это сервис Minecraft, например `minecraft.service`, а не сервис Telegram-бота.

### `src/vps_bot/services/logs.py`

Работа с `latest.log`:

- проверить существование и доступность;
- получить размер;
- прочитать хвост файла;
- прочитать новые байты с offset;
- найти строку готовности ядра Minecraft: `Done (...) For help, type "help"`.

### `src/vps_bot/services/resources.py`

Формирует текст с ресурсами системы:

- CPU count;
- load average, если доступен;
- RAM на Linux через `/proc/meminfo`;
- RAM на Windows через `ctypes`;
- disk usage.

Сделан кроссплатформенным, чтобы локальный dev на Windows не падал.

### `src/vps_bot/services/minecraft.py`

Основная бизнес-логика Minecraft:

- статус systemd-сервиса;
- проверка TCP-порта `MC_PORT`;
- ожидание готовности ядра по `latest.log`;
- запуск, остановка, перезапуск;
- отправка `latest.log`;
- получение списка игроков;
- реконструкция состояния игроков по join/leave/kick/lost connection строкам в `latest.log`;
- уведомления админам о входе/выходе игроков;
- отправка `/kill` и `/kick` через RCON.

RCON используется только если задан `MC_RCON_PASSWORD`.

Для работы RCON на Minecraft-сервере должны быть включены настройки в `server.properties`:

```properties
enable-rcon=true
rcon.port=25575
rcon.password=...
```

### `.github/workflows/ci.yml`

CI для `dev` и `master`:

- запускается на `push` и `pull_request`;
- ставит Python 3.12;
- выполняет `python -m compileall bot.py src`;
- smoke-test для dev profile;
- smoke-test для master/prod profile;
- на push отправляет Telegram-уведомление, если заданы secrets `TELEGRAM_STATUS_BOT_TOKEN` и `TELEGRAM_STATUS_CHAT_ID`.

### `.github/workflows/deploy-master.yml`

Деплой `master` на VPS:

- запускается на push в `master` и вручную через `workflow_dispatch`;
- проверяет Python-код;
- проверяет prod profile;
- проверяет наличие deploy secrets;
- настраивает SSH-ключ;
- ставит `rsync`;
- создаёт `VPS_PROJECT_DIR` на сервере;
- отправляет код через `rsync`;
- исключает `.git`, `.github`, `.env`, `.env.*`, `__pycache__`, `.pyc`, `.venv`, `venv`;
- на VPS выполняет `python3 -m compileall bot.py src`;
- выставляет владельца проекта `mcbot:mcbot`;
- перезапускает systemd-сервис Telegram-бота из `VPS_BOT_SERVICE`;
- отправляет Telegram-уведомление о результате деплоя.

Важно: `.env.prod` не деплоится и не затирается. В текущем VPS unit используется не `.env.prod`, а `/etc/minecraft-bot.env`.

### `deploy/systemd/vps-bot.service.example`

Пример systemd unit для запуска Telegram-бота.

Фактический сервис на VPS сейчас найден как:

```text
minecraft-bot.service
```

Фактический unit:

```ini
[Unit]
Description=Telegram bot for Minecraft server
After=network-online.target
Wants=network-online.target

[Service]
User=mcbot
Group=mcbot
WorkingDirectory=/bots/bot_core_control
EnvironmentFile=/etc/minecraft-bot.env
ExecStart=/usr/bin/python3 -u /bots/bot_core_control/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Его имя должно быть записано в GitHub secret:

```text
Name:   VPS_BOT_SERVICE
Secret: minecraft-bot.service
```

Путь проекта должен быть записан в GitHub secret:

```text
Name:   VPS_PROJECT_DIR
Secret: /bots/bot_core_control
```

### `scripts/run_dev.ps1`

Windows-скрипт для локального dev:

```powershell
.\scripts\run_dev.ps1
```

Устанавливает `BOT_PROFILE=dev` и запускает `bot.py --profile dev`.

### `scripts/run_prod.sh`

Linux-скрипт для prod:

```bash
./scripts/run_prod.sh
```

Устанавливает `BOT_PROFILE=prod` и запускает `python3 bot.py --profile prod`.

## Профили окружения

### Dev

Файл:

```text
.env.dev
```

Пример:

```text
.env.dev.example
```

Dev должен использовать:

```text
BOT_PROFILE=dev
MC_CONTROL_MODE=mock
```

В dev-режиме кнопки start/stop/restart ничего не делают с настоящим systemd.

### Prod

Стандартный файл для prod-профиля:

```text
<VPS_PROJECT_DIR>/.env.prod
```

Но на текущем VPS systemd unit уже подключает:

```text
/etc/minecraft-bot.env
```

Это допустимо: `config.py` читает переменные из process environment, поэтому значения из `EnvironmentFile=/etc/minecraft-bot.env` имеют приоритет и работают без `.env.prod`.

Prod должен использовать:

```text
BOT_PROFILE=prod
MC_CONTROL_MODE=systemd
```

`BOT_TOKEN`, `ADMIN_IDS`, `MC_RCON_PASSWORD` и другие реальные секреты нельзя хранить в example-файлах и нельзя коммитить.

## GitHub Secrets

Repository secrets для уведомлений:

```text
TELEGRAM_STATUS_BOT_TOKEN
TELEGRAM_STATUS_CHAT_ID
```

Repository secrets для деплоя:

```text
VPS_HOST
VPS_USER
VPS_PORT
VPS_SSH_KEY
VPS_PROJECT_DIR
VPS_BOT_SERVICE
```

Текущие известные значения по VPS:

```text
VPS_USER=root
VPS_PROJECT_DIR=/bots/bot_core_control
VPS_BOT_SERVICE=minecraft-bot.service
```

`VPS_PROJECT_DIR` должен быть фактическим путём к папке бота на VPS. Unit `minecraft-bot.service` указывает:

```ini
WorkingDirectory=/bots/bot_core_control
ExecStart=/usr/bin/python3 -u /bots/bot_core_control/bot.py
```

Ранее проверка показала, что `/bots/bot_core_control` не существует. Это нормально до первого деплоя: GitHub Actions выполняет:

```bash
mkdir -p "$VPS_PROJECT_DIR"
```

После деплоя директория должна существовать и принадлежать `mcbot:mcbot`.

## VPS-структура и проверки

На VPS в `/root` ранее были видны директории:

```text
bots
docker.gpg
nyst-backend
os_postinstall.log
peresdacha
server
user
```

Проверить systemd unit Telegram-бота:

```bash
systemctl cat minecraft-bot.service
```

В выводе искать:

```ini
WorkingDirectory=...
ExecStart=...
```

`VPS_PROJECT_DIR` должен указывать на директорию, куда GitHub Actions будет отправлять файлы. Для текущего unit это строго `/bots/bot_core_control`.

Проверить состояние Telegram-бота:

```bash
systemctl status minecraft-bot.service --no-pager -l
```

Проверить Minecraft-сервис:

```bash
systemctl status minecraft.service --no-pager -l
```

Проверить лог Minecraft:

```bash
ls -la /root/server/logs/latest.log
```

Если фактический путь отличается, обновить `MC_LATEST_LOG` в `.env.prod`.

## SSH для GitHub Actions

Создан SSH-ключ для деплоя:

```text
/root/.ssh/vps_bot_deploy
/root/.ssh/vps_bot_deploy.pub
```

В GitHub secret `VPS_SSH_KEY` должен быть вставлен приватный ключ целиком:

```text
-----BEGIN OPENSSH PRIVATE KEY-----
...
-----END OPENSSH PRIVATE KEY-----
```

Публичный ключ должен быть добавлен на VPS в:

```text
/root/.ssh/authorized_keys
```

Так как ключ создан под `root`, GitHub secret `VPS_USER` должен быть `root`, если не создан отдельный deploy-пользователь.

## Команды проверки локально

Проверить синтаксис:

```bash
python -m compileall bot.py src
```

Проверить dev profile:

```bash
python bot.py --profile dev --help
python bot.py --profile dev
```

Проверить prod profile без запуска Telegram polling:

```bash
python -B -c "import sys; from pathlib import Path; sys.path.insert(0, 'src'); from vps_bot.config import load_settings; s=load_settings(profile='prod', env_file='.env.prod.example', project_root=Path.cwd()); print(s.profile, s.control_mode)"
```

## Правила расширения

Для новой кнопки:

1. Добавить текст кнопки в `src/vps_bot/telegram/keyboards.py`.
2. Добавить кнопку в `main_menu()`.
3. Добавить slash-команду в `default_commands()`, если нужна.
4. Добавить обработку в `src/vps_bot/handlers.py`.
5. Логику вынести в `src/vps_bot/services/`, если это не простая маршрутизация.

Для новой интеграции:

1. Создать отдельный service module в `src/vps_bot/services/`.
2. Настройки добавить в `Settings` в `config.py`.
3. Подключить service в `app.py` или внутри `MinecraftService`, если интеграция относится к Minecraft.
4. Обновить `.env.example`, `.env.dev.example`, `.env.prod.example`.
5. Обновить этот файл.

## Важные ограничения

- Не коммитить реальные `.env`, `.env.dev`, `.env.prod`.
- Не хранить реальные токены в `*.example`.
- Бот использует long polling; webhook не используется.
- `MC_PORT=25565` - порт Minecraft, бот его не слушает.
- `MC_SERVICE` - systemd-сервис Minecraft.
- `VPS_BOT_SERVICE` - systemd-сервис Telegram-бота.
- `VPS_PROJECT_DIR` - директория проекта бота на VPS, куда деплоит GitHub Actions; сейчас `/bots/bot_core_control`.
- Для `sudo systemctl restart minecraft-bot.service` у deploy-пользователя должен быть доступ без интерактивного пароля.
