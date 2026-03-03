import json
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings

# .env lives at the project root (one level above backend/)
_env_file = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/prosim"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-5-mini"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    DWSIM_PATH: str = "/opt/dwsim"
    PORT: int = 8000

    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            # Accept comma-separated or single origin
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    model_config = {"env_file": str(_env_file), "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
