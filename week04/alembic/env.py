import sys  # 导入 sys 模块，用来修改 Python 模块搜索路径
from pathlib import Path  # 导入 Path，用来处理跨平台路径

from logging.config import (
    fileConfig,
)  # 导入日志配置工具，用来读取 alembic.ini 里的日志配置

from sqlalchemy import engine_from_config  # 导入 Alembic 用来创建数据库引擎的工具
from sqlalchemy import pool  # 导入连接池工具
from sqlmodel import SQLModel  # 导入 SQLModel，用来获取所有表模型的 metadata

from alembic import context  # 导入 Alembic 上下文对象，用来读取配置和执行迁移

BASE_DIR = Path(__file__).resolve().parents[1]  # 获取 week04 项目根目录
sys.path.append(str(BASE_DIR))  # 把 week04 项目根目录加入 Python 搜索路径


from settings import settings  # 导入项目配置对象，用来读取 .env 里的 DATABASE_URL
import models  # 导入 models.py，让所有 SQLModel 表模型注册到 SQLModel.metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
config.set_main_option(
    "sqlalchemy.url",  # 设置 Alembic 使用的数据库连接配置项
    settings.database_url,  # 使用 settings.py 从 .env 读取到的 DATABASE_URL
)  # 把项目真实数据库地址写入 Alembic 配置对象
# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = (
    SQLModel.metadata
)  # 告诉 Alembic：以 SQLModel.metadata 里的表结构作为对比目标

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




