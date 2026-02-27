from pathlib import Path

from pydantic_settings import BaseSettings

# .env lives at the project root (one level above backend/)
_env_file = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/prosim"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    DWSIM_PATH: str = "/opt/dwsim"

    model_config = {"env_file": str(_env_file), "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
