from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    secret_key: str = "change-me-to-a-long-random-string"
    admin_username: str = "admin"
    admin_password: str = "changeme"
    access_token_expire_minutes: int = 720

    database_url: str = "postgresql+psycopg://catshort:catshort@postgres:5432/catshort"

    data_dir: Path = Path("/data")
    drive_inbox_dir: Path = Path("/data/inbox")

    drive_mode: str = "mock"  # mock | live
    google_client_secrets_file: Path = Path("/data/secrets/google_client_secrets.json")
    google_token_file: Path = Path("/data/secrets/google_token.json")
    drive_folder_id: str = ""
    drive_sync_interval_seconds: int = 120

    youtube_mode: str = "mock"  # mock | live
    youtube_client_secrets_file: Path = Path("/data/secrets/youtube_client_secrets.json")
    youtube_token_file: Path = Path("/data/secrets/youtube_token.json")
    youtube_default_title_prefix: str = "Cat Short"
    youtube_category_id: str = "15"

    render_max_seconds: float = 59.0
    render_width: int = 1080
    render_height: int = 1920
    render_fps: int = 30
    music_bed_path: Path = Path("/app/assets/music/cozy_afternoon.wav")
    caption_font_path: Path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")

    worker_poll_seconds: float = 2.0
    scheduler_tick_seconds: float = 30.0

    @property
    def assets_dir(self) -> Path:
        return self.data_dir / "assets"

    @property
    def renders_dir(self) -> Path:
        return self.data_dir / "renders"

    @property
    def work_dir(self) -> Path:
        return self.data_dir / "work"

    @property
    def youtube_mock_dir(self) -> Path:
        return self.data_dir / "youtube_mock"

    @property
    def secrets_dir(self) -> Path:
        return self.data_dir / "secrets"

    def ensure_dirs(self) -> None:
        for path in (
            self.data_dir,
            self.drive_inbox_dir,
            self.assets_dir,
            self.renders_dir,
            self.work_dir,
            self.youtube_mock_dir,
            self.secrets_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
