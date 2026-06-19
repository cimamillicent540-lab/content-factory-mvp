from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    database_path: str
    upload_dir: str
    ai_provider: str
    host: str
    port: int


def load_settings(env=None):
    source = os.environ if env is None else env
    return Settings(
        database_path=source.get("DATABASE_PATH", "data/content_factory.sqlite3"),
        upload_dir=source.get("UPLOAD_DIR", "uploads"),
        ai_provider=source.get("AI_PROVIDER", "mock"),
        host=source.get("HOST", "127.0.0.1"),
        port=int(source.get("PORT", "8000")),
    )
