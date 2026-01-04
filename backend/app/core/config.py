from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://app:app@127.0.0.1:5432/finance"
    jwt_secret: str = "devsecret"
    jwt_expires_min: int = 120
    cors_origins: str = "http://localhost:5173"

    class Config:
        env_prefix = ""
        case_sensitive = False
        env_file = ".env"

settings = Settings()