from typing import Any  # 导入 Any，用来表示 citations 里面的字段可以是任意类型

from sqlmodel import Session  # 导入 Session，用来创建数据库会话

from database import engine  # 从 database.py 导入数据库 engine，用来连接数据库
from models import AgentRun  # 从 models.py 导入 AgentRun 数据库模型


def save_agent_run_to_db(  # 定义保存 Agent 执行结果到数据库的函数
    user_input: str,  # 接收用户原始输入
    task_type: str,  # 接收任务类型
    answer: str,  # 接收 Agent 最终回答
    context: str = "",  # 接收 RAG 检索上下文，默认空字符串
    citations: list | None = None,  # 接收引用来源列表，可以为空
    steps: list | None = None,  # 接收执行步骤列表，可以为空
    session_id: int | None = None,  # 接收会话 ID，可以为空
    knowledge_base_id: int | None = None,  # 接收知识库 ID，可以为空
    status: str = "success",  # 接收执行状态，默认 success
    error: str | None = None,  # 接收错误信息，可以为空
    task_id: int | None = None,  # 接收 AgentTask ID，用来关联 trace 调用链
) -> AgentRun:  # 返回保存后的 AgentRun 对象
    if citations is None:  # 判断引用来源是否为空
        citations = []  # 如果为空，就使用空列表

    if steps is None:  # 判断执行步骤是否为空
        steps = []  # 如果为空，就使用空列表

    with Session(engine) as session:  # 创建数据库会话
        agent_run = AgentRun(  # 创建 AgentRun 数据库对象
            task_id=task_id,  # 保存 AgentTask ID
            user_input=user_input,  # 保存用户原始输入
            task_type=task_type,  # 保存任务类型
            answer=answer,  # 保存最终回答
            context=context,  # 保存 RAG 上下文
            citations=citations,  # 保存引用来源列表
            steps=steps,  # 保存执行步骤列表
            session_id=session_id,  # 保存会话 ID
            knowledge_base_id=knowledge_base_id,  # 保存知识库 ID
            status=status,  # 保存执行状态
            error=error,  # 保存错误信息
        )  # AgentRun 对象创建结束

        session.add(agent_run)  # 把 AgentRun 加入数据库会话
        session.commit()  # 提交事务
        session.refresh(agent_run)  # 刷新对象，拿到数据库生成的 ID

        return agent_run  # 返回保存后的 AgentRun 对象
