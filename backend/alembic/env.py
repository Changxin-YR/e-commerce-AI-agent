"""Migration-only code is the sole D0 entrypoint allowed to create the database."""

from alembic import context

from backend.app.config import Settings
from backend.app.database import create_database_engine
from backend.app.models import Base

config = context.config
settings = config.attributes.get("settings") or Settings()
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url="sqlite+pysqlite://",
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_database_engine(settings, allow_create=True)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
