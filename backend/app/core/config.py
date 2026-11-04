from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment configuration; supports both ExamFlow and the user's prior .env names."""

    app_name: str = Field(default="ExamFlow API", validation_alias=AliasChoices("APP_NAME"))
    environment: str = Field(default="development", validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT"))
    database_url: str = Field(default="sqlite:///./exam.db", validation_alias=AliasChoices("DATABASE_URL"))
    database_echo: bool = Field(default=False, validation_alias=AliasChoices("DATABASE_ECHO"))
    # FastAPI Cloud deployments do not necessarily execute the project Dockerfile.
    # Run Alembic at ASGI startup so ORM columns and database schema stay in sync.
    auto_migrate: bool = Field(default=True, validation_alias=AliasChoices("AUTO_MIGRATE"))
    secret_key: str = Field(
        default="CHANGE-ME-IN-PRODUCTION-USE-A-LONG-RANDOM-SECRET",
        validation_alias=AliasChoices("JWT_SECRET", "SECRET_KEY"),
    )
    access_token_minutes: int = Field(default=720, validation_alias=AliasChoices("ACCESS_TOKEN_MINUTES"))
    frontend_origins: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("CORS_ORIGINS", "FRONTEND_ORIGINS"),
    )
    cookie_secure: bool = Field(default=False, validation_alias=AliasChoices("COOKIE_SECURE"))
    max_upload_bytes: int = Field(default=307200, ge=1, validation_alias=AliasChoices("MAX_UPLOAD_BYTES"))
    max_pdf_upload_mb: int = Field(default=15, ge=1, le=50, validation_alias=AliasChoices("MAX_PDF_UPLOAD_MB"))
    ocr_space_api_key: str = Field(default="", validation_alias=AliasChoices("OCR_SPACE_API_KEY"))
    ocr_space_engine: int = Field(default=3, ge=2, le=3, validation_alias=AliasChoices("OCR_SPACE_ENGINE"))
    ocr_space_timeout_seconds: int = Field(default=90, ge=15, le=180, validation_alias=AliasChoices("OCR_SPACE_TIMEOUT_SECONDS"))
    allowed_image_types: str = Field(
        default="image/jpeg,image/png,image/webp,image/jpg",
        validation_alias=AliasChoices("ALLOWED_IMAGE_TYPES"),
    )
    cloudinary_cloud_name: str = Field(default="", validation_alias=AliasChoices("CLOUDINARY_CLOUD_NAME"))
    cloudinary_api_key: str = Field(default="", validation_alias=AliasChoices("CLOUDINARY_API_KEY"))
    cloudinary_api_secret: str = Field(default="", validation_alias=AliasChoices("CLOUDINARY_API_SECRET"))
    cloudinary_folder: str = Field(default="examflow", validation_alias=AliasChoices("CLOUDINARY_FOLDER"))
    db_pool_size: int = Field(default=2, ge=1, le=10, validation_alias=AliasChoices("DB_POOL_SIZE"))
    db_max_overflow: int = Field(default=1, ge=0, le=10, validation_alias=AliasChoices("DB_MAX_OVERFLOW"))
    db_pool_recycle_seconds: int = Field(default=300, validation_alias=AliasChoices("DB_POOL_RECYCLE_SECONDS"))
    db_connect_timeout_seconds: int = Field(default=15, validation_alias=AliasChoices("DB_CONNECT_TIMEOUT_SECONDS"))
    db_command_timeout_seconds: int = Field(default=30, validation_alias=AliasChoices("DB_COMMAND_TIMEOUT_SECONDS"))
    admin_email: str = Field(default="", validation_alias=AliasChoices("ADMIN_EMAIL"))
    admin_name: str = Field(default="ExamFlow Admin", validation_alias=AliasChoices("ADMIN_NAME"))
    admin_password: str = Field(default="", validation_alias=AliasChoices("ADMIN_PASSWORD"))

    @field_validator("max_upload_bytes", mode="before")
    @classmethod
    def cap_profile_upload_size(cls, value):
        # Old projects may have a larger MAX_UPLOAD_BYTES value; ExamFlow always caps it at 300 KiB.
        return min(max(1, int(value)), 307200)

    @field_validator("db_pool_size", mode="before")
    @classmethod
    def cap_neon_pool_size(cls, value):
        return min(max(1, int(value)), 2)

    @field_validator("db_max_overflow", mode="before")
    @classmethod
    def cap_neon_pool_overflow(cls, value):
        return min(max(0, int(value)), 1)

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    @property
    def origins(self) -> list[str]:
        return [item.strip() for item in self.frontend_origins.split(",") if item.strip()]

    @property
    def image_mime_types(self) -> set[str]:
        return {item.strip().lower() for item in self.allowed_image_types.split(",") if item.strip()}

    @property
    def sqlalchemy_database_url(self) -> str:
        """Normalize Neon/Render PostgreSQL URLs for the installed psycopg 3 driver."""
        url = self.database_url.strip()
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url[len("postgresql://"):]
        return url


settings = Settings()
