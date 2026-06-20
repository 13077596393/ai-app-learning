# 1. 查询 AgentTask
# 2. 提取 user_input
# 3. 提取 answer
# 4. 提取 task_type
# 5. 从 trace 中尝试提取 prompt_name / prompt_version
# 6. 生成 trace_snapshot
# 7. 写入 bad_cases 表
from datetime import datetime  # 导入 datetime，用来更新时间字段

from typing import Any  # 导入 Any，用来表示字典中可以保存任意结构的数据

from sqlmodel import (
    Session,
    select,
)  # 导入 Session 用来操作数据库，导入 select 用来构造查询语句

from database import engine  # 导入数据库 engine，用来连接 PostgreSQL 数据库

from models import BadCase  # 导入 BadCase 模型，用来写入 bad_cases 表

from services.agent_task_service import (
    get_agent_task,
)  # 导入已有的任务查询函数，用来根据 task_id 查询 AgentTask

from services.agent_trace_service import (
    build_agent_task_trace,
)  # 导入调用链构建函数，用来生成 trace 快照


def build_bad_case_trace_snapshot(  # 定义生成 bad case 调用链快照的函数
    task_id: int,  # 接收 AgentTask ID，用来查询对应任务调用链
) -> dict[str, Any]:  # 返回一个简化后的 trace 快照字典
    trace_result = build_agent_task_trace(
        task_id
    )  # 调用第70章写好的函数，获取完整任务调用链

    if not trace_result.get("success"):  # 判断调用链是否查询失败
        return {  # 如果查询失败，就返回一个简单快照
            "success": False,  # 标记 trace 查询失败
            "error": trace_result.get("error"),  # 保存 trace 查询失败原因
        }  # 失败快照返回结束

    steps = trace_result.get("steps", [])  # 从 trace 结果中取出步骤列表

    task_info = trace_result.get("task", {})  # 从 trace 结果中取出任务基本信息

    total_tool_calls = 0  # 初始化工具调用数量统计

    total_rag_logs = 0  # 初始化 RAG 检索日志数量统计

    total_llm_calls = 0  # 初始化 LLM 调用日志数量统计

    failed_steps = []  # 初始化失败步骤列表

    for step in steps:  # 遍历每一个 AgentStep 调用链记录
        total_tool_calls += len(
            step.get("tool_calls", [])
        )  # 累加当前步骤里的工具调用数量

        total_rag_logs += len(
            step.get("rag_retrieval_logs", [])
        )  # 累加当前步骤里的 RAG 检索日志数量

        total_llm_calls += len(
            step.get("llm_calls", [])
        )  # 累加当前步骤里的 LLM 调用数量

        if step.get("status") == "failed":  # 判断当前步骤是否失败
            failed_steps.append(  # 如果失败，就把失败步骤加入列表
                {  # 创建失败步骤简要信息
                    "step_id": step.get("step_id"),  # 保存失败步骤 ID
                    "step_name": step.get("step_name"),  # 保存失败步骤名称
                    "error": step.get("error"),  # 保存失败原因
                }  # 失败步骤简要信息结束
            )  # 失败步骤追加结束

    return {  # 返回简化后的 trace 快照
        "success": True,  # 标记 trace 快照生成成功
        "task_id": task_info.get("task_id"),  # 保存任务 ID
        "task_type": task_info.get("task_type"),  # 保存任务类型
        "task_status": task_info.get("status"),  # 保存任务状态
        "steps_count": len(steps),  # 保存步骤数量
        "tool_calls_count": total_tool_calls,  # 保存工具调用总数
        "rag_logs_count": total_rag_logs,  # 保存 RAG 检索日志总数
        "llm_calls_count": total_llm_calls,  # 保存 LLM 调用总数
        "failed_steps": failed_steps,  # 保存失败步骤列表
    }  # trace 快照返回结束


def extract_prompt_info_from_trace(  # 定义从 trace 中提取 prompt 名称和版本的函数
    task_id: int,  # 接收 AgentTask ID，用来查询完整调用链
) -> tuple[str | None, str | None]:  # 返回 prompt_name 和 prompt_version
    trace_result = build_agent_task_trace(task_id)  # 查询当前任务的完整调用链

    if not trace_result.get("success"):  # 判断调用链是否查询失败
        return None, None  # 如果失败，就返回空的 prompt_name 和 prompt_version

    steps = trace_result.get("steps", [])  # 从 trace 中取出步骤列表

    for step in reversed(steps):  # 倒序遍历步骤，优先找到最近一次 LLM 调用
        llm_calls = step.get("llm_calls", [])  # 取出当前步骤下的 LLM 调用列表

        for llm_call in reversed(llm_calls):  # 倒序遍历当前步骤下的 LLM 调用
            prompt_name = llm_call.get("prompt_name")  # 取出 prompt 名称

            prompt_version = llm_call.get("prompt_version")  # 取出 prompt 版本

            if prompt_name or prompt_version:  # 判断是否至少有一个 prompt 信息
                return prompt_name, prompt_version  # 返回找到的 prompt 信息

    unlinked_logs = trace_result.get("unlinked_logs", {})  # 取出未绑定 step_id 的日志

    unlinked_llm_calls = unlinked_logs.get(
        "llm_calls", []
    )  # 取出未绑定步骤的 LLM 调用记录

    for llm_call in reversed(unlinked_llm_calls):  # 倒序遍历未绑定步骤的 LLM 调用记录
        prompt_name = llm_call.get("prompt_name")  # 取出 prompt 名称

        prompt_version = llm_call.get("prompt_version")  # 取出 prompt 版本

        if prompt_name or prompt_version:  # 判断是否至少有一个 prompt 信息
            return prompt_name, prompt_version  # 返回找到的 prompt 信息

    return None, None  # 如果完全没找到，就返回 None


def create_bad_case(  # 定义创建 bad case 的服务函数
    task_id: int,  # 接收 AgentTask ID，用来关联是哪一次任务出现了问题
    reason: str,  # 接收 bad case 原因，例如回答错误、引用错误、格式错误
    expected_answer: str | None = None,  # 接收期望答案，可以为空
    category: str = "unknown",  # 接收 bad case 分类，默认 unknown
    severity: str = "medium",  # 接收严重程度，默认 medium
    feedback_source: str = "developer",  # 接收反馈来源，默认 developer
    prompt_name: (
        str | None
    ) = None,  # 接收 prompt 名称，如果不传就尝试从 llm_calls 里提取
    prompt_version: (
        str | None
    ) = None,  # 接收 prompt 版本，如果不传就尝试从 llm_calls 里提取
) -> BadCase | None:  # 返回创建后的 BadCase 对象，如果任务不存在则返回 None
    task = get_agent_task(task_id)  # 调用已有函数，根据 task_id 查询 AgentTask

    if task is None:  # 判断任务是否不存在
        return None  # 如果任务不存在，就不创建 bad case，直接返回 None

    if (
        prompt_name is None or prompt_version is None
    ):  # 判断调用方是否没有手动传 prompt 信息
        auto_prompt_name, auto_prompt_version = extract_prompt_info_from_trace(
            task_id
        )  # 从 trace 的 llm_calls 中自动提取 prompt 信息

        if prompt_name is None:  # 判断 prompt_name 是否仍然为空
            prompt_name = auto_prompt_name  # 如果为空，就使用自动提取到的 prompt_name

        if prompt_version is None:  # 判断 prompt_version 是否仍然为空
            prompt_version = (
                auto_prompt_version  # 如果为空，就使用自动提取到的 prompt_version
            )

    trace_snapshot = build_bad_case_trace_snapshot(
        task_id
    )  # 生成当前任务的简化调用链快照

    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        bad_case = BadCase(  # 创建 BadCase 数据库对象
            task_id=task_id,  # 保存任务 ID
            user_id=getattr(
                task, "user_id", None
            ),  # 保存用户 ID，如果 AgentTask 没有 user_id 字段就保存 None
            task_type=getattr(
                task, "task_type", None
            ),  # 保存任务类型，如果没有 task_type 字段就保存 None
            user_input=getattr(
                task, "user_input", ""
            ),  # 保存用户原始输入，如果没有该字段就保存空字符串
            answer=getattr(
                task, "answer", ""
            ),  # 保存 AI 当时的回答，如果没有该字段就保存空字符串
            expected_answer=expected_answer,  # 保存期望答案
            reason=reason,  # 保存 bad case 原因
            category=category,  # 保存 bad case 分类
            severity=severity,  # 保存严重程度
            status="open",  # 新建 bad case 默认状态为 open
            feedback_source=feedback_source,  # 保存反馈来源
            prompt_name=prompt_name,  # 保存 prompt 名称
            prompt_version=prompt_version,  # 保存 prompt 版本
            trace_snapshot=trace_snapshot,  # 保存简化调用链快照
            fixed_note=None,  # 新建时还没有修复说明，所以为空
            fixed_at=None,  # 新建时还没有修复时间，所以为空
        )  # BadCase 对象创建结束

        session.add(bad_case)  # 把 bad case 对象加入数据库会话

        session.commit()  # 提交事务，把 bad case 保存到数据库

        session.refresh(bad_case)  # 刷新对象，拿到数据库生成的 id 等最新字段

        return bad_case  # 返回创建后的 bad case 对象


def get_bad_case(  # 定义根据 ID 查询 bad case 的函数
    bad_case_id: int,  # 接收 bad case ID
) -> BadCase | None:  # 返回 BadCase 对象，如果不存在就返回 None
    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        bad_case = session.get(BadCase, bad_case_id)  # 根据主键 ID 查询 bad case

        return bad_case  # 返回查询结果，如果不存在就是 None


def list_bad_cases(  # 定义查询 bad case 列表的函数
    status: str | None = None,  # 接收状态筛选条件，例如 open、fixed、ignored，可以为空
    category: (
        str | None
    ) = None,  # 接收分类筛选条件，例如 rag_no_hit、prompt_issue，可以为空
) -> list[BadCase]:  # 返回 BadCase 列表
    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        statement = select(BadCase)  # 构造基础查询语句，默认查询所有 bad case

        if status is not None:  # 判断是否传入状态筛选
            statement = statement.where(  # 如果传入状态，就追加查询条件
                BadCase.status == status  # 限定 bad_cases.status 等于传入状态
            )  # 状态查询条件追加结束

        if category is not None:  # 判断是否传入分类筛选
            statement = statement.where(  # 如果传入分类，就追加查询条件
                BadCase.category == category  # 限定 bad_cases.category 等于传入分类
            )  # 分类查询条件追加结束

        statement = statement.order_by(
            BadCase.id.desc()
        )  # 按 ID 倒序排列，让最新 bad case 排在前面

        bad_cases = session.exec(statement).all()  # 执行查询，获取 bad case 列表

        return list(bad_cases)  # 转成普通 list 后返回



