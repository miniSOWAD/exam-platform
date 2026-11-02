from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Exam Platform API"
    environment: str = "development"
    database_url: str = "sqlite:///./exam.db"
    secret_key: str = "CHANGE-ME-IN-PRODUCTION-USE-A-LONG-RANDOM-SECRET"
    access_token_minutes: int = 720
    frontend_origins: str = "http://localhost:3000"
    cookie_secure: bool = False
    max_upload_mb: int = 15
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def origins(self):
        return [x.strip() for x in self.frontend_origins.split(",") if x.strip()]

settings = Settings()
