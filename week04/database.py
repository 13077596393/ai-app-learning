from sqlmodel import (
    SQLModel,
    create_engine,
    Session,
)  # 导入 SQLModel 元数据对象和数据库引擎创建函数
from settings import settings  # 导入全局配置对象，统一从 .env 读取数据库连接地址

engine = create_engine(
    settings.database_url, echo=True
)  # 创建数据库引擎并开启 SQL 日志输出


def create_db_and_tables():  # 定义创建数据库表的初始化函数
    SQLModel.metadata.create_all(engine)  # 根据已注册的 SQLModel 模型创建所有表


def get_session():  # 定义 FastAPI 依赖函数，用来给接口提供数据库连接，提供数据库会话，让接口能查库、写库
    with Session(engine) as session:  # 使用 engine 创建一个数据库会话，并在使用结束后自动关闭
        yield session  # 把数据库会话交给接口使用，接口执行完后会自动回到这里释放资源
