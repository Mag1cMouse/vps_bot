import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vps_bot.services.minecraft import (
    MinecraftService,
    log_message,
    parse_player_list,
    strip_minecraft_formatting,
)


class MinecraftParsingTests(unittest.TestCase):
    def test_log_message_handles_arclight_prefix(self):
        line = "[14May2026 12:00:00.000] [Server thread/INFO] [minecraft/DedicatedServer]: Alex joined the game"

        self.assertEqual(log_message(line), "Alex joined the game")

    def test_rebuild_players_after_old_empty_list(self):
        lines = [
            "[12:00:00 INFO]: There are 0 of a max of 20 players online:",
            "[14May2026 12:00:05.000] [Server thread/INFO] [minecraft/DedicatedServer]: Steve joined the game",
            "[14May2026 12:01:00.000] [Server thread/INFO] [minecraft/DedicatedServer]: Alex[/127.0.0.1:12345] logged in with entity id 1 at ([world]0, 0, 0)",
        ]

        self.assertEqual(MinecraftService._rebuild_players_from_lines(None, lines), ["Steve", "Alex"])

    def test_leave_event_deduplicates_lost_connection(self):
        text = (
            "[14May2026 08:16:00.000] [Server thread/INFO] [minecraft/DedicatedServer]: Opssss lost connection: Disconnected\n"
            "[14May2026 08:16:00.100] [Server thread/INFO] [minecraft/DedicatedServer]: Opssss left the game\n"
        )

        self.assertEqual(MinecraftService._parse_log_events(None, text), [{"type": "leave", "player": "Opssss"}])

    def test_strip_minecraft_formatting(self):
        self.assertEqual(strip_minecraft_formatting("§6Убит§c §4Opssss§r§6."), "Убит Opssss.")

    def test_parse_player_list(self):
        self.assertEqual(parse_player_list("Steve, Alex"), ["Steve", "Alex"])
        self.assertEqual(parse_player_list(""), [])


if __name__ == "__main__":
    unittest.main()
