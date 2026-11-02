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
