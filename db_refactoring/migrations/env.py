"""
Alembic Environment Configuration

주의: 이 설정은 테스트 DB(포트 15432)에서만 작동합니다.
운영 DB(포트 5432)에 대한 마이그레이션은 절대 실행하지 마세요.
"""
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# 환경변수 로드 (선택적)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# 환경변수에서 DB URL 로드 (우선순위: 환경변수 > alembic.ini)
db_url = os.getenv("POSTGRES_TEST_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

# 안전장치: 운영 DB(5432 포트) 접근 차단
current_url = config.get_main_option("sqlalchemy.url")
if current_url and ":5432/" in current_url:
    raise RuntimeError(
        "운영 DB(포트 5432) 접근이 감지되었습니다! "
        "db_refactoring의 Alembic은 테스트 DB(포트 15432)에서만 실행해야 합니다."
    )

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
