"""SQLite connections without implicit file creation during API requests."""

import sqlite3

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from backend.app.config import Settings


def current_schema_revision() -> str:
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from backend.app.config import PROJECT_ROOT
    return ScriptDirectory.from_config(Config(str(PROJECT_ROOT / "backend/alembic.ini"))).get_current_head()


def create_database_engine(
    settings: Settings, *, allow_create: bool = False, readonly: bool = False
) -> Engine:
    path = settings.database_path
    mode = "ro" if readonly else ("rwc" if allow_create else "rw")
    uri = f"{path.as_uri()}?mode={mode}"

    def connect() -> sqlite3.Connection:
        return sqlite3.connect(uri, uri=True, timeout=5, check_same_thread=False)

    engine = create_engine("sqlite+pysqlite://", creator=connect, poolclass=NullPool)

    @event.listens_for(engine, "connect")
    def configure_connection(connection: sqlite3.Connection, _record: object) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
