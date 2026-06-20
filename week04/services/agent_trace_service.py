# 文件做了
# 1. 查询任务本身
# 2. 查询任务步骤
# 3. 查询每个步骤下的 tool_calls
# 4. 查询每个步骤下的 rag_retrieval_logs
# 5. 查询每个步骤下的 llm_calls
# 6. 组装成完整 trace 返回结果
# 最终服务于接口：GET /agent/tasks/{task_id}/trace
from sqlmodel import (
    Session,
    select,
)  # 导入 Session 用来创建数据库会话，导入 select 用来构造查询语句

from database import engine  # 导入数据库 engine，用来连接 PostgreSQL 数据库

from models import LlmCall  # 导入 LlmCall 模型，用来查询 llm_calls 表

from models import ToolCall  # 导入 ToolCall 模型，用来查询 tool_calls 表

from models import (
    RagRetrievalLog,
)  # 导入 RagRetrievalLog 模型，用来查询 rag_retrieval_logs 表
from models import AgentTask  # 导入 AgentTask 类型，用来给返回值做类型标注

from models import AgentStep  # 导入 AgentStep 类型，用来给返回值做类型标注

from services.agent_task_service import (  # 从 Agent 任务服务中导入已有查询函数
    get_agent_task,  # 导入查询单个 AgentTask 的函数，避免重复写查询逻辑
)  # get_agent_task 导入结束

from services.agent_task_service import (  # 从 Agent 任务服务中导入已有步骤查询函数
    list_agent_steps,  # 导入查询某个任务下所有 AgentStep 的函数
)  # list_agent_steps 导入结束


def get_task_and_steps_for_trace(  # 定义查询调用链基础数据的函数
    task_id: int,  # 接收要查询的 AgentTask ID
) -> tuple[AgentTask | None, list[AgentStep]]:  # 返回任务对象和步骤列表
    task = get_agent_task(task_id)  # 调用已有函数，根据 task_id 查询 AgentTask 主任务

    if task is None:  # 判断任务是否不存在
        return None, []  # 如果任务不存在，就返回 None 和空步骤列表

    steps = list_agent_steps(
        task_id
    )  # 调用已有函数，查询这个任务下的所有 AgentStep 步骤

    return task, steps  # 返回任务对象和步骤列表


def list_tool_calls_for_step(  # 定义查询某个步骤下工具调用日志的函数
    task_id: int,  # 接收 AgentTask ID，用来限定当前任务
    step_id: int | None,  # 接收 AgentStep ID，用来限定当前步骤；可能为空
) -> list[ToolCall]:  # 返回 ToolCall 日志列表
    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        statement = select(ToolCall).where(  # 构造查询 tool_calls 表的语句
            ToolCall.task_id == task_id  # 先限定 tool_calls.task_id 必须等于当前任务 ID
        )  # 基础查询条件构造结束

        if step_id is not None:  # 判断当前步骤 ID 是否存在
            statement = statement.where(  # 如果 step_id 存在，就继续追加查询条件
                ToolCall.step_id
                == step_id  # 限定 tool_calls.step_id 必须等于当前步骤 ID
            )  # step_id 查询条件追加结束

        statement = statement.order_by(
            ToolCall.id
        )  # 按工具调用日志 ID 升序排列，保证显示顺序稳定

        tool_calls = session.exec(statement).all()  # 执行查询语句，拿到工具调用日志结果

        return list(tool_calls)  # 把查询结果转换成普通 list 后返回


def list_rag_logs_for_step(  # 定义查询某个步骤下 RAG 检索日志的函数
    task_id: int,  # 接收 AgentTask ID，用来限定当前任务
    step_id: int | None,  # 接收 AgentStep ID，用来限定当前步骤；可能为空
) -> list[RagRetrievalLog]:  # 返回 RagRetrievalLog 日志列表
    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        statement = select(
            RagRetrievalLog
        ).where(  # 构造查询 rag_retrieval_logs 表的语句
            RagRetrievalLog.task_id
            == task_id  # 先限定 rag_retrieval_logs.task_id 必须等于当前任务 ID
        )  # 基础查询条件构造结束

        if step_id is not None:  # 判断当前步骤 ID 是否存在
            statement = statement.where(  # 如果 step_id 存在，就继续追加查询条件
                RagRetrievalLog.step_id
                == step_id  # 限定 rag_retrieval_logs.step_id 必须等于当前步骤 ID
            )  # step_id 查询条件追加结束

        statement = statement.order_by(
            RagRetrievalLog.id
        )  # 按 RAG 检索日志 ID 升序排列

        rag_logs = session.exec(statement).all()  # 执行查询语句，拿到 RAG 检索日志结果

        return list(rag_logs)  # 把查询结果转换成普通 list 后返回


def list_llm_calls_for_step(  # 定义查询某个步骤下 LLM 调用日志的函数
    task_id: int,  # 接收 AgentTask ID，用来限定当前任务
    step_id: int | None,  # 接收 AgentStep ID，用来限定当前步骤；可能为空
) -> list[LlmCall]:  # 返回 LlmCall 日志列表
    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        statement = select(LlmCall).where(  # 构造查询 llm_calls 表的语句
            LlmCall.task_id == task_id  # 先限定 llm_calls.task_id 必须等于当前任务 ID
        )  # 基础查询条件构造结束

        if step_id is not None:  # 判断当前步骤 ID 是否存在
            statement = statement.where(  # 如果 step_id 存在，就继续追加查询条件
                LlmCall.step_id == step_id  # 限定 llm_calls.step_id 必须等于当前步骤 ID
            )  # step_id 查询条件追加结束

        statement = statement.order_by(LlmCall.id)  # 按 LLM 调用日志 ID 升序排列

        llm_calls = session.exec(statement).all()  # 执行查询语句，拿到 LLM 调用日志结果

        return list(llm_calls)  # 把查询结果转换成普通 list 后返回


def format_datetime_value(value):  # 定义时间格式化函数，用来把 datetime 转成字符串
    if value is None:  # 判断时间值是否为空
        return None  # 如果为空，就返回 None，避免后面报错

    return (
        value.isoformat()
    )  # 如果是 datetime，就转成 ISO 格式字符串，方便接口返回 JSON


def build_tool_call_trace(tool_call: ToolCall) -> dict:  # 定义工具调用日志转换函数
    return {  # 返回一个字典，方便后面接口直接转成 JSON
        "id": tool_call.id,  # 返回工具调用日志 ID
        "task_id": tool_call.task_id,  # 返回关联的任务 ID
        "step_id": tool_call.step_id,  # 返回关联的步骤 ID
        "tool_name": tool_call.tool_name,  # 返回工具名称
        "tool_input": tool_call.tool_input,  # 返回工具输入参数
        "tool_output": tool_call.tool_output,  # 返回工具输出结果
        "latency_ms": tool_call.latency_ms,  # 返回工具执行耗时
        "cost": tool_call.cost,  # 返回工具调用成本
        "status": tool_call.status,  # 返回工具调用状态
        "error": tool_call.error,  # 返回工具错误信息
        "created_at": format_datetime_value(
            tool_call.created_at
        ),  # 返回格式化后的创建时间
    }  # 工具调用日志字典返回结束


def build_rag_log_trace(rag_log: RagRetrievalLog) -> dict:  # 定义 RAG 检索日志转换函数
    return {  # 返回一个字典，方便接口转成 JSON
        "id": rag_log.id,  # 返回 RAG 检索日志 ID
        "task_id": rag_log.task_id,  # 返回关联任务 ID
        "step_id": rag_log.step_id,  # 返回关联步骤 ID
        "knowledge_base_id": rag_log.knowledge_base_id,  # 返回知识库 ID
        "query": rag_log.query,  # 返回检索问题
        "top_k": rag_log.top_k,  # 返回本次检索 top_k
        "retrieved_count": rag_log.retrieved_count,  # 返回实际命中数量
        "matched_chunk_ids": rag_log.matched_chunk_ids,  # 返回命中的 chunk ID 列表
        "scores": rag_log.scores,  # 返回每个 chunk 的分数信息
        "context": rag_log.context,  # 返回最终拼接给 LLM 的上下文
        "latency_ms": rag_log.latency_ms,  # 返回检索耗时
        "status": rag_log.status,  # 返回检索状态
        "error": rag_log.error,  # 返回检索错误信息
        "created_at": format_datetime_value(
            rag_log.created_at
        ),  # 返回格式化后的创建时间
    }  # RAG 检索日志字典返回结束


def build_llm_call_trace(llm_call: LlmCall) -> dict:  # 定义 LLM 调用日志转换函数
    return {  # 返回一个字典，方便接口转成 JSON
        "id": llm_call.id,  # 返回 LLM 调用日志 ID
        "task_id": llm_call.task_id,  # 返回关联任务 ID
        "step_id": llm_call.step_id,  # 返回关联步骤 ID
        "model_name": llm_call.model_name,  # 返回模型名称
        "prompt_name": llm_call.prompt_name,  # 返回 prompt 名称
        "prompt_version": llm_call.prompt_version,  # 返回 prompt 版本
        "prompt": llm_call.prompt,  # 返回完整 prompt
        "response": llm_call.response,  # 返回模型响应内容
        "input_tokens": llm_call.input_tokens,  # 返回输入 token 数
        "output_tokens": llm_call.output_tokens,  # 返回输出 token 数
        "total_tokens": llm_call.total_tokens,  # 返回总 token 数
        "cost": llm_call.cost,  # 返回预估成本
        "latency_ms": llm_call.latency_ms,  # 返回模型调用耗时
        "status": llm_call.status,  # 返回调用状态
        "error": llm_call.error,  # 返回错误信息
        "created_at": format_datetime_value(
            llm_call.created_at
        ),  # 返回格式化后的创建时间
    }  # LLM 调用日志字典返回结束


def build_step_trace(  # 定义单个 AgentStep 调用链组装函数
    task_id: int,  # 接收当前任务 ID
    step: AgentStep,  # 接收当前步骤对象
) -> dict:  # 返回当前步骤的完整调用链字典
    tool_calls = list_tool_calls_for_step(  # 查询当前步骤下的工具调用日志
        task_id=task_id,  # 传入任务 ID
        step_id=step.id,  # 传入当前步骤 ID
    )  # 工具调用日志查询结束

    rag_logs = list_rag_logs_for_step(  # 查询当前步骤下的 RAG 检索日志
        task_id=task_id,  # 传入任务 ID
        step_id=step.id,  # 传入当前步骤 ID
    )  # RAG 检索日志查询结束

    llm_calls = list_llm_calls_for_step(  # 查询当前步骤下的 LLM 调用日志
        task_id=task_id,  # 传入任务 ID
        step_id=step.id,  # 传入当前步骤 ID
    )  # LLM 调用日志查询结束

    return {  # 返回当前步骤的完整调用链
        "step_id": step.id,  # 返回步骤 ID
        "task_id": step.task_id,  # 返回任务 ID
        "step_name": step.step_name,  # 返回步骤名称
        "step_type": step.step_type,  # 返回步骤类型
        "status": step.status,  # 返回步骤状态
        "input_data": step.input_data,  # 返回步骤输入数据
        "output_data": step.output_data,  # 返回步骤输出数据
        "error": step.error,  # 返回步骤错误信息
        "retry_count": step.retry_count,  # 返回步骤重试次数
        "is_retry": step.is_retry,  # 返回当前步骤是否是重试步骤
        "started_at": format_datetime_value(step.started_at),  # 返回格式化后的开始时间
        "finished_at": format_datetime_value(
            step.finished_at
        ),  # 返回格式化后的结束时间
        "created_at": format_datetime_value(step.created_at),  # 返回格式化后的创建时间
        "tool_calls": [
            build_tool_call_trace(item) for item in tool_calls
        ],  # 返回当前步骤下的工具调用日志列表
        "rag_retrieval_logs": [
            build_rag_log_trace(item) for item in rag_logs
        ],  # 返回当前步骤下的 RAG 检索日志列表
        "llm_calls": [
            build_llm_call_trace(item) for item in llm_calls
        ],  # 返回当前步骤下的 LLM 调用日志列表
    }  # 当前步骤调用链返回结束


def build_unlinked_logs(task_id: int) -> dict:  # 定义组装未绑定步骤日志的函数
    tool_calls = list_tool_calls_for_step(
        task_id, None
    )  # 查询当前任务下所有工具调用日志

    rag_logs = list_rag_logs_for_step(task_id, None)  # 查询当前任务下所有 RAG 检索日志

    llm_calls = list_llm_calls_for_step(
        task_id, None
    )  # 查询当前任务下所有 LLM 调用日志

    unlinked_tool_calls = [
        item for item in tool_calls if item.step_id is None
    ]  # 过滤出 step_id 为空的工具调用日志

    unlinked_rag_logs = [
        item for item in rag_logs if item.step_id is None
    ]  # 过滤出 step_id 为空的 RAG 检索日志

    unlinked_llm_calls = [
        item for item in llm_calls if item.step_id is None
    ]  # 过滤出 step_id 为空的 LLM 调用日志

    return {  # 返回未绑定步骤的日志结构
        "tool_calls": [
            build_tool_call_trace(item) for item in unlinked_tool_calls
        ],  # 返回未绑定步骤的工具调用日志
        "rag_retrieval_logs": [
            build_rag_log_trace(item) for item in unlinked_rag_logs
        ],  # 返回未绑定步骤的 RAG 检索日志
        "llm_calls": [
            build_llm_call_trace(item) for item in unlinked_llm_calls
        ],  # 返回未绑定步骤的 LLM 调用日志
    }  # 未绑定步骤日志返回结束


def build_agent_task_trace(task_id: int) -> dict:  # 定义组装完整 AgentTask 调用链的函数
    task, steps = get_task_and_steps_for_trace(task_id)  # 查询任务对象和任务步骤列表

    if task is None:  # 判断任务是否不存在
        return {  # 返回任务不存在的结果
            "success": False,  # 标记查询失败
            "task_id": task_id,  # 返回用户查询的任务 ID
            "error": "任务不存在",  # 返回错误信息
            "task": None,  # 任务不存在，所以 task 为空
            "steps": [],  # 任务不存在，所以步骤为空
            "unlinked_logs": {},  # 任务不存在，所以未绑定日志为空
        }  # 任务不存在结果返回结束

    step_traces = [  # 构造任务步骤调用链列表
        build_step_trace(task_id=task_id, step=step)  # 组装每一个步骤的调用链
        for step in steps  # 遍历当前任务下的所有步骤
    ]  # 步骤调用链列表构造结束

    return {  # 返回完整任务调用链
        "success": True,  # 标记查询成功
        "task": {  # 返回任务基本信息
            "task_id": task.id,  # 返回任务 ID
            "task_type": task.task_type,  # 返回任务类型
            "status": task.status,  # 返回任务状态
            "progress": task.progress,  # 返回任务进度
            "current_step": task.current_step,  # 返回当前步骤描述
            "user_input": task.user_input,  # 返回用户原始输入
            "answer": task.answer,  # 返回任务最终答案
            "report_id": task.report_id,  # 返回报告 ID
            "markdown_file_path": task.markdown_file_path,  # 返回 Markdown 文件路径
            "job_id": task.job_id,  # 返回 RQ Job ID
            "error": task.error,  # 返回任务错误信息
            "created_at": format_datetime_value(
                task.created_at
            ),  # 返回格式化后的创建时间
            "updated_at": format_datetime_value(
                task.updated_at
            ),  # 返回格式化后的更新时间
            "queued_at": format_datetime_value(
                task.queued_at
            ),  # 返回格式化后的入队时间
            "started_at": format_datetime_value(
                task.started_at
            ),  # 返回格式化后的开始时间
            "finished_at": format_datetime_value(
                task.finished_at
            ),  # 返回格式化后的结束时间
        },  # 任务基本信息结束
        "steps": step_traces,  # 返回步骤调用链列表
        "unlinked_logs": build_unlinked_logs(task_id),  # 返回没有绑定 step_id 的日志
    }  # 完整任务调用链返回结束

