import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vps_bot.config import load_settings


class ConfigTests(unittest.TestCase):
    def test_dev_profile_uses_mock(self):
        settings = load_settings(profile="dev", env_file=".env.dev.example", project_root=ROOT)

        self.assertEqual(settings.profile, "dev")
        self.assertEqual(settings.control_mode, "mock")
        self.assertTrue(settings.backup_paths)

    def test_master_profile_uses_prod_systemd(self):
        settings = load_settings(profile="master", env_file=".env.prod.example", project_root=ROOT)

        self.assertEqual(settings.profile, "prod")
        self.assertEqual(settings.control_mode, "systemd")
        self.assertTrue(settings.backup_dir)


if __name__ == "__main__":
    unittest.main()
