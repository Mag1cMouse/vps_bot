# VPS Bot

Telegram-бот для управления Minecraft-сервером на VPS через systemd.

## Запуск

Бот по-прежнему можно запускать старой командой на сервере:

```bash
python3 bot.py
```

Теперь есть два профиля:

```text
dev  - локальный тестовый запуск с тестовым Telegram-токеном и mock-управлением Minecraft
prod - боевой запуск на VPS с настоящим токеном и systemd
```

Профиль можно указать явно:

```bash
python3 bot.py --profile prod
python3 bot.py --profile dev
```

Если проект является git-репозиторием, бот сам выберет `dev` для ветки `dev`/`develop` и `prod` для `master`/`main`.

## Локальный dev

Создай тестового Telegram-бота и файл `.env.dev`:

```bash
cp .env.dev.example .env.dev
```

В `.env.dev` укажи токен тестового бота и свой Telegram ID:

```env
BOT_PROFILE=dev
BOT_TOKEN=123456:test-telegram-token
ADMIN_IDS=123456789
MC_CONTROL_MODE=mock
```

Запуск с компьютера:

```bash
python3 bot.py --profile dev
```

В Windows можно использовать:

```powershell
.\scripts\run_dev.ps1
```

В dev-режиме кнопки запуска, остановки и перезапуска ничего не делают с systemd. Бот только имитирует действия, чтобы можно было спокойно проверить Telegram-интерфейс.

## Production на VPS

На сервере создай `.env.prod`:

```bash
cp .env.prod.example .env.prod
```

В `.env.prod` укажи боевой токен и настройки логов. Если хочешь отправлять команды напрямую в сервер, добавь RCON-параметры.

```bash
BOT_PROFILE=prod
BOT_TOKEN=123456:production-telegram-token
ADMIN_IDS=123456789
MC_CONTROL_MODE=systemd
MC_SERVICE=minecraft.service
MC_LATEST_LOG=/root/server/logs/latest.log
MC_RCON_HOST=127.0.0.1
MC_RCON_PORT=25575
MC_RCON_PASSWORD=ваш_пароль
```

Пример systemd unit лежит в `deploy/systemd/vps-bot.service.example`.

## GitHub Actions

Добавлены два workflow:

```text
.github/workflows/ci.yml             # автопроверка dev и master
.github/workflows/deploy-master.yml  # проверка и деплой master на VPS
```

Для Telegram-уведомлений о статусе CI/CD добавь в GitHub repository secrets:

```text
TELEGRAM_STATUS_BOT_TOKEN  # токен бота, который будет писать статусы сборки
TELEGRAM_STATUS_CHAT_ID    # chat_id, куда отправлять сообщения
```

Через GitHub CLI это можно сделать так:

```bash
gh secret set TELEGRAM_STATUS_BOT_TOKEN
gh secret set TELEGRAM_STATUS_CHAT_ID
```

Для автоматического деплоя `master` на VPS добавь secrets:

```text
VPS_HOST         # IP или домен VPS
VPS_USER         # SSH-пользователь
VPS_PORT         # необязательно, по умолчанию 22
VPS_SSH_KEY      # приватный SSH-ключ для доступа к VPS
VPS_PROJECT_DIR  # путь к проекту на VPS, например /opt/vps_bot
VPS_BOT_SERVICE  # systemd-сервис бота, например vps-bot.service
```

Через GitHub CLI:

```bash
gh secret set VPS_HOST
gh secret set VPS_USER
gh secret set VPS_PORT
gh secret set VPS_PROJECT_DIR
gh secret set VPS_BOT_SERVICE
gh secret set VPS_SSH_KEY < ~/.ssh/vps_bot_deploy
```

Деплой `master` работает через SSH + `rsync`: GitHub Actions отправляет проверенную версию файлов в `VPS_PROJECT_DIR`, затем запускает проверку Python и перезапускает systemd-сервис.

Файлы `.env`, `.env.*`, `.git`, `.github`, `__pycache__` и виртуальные окружения при деплое не отправляются и не затираются. Боевой `.env.prod` должен лежать на VPS внутри `VPS_PROJECT_DIR`.

Для перезапуска сервиса GitHub Actions вызывает:

```bash
sudo systemctl restart "$VPS_BOT_SERVICE"
```

Поэтому для `VPS_USER` лучше настроить sudo без пароля только на этот конкретный сервис.

## Структура

```text
bot.py                         # совместимая точка входа
src/vps_bot/app.py             # сборка приложения и polling-loop
src/vps_bot/config.py          # профили, env-файлы и настройки
src/vps_bot/handlers.py        # обработка сообщений и callback-кнопок
src/vps_bot/telegram/          # Telegram API, команды и клавиатуры
src/vps_bot/services/          # Minecraft, systemd, latest.log, ресурсы VPS
scripts/run_dev.ps1            # локальный dev-запуск на Windows
scripts/run_prod.sh            # prod-запуск на Linux/VPS
deploy/systemd/                # пример systemd unit для бота
```

## Как расширять

Новые кнопки и команды добавляются в `src/vps_bot/telegram/keyboards.py`.

Логика реакции на сообщения находится в `src/vps_bot/handlers.py`.

Работу с внешними системами лучше держать в `src/vps_bot/services/`, чтобы обработчики оставались короткими и понятными.
