import os
from alembic import context
from sqlalchemy import engine_from_config, pool
from commlab.assembly import Services
from commlab.db import Base

config = context.config
if config.attributes.get("use_environment_url", True) and os.getenv("DATABASE_URL"):
    config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"].replace("%", "%%"))
target_metadata = Base.metadata


def run():
    if context.is_offline_mode():
        context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                          literal_binds=True, dialect_opts={"paramstyle": "named"})
        with context.begin_transaction():
            context.run_migrations()
    else:
        connectable = engine_from_config(config.get_section(config.config_ini_section), prefix="sqlalchemy.",
                                         poolclass=pool.NullPool)
        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()


run()
