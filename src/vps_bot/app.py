import argparse
import time
from pathlib import Path

from vps_bot.config import load_settings
from vps_bot.handlers import BotHandlers
from vps_bot.services.logs import MinecraftLog
from vps_bot.services.minecraft import MinecraftService
from vps_bot.services.systemd import MockSystemdService, SystemdService
from vps_bot.telegram.client import TelegramClient
from vps_bot.telegram.keyboards import default_commands


class BotApp:
    def __init__(self, settings):
        self.settings = settings
        self.telegram = TelegramClient(settings.token)
        systemd = self._build_systemd_service()
        self.minecraft = MinecraftService(
            settings=settings,
            telegram=self.telegram,
            systemd=systemd,
            log=MinecraftLog(settings.log_file),
        )
        self.handlers = BotHandlers(settings, self.telegram, self.minecraft)

    def _build_systemd_service(self):
        if self.settings.control_mode == "mock":
            return MockSystemdService(self.settings.service)
        return SystemdService(self.settings.service)

    def configure_telegram(self):
        self.telegram.delete_webhook(drop_pending_updates=False)
        self.telegram.set_my_commands(default_commands())

    def run_forever(self):
        self.configure_telegram()
        self.minecraft.initialize_log_offset()
        print("Bot started", flush=True)

        offset = 0
        while True:
            try:
                updates = self.telegram.get_updates(
                    offset=offset,
                    timeout=30,
                    allowed_updates=["message", "callback_query"],
                )

                for update in updates:
                    offset = update["update_id"] + 1
                    try:
                        self.handlers.handle_update(update)
                    except Exception as exc:
                        print("Update error:", repr(exc), flush=True)

                self.minecraft.process_log_events()
            except Exception as exc:
                print("Loop error:", repr(exc), flush=True)
                time.sleep(5)


def build_app(settings=None, profile=None, env_file=None, project_root=None):
    return BotApp(settings or load_settings(profile=profile, env_file=env_file, project_root=project_root))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Telegram bot for managing a Minecraft server")
    parser.add_argument(
        "--profile",
        help="Config profile: dev uses .env.dev, prod/master uses .env.prod",
    )
    parser.add_argument(
        "--env-file",
        help="Explicit env file path. Process environment variables still have priority.",
    )
    return parser.parse_args(argv)


def main(argv=None, project_root=None):
    args = parse_args(argv)
    root = Path(project_root).resolve() if project_root else Path.cwd().resolve()
    build_app(profile=args.profile, env_file=args.env_file, project_root=root).run_forever()
