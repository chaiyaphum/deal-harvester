from pathlib import Path

from pydantic_settings import BaseSettings

_default_db_path = Path(__file__).resolve().parent.parent.parent / "data" / "promotions.db"


class Settings(BaseSettings):
    model_config = {"env_prefix": "CARD_RETRIEVAL_"}

    database_url: str = f"sqlite:///{_default_db_path}"
    log_level: str = "INFO"
    log_json: bool = False

    # Rate limiting defaults (seconds between requests)
    rate_limit_ktc: float = 2.0
    rate_limit_cardx: float = 5.0
    rate_limit_kasikorn: float = 10.0
    rate_limit_krungsri: float = 3.0
    rate_limit_uob: float = 4.0
    rate_limit_amex: float = 6.0
    rate_limit_bbl: float = 5.0

    # Scheduling intervals (hours)
    schedule_ktc: int = 6
    schedule_cardx: int = 12
    schedule_kasikorn: int = 24
    schedule_krungsri: int = 12
    schedule_uob: int = 24
    schedule_amex: int = 12
    schedule_bbl: int = 24

    # Browser settings
    browser_headless: bool = True
    browser_timeout: int = 30000

    # API settings
    api_keys: str = ""


settings = Settings()
