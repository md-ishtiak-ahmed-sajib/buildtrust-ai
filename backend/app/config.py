from functools import lru_cache
from pathlib import Path
import secrets

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BUILDTRUST_", env_file=ROOT / ".env", extra="ignore"
    )
    data_dir: Path = ROOT / "data"
    demo_mode: bool = True
    minimum_reserve: str = "100000.00"
    admin_ceiling: str = "1000000.00"
    approval_minutes: int = 30
    receivable_delay_days: int = 15
    cost_pressure_percent: str = "10"
    llm_provider: str = "none"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    max_upload_bytes: int = 10 * 1024 * 1024
    max_pdf_pages: int = 50
    serpapi_key: str = ""
    dataforseo_login: str = ""
    dataforseo_password: str = ""
    paid_providers_enabled: bool = False
    paid_user_daily_calls: int = Field(default=0, ge=0)
    paid_project_daily_calls: int = Field(default=0, ge=0)
    paid_provider_daily_calls: int = Field(default=0, ge=0)
    paid_operation_ceiling: str = "0"
    paid_daily_budget: str = "0"
    llm_user_daily_calls: int = Field(default=20, ge=1)
    llm_project_daily_calls: int = Field(default=100, ge=1)
    price_timeout_seconds: int = 15
    ocr_enabled: bool = False
    ocr_tessdata_dir: Path | None = None
    ocr_languages: str = "eng+ben"
    background_jobs: bool = True
    job_poll_seconds: int = Field(default=2, ge=1, le=60)

    def prepare(self):
        self.data_dir = (
            self.data_dir if self.data_dir.is_absolute() else ROOT / self.data_dir
        ).resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "uploads").mkdir(exist_ok=True)
        from .private_storage import protect_runtime
        protect_runtime(self.data_dir)

    def signing_secret(self):
        path = self.data_dir / "signing-secret"
        if not path.exists():
            try:
                with path.open("x", encoding="utf-8") as f:
                    f.write(secrets.token_urlsafe(48))
            except FileExistsError:
                pass
        from .private_storage import protect_file
        protect_file(path)
        return path.read_text(encoding="utf-8").strip()


@lru_cache
def get_settings():
    settings = Settings()
    settings.prepare()
    return settings
