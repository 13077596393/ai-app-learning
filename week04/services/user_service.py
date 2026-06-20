from sqlmodel import Session, select  # 导入数据库会话和查询构造函数

from database import engine  # 导入全局数据库引擎
from models import ChatMessage, ChatSession, User  # 导入业务数据表模型


def create_user(username: str, hashed_password: str) -> User:  # 定义创建用户的服务函数
    user = User(
        username=username, hashed_password=hashed_password
    )  # 根据用户名和哈希密码构造用户对象

    with Session(engine) as session:  # 创建数据库会话并在代码块结束后自动关闭
        session.add(user)  # 将新用户对象加入当前会话
        session.commit()  # 提交事务，把新用户写入数据库
        session.refresh(user)  # 刷新对象以获取数据库生成的字段

    return user  # 返回创建完成的用户对象


def find_user_by_id(user_id: int) -> User | None:  # 定义按用户 ID 查询用户的服务函数
    with Session(engine) as session:  # 创建数据库会话
        user = session.get(User, user_id)  # 根据主键 ID 获取用户记录

    return user  # 返回查询到的用户，未找到时返回 None


def find_user_by_username(
    username: str,
) -> User | None:  # 定义按用户名查询用户的服务函数
    with Session(engine) as session:  # 创建数据库会话
        statement = select(User).where(
            User.username == username
        )  # 构造按用户名过滤的查询语句
        user = session.exec(statement).first()  # 执行查询并取第一条匹配记录

    return user  # 返回查询到的用户，未找到时返回 None


def create_chat_session(  # 定义创建聊天会话的服务函数
    user_id: int,  # 创建会话的用户 ID
    project_id: int,  # 会话所属项目空间 ID
    title: str | None = None,  # 会话标题，可以为空
) -> ChatSession:  # 返回创建完成的聊天会话对象
    chat_session = ChatSession(  # 构造聊天会话对象
        user_id=user_id,  # 设置创建者用户 ID
        project_id=project_id,  # 设置会话所属项目空间 ID
        title=title or "新会话",  # 如果前端没传标题，就使用默认标题“新会话”
    )  # 结束聊天会话对象构造

    with Session(engine) as session:  # 创建数据库会话
        session.add(chat_session)  # 将新会话对象加入当前会话
        session.commit()  # 提交事务，把新会话写入数据库
        session.refresh(
            chat_session
        )  # 刷新对象以获取数据库生成的 id、created_at 等字段

    return chat_session  # 返回创建完成的聊天会话对象


def find_chat_session_by_id(
    session_id: int,
) -> ChatSession | None:  # 定义按会话 ID 查询聊天会话的服务函数
    with Session(engine) as session:  # 创建数据库会话
        chat_session = session.get(
            ChatSession, session_id
        )  # 根据主键 ID 获取聊天会话记录

    return chat_session  # 返回查询到的聊天会话，未找到时返回 None


def find_chat_sessions_by_user_id(
    user_id: int,
) -> list[ChatSession]:  # 定义按用户 ID 查询聊天会话列表的服务函数
    with Session(engine) as session:  # 创建数据库会话
        statement = select(ChatSession).where(
            ChatSession.user_id == user_id
        )  # 构造查询当前用户所有会话的语句
        chat_sessions = session.exec(statement).all()  # 执行查询并获取全部会话

    return list(chat_sessions)  # 将查询结果转成列表后返回


def find_chat_sessions_by_project_id(  # 定义按项目空间 ID 查询聊天会话列表的服务函数
    project_id: int,  # 项目空间 ID
) -> list[ChatSession]:  # 返回聊天会话列表
    with Session(engine) as session:  # 创建数据库会话
        statement = (  # 开始构造查询语句
            select(ChatSession)  # 查询 ChatSession 表
            .where(
                ChatSession.project_id == project_id
            )  # 只查询当前项目空间下的聊天会话
            .order_by(
                ChatSession.updated_at.desc()
            )  # 按更新时间倒序排列，让最近更新的会话排在前面
        )  # 结束查询语句构造

        chat_sessions = session.exec(statement).all()  # 执行查询并获取全部会话

    return list(chat_sessions)  # 将查询结果转成列表后返回


def create_chat_message(  # 定义创建聊天消息的服务函数
    session_id: int,  # 接收消息所属会话 ID
    role: str,  # 接收消息角色
    content: str,  # 接收消息正文
) -> ChatMessage:  # 返回创建完成的聊天消息对象类型
    chat_message = ChatMessage(  # 构造聊天消息对象
        session_id=session_id,  # 设置消息所属会话 ID
        role=role,  # 设置消息角色
        content=content,  # 设置消息正文
    )  # 结束聊天消息对象构造

    with Session(engine) as session:  # 创建数据库会话
        session.add(chat_message)  # 将新消息对象加入当前会话
        session.commit()  # 提交事务，把新消息写入数据库
        session.refresh(chat_message)  # 刷新对象以获取数据库生成的字段

    return chat_message  # 返回创建完成的聊天消息对象


def find_messages_by_session_id(
    session_id: int,
) -> list[ChatMessage]:  # 定义按会话 ID 查询消息列表的服务函数
    with Session(engine) as session:  # 创建数据库会话
        statement = (  # 开始构造查询当前会话消息的 SQLModel 查询语句
            select(ChatMessage)  # 选择聊天消息表
            .where(ChatMessage.session_id == session_id)  # 只查询指定会话 ID 的消息
            .order_by(ChatMessage.id)  # 按消息 ID 升序排列，保持聊天顺序
        )  # 结束查询语句构造
        chat_messages = session.exec(statement).all()  # 执行查询并获取全部消息

    return list(chat_messages)  # 将查询结果转成列表后返回
