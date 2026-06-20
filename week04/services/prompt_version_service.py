from sqlmodel import (
    Session,
    select,
)  # 导入 Session 用来创建数据库会话，导入 select 用来构造查询语句

from database import engine  # 导入数据库 engine，用来连接 PostgreSQL 数据库

from models import PromptVersion  # 导入 PromptVersion 模型，用来操作 prompt_versions 表


def create_prompt_version(  # 定义创建 prompt 版本的函数
    prompt_name: str,  # 接收 prompt 名称，例如 generate_agent_answer_prompt
    prompt_version: str,  # 接收 prompt 版本号，例如 v1、v2、v3
    prompt_content: str,  # 接收 prompt 的完整内容
    description: str | None = None,  # 接收 prompt 版本说明，可以为空
    task_type: str | None = None,  # 接收适用任务类型，例如 rag_chat、report，可以为空
    is_active: bool = True,  # 接收是否启用，默认启用
) -> PromptVersion:  # 返回创建后的 PromptVersion 对象
    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        prompt_version_obj = PromptVersion(  # 创建 PromptVersion 数据库对象
            prompt_name=prompt_name,  # 保存 prompt 名称
            prompt_version=prompt_version,  # 保存 prompt 版本号
            prompt_content=prompt_content,  # 保存 prompt 完整内容
            description=description,  # 保存 prompt 版本说明
            task_type=task_type,  # 保存适用任务类型
            is_active=is_active,  # 保存是否启用
        )  # PromptVersion 对象创建结束

        session.add(prompt_version_obj)  # 把 PromptVersion 对象加入数据库会话
        session.commit()  # 提交事务，把 prompt 版本真正保存到数据库
        session.refresh(prompt_version_obj)  # 刷新对象，拿到数据库生成的 id 等字段

        return prompt_version_obj  # 返回创建后的 prompt 版本对象


def get_prompt_version(  # 定义查询指定 prompt 版本的函数
    prompt_name: str,  # 接收 prompt 名称
    prompt_version: str,  # 接收 prompt 版本号
) -> PromptVersion | None:  # 返回 PromptVersion 对象，如果不存在则返回 None
    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        statement = select(PromptVersion).where(  # 构造查询 prompt_versions 表的语句
            PromptVersion.prompt_name
            == prompt_name,  # 查询 prompt_name 等于指定名称的记录
            PromptVersion.prompt_version
            == prompt_version,  # 查询 prompt_version 等于指定版本的记录
        )  # 查询条件构造结束

        prompt_version_obj = session.exec(statement).first()  # 执行查询，并取第一条结果

        return prompt_version_obj  # 返回查询到的 prompt 版本对象，如果没有就是 None


def get_active_prompt_version(  # 定义查询当前启用 prompt 版本的函数
    prompt_name: str,  # 接收 prompt 名称
    task_type: str | None = None,  # 接收任务类型，可以为空
) -> PromptVersion | None:  # 返回当前启用的 PromptVersion，如果不存在则返回 None
    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        statement = select(PromptVersion).where(  # 构造查询 prompt_versions 表的语句
            PromptVersion.prompt_name == prompt_name,  # 查询指定 prompt 名称
            PromptVersion.is_active == True,  # 只查询当前启用的 prompt 版本
        )  # 基础查询条件构造结束

        if task_type is not None:  # 判断是否传入了任务类型
            statement = statement.where(  # 如果传入了任务类型，就继续追加查询条件
                PromptVersion.task_type
                == task_type  # 限定 task_type 必须等于传入的任务类型
            )  # task_type 查询条件追加结束

        statement = statement.order_by(
            PromptVersion.id.desc()
        )  # 按 ID 倒序排列，优先返回最新创建的启用版本

        prompt_version_obj = session.exec(statement).first()  # 执行查询，并取第一条结果

        return prompt_version_obj  # 返回当前启用的 prompt 版本对象，如果没有就是 None


def list_prompt_versions(  # 定义查询 prompt 历史版本列表的函数
    prompt_name: str | None = None,  # 接收 prompt 名称，可以为空
    task_type: str | None = None,  # 接收任务类型，可以为空
) -> list[PromptVersion]:  # 返回 PromptVersion 列表
    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        statement = select(PromptVersion)  # 构造基础查询语句，默认查询所有 prompt 版本

        if prompt_name is not None:  # 判断是否传入了 prompt 名称
            statement = statement.where(  # 如果传入了 prompt 名称，就追加查询条件
                PromptVersion.prompt_name == prompt_name  # 限定 prompt_name 等于传入值
            )  # prompt_name 查询条件追加结束

        if task_type is not None:  # 判断是否传入了任务类型
            statement = statement.where(  # 如果传入了任务类型，就追加查询条件
                PromptVersion.task_type == task_type  # 限定 task_type 等于传入值
            )  # task_type 查询条件追加结束

        statement = statement.order_by(
            PromptVersion.id.desc()
        )  # 按 ID 倒序排列，让最新版本排在前面

        prompt_versions = session.exec(statement).all()  # 执行查询，获取所有匹配记录

        return list(prompt_versions)  # 转成普通 list 后返回


def deactivate_prompt_version(  # 定义停用某个 prompt 版本的函数
    prompt_name: str,  # 接收 prompt 名称
    prompt_version: str,  # 接收 prompt 版本号
) -> PromptVersion | None:  # 返回被停用的 PromptVersion，如果不存在则返回 None
    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        statement = select(PromptVersion).where(  # 构造查询指定 prompt 版本的语句
            PromptVersion.prompt_name == prompt_name,  # 限定 prompt 名称
            PromptVersion.prompt_version == prompt_version,  # 限定 prompt 版本
        )  # 查询条件构造结束

        prompt_version_obj = session.exec(statement).first()  # 执行查询，并取第一条记录

        if prompt_version_obj is None:  # 判断指定 prompt 版本是否不存在
            return None  # 如果不存在，直接返回 None

        prompt_version_obj.is_active = False  # 把当前 prompt 版本设置为停用

        session.add(prompt_version_obj)  # 把修改后的对象重新加入数据库会话
        session.commit()  # 提交事务，把停用状态保存到数据库
        session.refresh(prompt_version_obj)  # 刷新对象，拿到最新数据

        return prompt_version_obj  # 返回停用后的 prompt 版本对象
