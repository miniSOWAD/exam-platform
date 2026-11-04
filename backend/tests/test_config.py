from app.core.config import Settings


def test_prior_env_names_and_neon_url_are_supported():
    settings = Settings(
        _env_file=None,
        APP_ENV="production",
        DATABASE_URL="postgresql://owner:secret@ep-example-pooler.aws.neon.tech/neondb?sslmode=require",
        JWT_SECRET="x" * 64,
        CORS_ORIGINS="https://examflow.example",
        MAX_UPLOAD_BYTES="5242880",
        DB_POOL_SIZE="5",
        DB_MAX_OVERFLOW="10",
    )
    assert settings.environment == "production"
    assert settings.sqlalchemy_database_url.startswith("postgresql+psycopg://")
    assert settings.origins == ["https://examflow.example"]
    assert settings.max_upload_bytes == 307200
    assert settings.db_pool_size == 2
    assert settings.db_max_overflow == 1


def test_pdf_limit_is_separate_from_profile_photo_limit_and_ocr_settings():
    settings = Settings(
        _env_file=None,
        JWT_SECRET="x" * 64,
        MAX_UPLOAD_BYTES="5242880",
        MAX_PDF_UPLOAD_MB="20",
        OCR_SPACE_API_KEY="ocr-test-key",
        OCR_SPACE_ENGINE="3",
    )
    assert settings.max_upload_bytes == 307200
    assert settings.max_pdf_upload_mb == 20
    assert settings.ocr_space_api_key == "ocr-test-key"
    assert settings.ocr_space_engine == 3


def test_database_auto_migration_defaults_on_and_can_be_disabled():
    enabled = Settings(_env_file=None, JWT_SECRET="x" * 64)
    disabled = Settings(_env_file=None, JWT_SECRET="x" * 64, AUTO_MIGRATE="false")
    assert enabled.auto_migrate is True
    assert disabled.auto_migrate is False
