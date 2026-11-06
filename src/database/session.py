from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import EngineSettings


def create_db_engine_and_session_factory(
    settings: EngineSettings,
) -> tuple[Engine, sessionmaker[Session]]:
    """
    Create a SQLAlchemy 2.0 Engine and Session factory without calling create_all (`C-DB-01`).
    """
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    return engine, session_factory
