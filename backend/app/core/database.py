from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.core.config import settings


database_url = settings.sqlalchemy_database_url
if database_url.startswith("sqlite"):
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        echo=settings.database_echo,
        pool_pre_ping=True,
    )
else:
    # Small pools are intentional: Neon free plans have finite connection budgets.
    engine = create_engine(
        database_url,
        echo=settings.database_echo,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle_seconds,
        pool_timeout=20,
        connect_args={
            "connect_timeout": settings.db_connect_timeout_seconds,
            # Avoid server-side prepared statements with transaction-pooled Neon endpoints.
            "prepare_threshold": None,
        },
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
