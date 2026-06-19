import unittest

from content_factory.config import load_settings


class ConfigTests(unittest.TestCase):
    def test_default_settings_are_safe_for_local_mvp(self):
        settings = load_settings({})
        self.assertEqual(settings.database_path, "data/content_factory.sqlite3")
        self.assertEqual(settings.upload_dir, "uploads")
        self.assertEqual(settings.ai_provider, "mock")
        self.assertEqual(settings.host, "127.0.0.1")
        self.assertEqual(settings.port, 8000)

    def test_environment_overrides_are_supported(self):
        settings = load_settings(
            {
                "DATABASE_PATH": "tmp/test.sqlite3",
                "UPLOAD_DIR": "tmp/uploads",
                "CONTENT_FACTORY_PROVIDER": "openai",
                "HOST": "0.0.0.0",
                "PORT": "8123",
            }
        )
        self.assertEqual(settings.database_path, "tmp/test.sqlite3")
        self.assertEqual(settings.upload_dir, "tmp/uploads")
        self.assertEqual(settings.ai_provider, "openai")
        self.assertEqual(settings.host, "0.0.0.0")
        self.assertEqual(settings.port, 8123)
