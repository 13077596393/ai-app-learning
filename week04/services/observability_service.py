from typing import Any  # 导入 Any 类型，用来表示 JSON 字段里可以保存任意结构的数据

from sqlmodel import Session  # 导入 Session，用来创建数据库会话并执行数据库操作

from database import engine  # 导入数据库 engine，用来连接 PostgreSQL 数据库

from models import LlmCall  # 导入 LlmCall 模型，用来创建 LLM 调用日志记录

from models import ToolCall  # 导入 ToolCall 模型，用来创建工具调用日志记录

from models import (
    RagRetrievalLog,
)  # 导入 RagRetrievalLog 模型，用来创建 RAG 检索日志记录


def create_llm_call(  # 定义创建 LLM 调用日志的函数
    task_id: int | None,  # 接收 AgentTask ID，用来关联一次完整任务，也就是 trace
    step_id: int | None,  # 接收 AgentStep ID，用来关联任务里的某个步骤，也就是 span
    model_name: str,  # 接收模型名称，例如 deepseek-chat、qwen-plus、gpt-4o-mini
    prompt: str,  # 接收发送给模型的完整 prompt 内容
    response: str = "",  # 接收模型返回的文本结果，默认是空字符串
    input_tokens: int = 0,  # 接收输入 token 数，默认是 0
    output_tokens: int = 0,  # 接收输出 token 数，默认是 0
    total_tokens: int | None = None,  # 接收总 token 数，如果不传就自动计算
    cost: float = 0.0,  # 接收本次模型调用的预估成本，默认是 0
    latency_ms: int = 0,  # 接收本次模型调用耗时，单位是毫秒
    status: str = "success",  # 接收调用状态，默认是 success
    error: str | None = None,  # 接收错误信息，成功时为空
    prompt_name: str | None = None,  # 接收 prompt 名称，后面做 prompt 版本管理会用到
    prompt_version: str | None = None,  # 接收 prompt 版本，后面做 prompt 版本管理会用到
) -> LlmCall:  # 返回创建后的 LlmCall 数据库对象
    if total_tokens is None:  # 判断调用方有没有传 total_tokens
        total_tokens = (
            input_tokens + output_tokens
        )  # 如果没有传，就用输入 token 加输出 token 计算总 token

    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        llm_call = LlmCall(  # 创建一条 LLM 调用日志对象
            task_id=task_id,  # 保存任务 ID，用来关联 AgentTask
            step_id=step_id,  # 保存步骤 ID，用来关联 AgentStep
            model_name=model_name,  # 保存模型名称
            prompt=prompt,  # 保存完整 prompt
            response=response,  # 保存模型返回结果
            input_tokens=input_tokens,  # 保存输入 token 数
            output_tokens=output_tokens,  # 保存输出 token 数
            total_tokens=total_tokens,  # 保存总 token 数
            cost=cost,  # 保存预估成本
            latency_ms=latency_ms,  # 保存调用耗时
            status=status,  # 保存调用状态
            error=error,  # 保存错误信息
            prompt_name=prompt_name,  # 保存 prompt 名称
            prompt_version=prompt_version,  # 保存 prompt 版本
        )  # LLM 调用日志对象创建结束

        session.add(llm_call)  # 把 LLM 调用日志加入数据库会话
        session.commit()  # 提交事务，把日志真正保存到数据库
        session.refresh(llm_call)  # 刷新对象，拿到数据库生成的 id 等最新字段

        return llm_call  # 返回创建后的 LLM 调用日志对象


def create_tool_call(  # 定义创建工具调用日志的函数
    task_id: int | None,  # 接收 AgentTask ID，用来关联一次完整任务，也就是 trace
    step_id: int | None,  # 接收 AgentStep ID，用来关联任务里的某个步骤，也就是 span
    tool_name: str,  # 接收工具名称，例如 search_knowledge_base、generate_report、export_markdown
    tool_input: dict[str, Any] | None = None,  # 接收工具输入参数，默认可以为空
    tool_output: dict[str, Any] | None = None,  # 接收工具输出结果，默认可以为空
    latency_ms: int = 0,  # 接收工具执行耗时，单位是毫秒
    cost: float = 0.0,  # 接收工具调用成本，本地工具一般是 0，外部付费 API 可以记录实际成本
    status: str = "success",  # 接收工具调用状态，默认是 success
    error: str | None = None,  # 接收错误信息，成功时为空
) -> ToolCall:  # 返回创建后的 ToolCall 数据库对象
    if tool_input is None:  # 判断工具输入是否为空
        tool_input = {}  # 如果为空，就使用空字典，避免 JSON 字段保存 None

    if tool_output is None:  # 判断工具输出是否为空
        tool_output = {}  # 如果为空，就使用空字典，避免 JSON 字段保存 None

    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        tool_call = ToolCall(  # 创建一条工具调用日志对象
            task_id=task_id,  # 保存任务 ID，用来关联 AgentTask
            step_id=step_id,  # 保存步骤 ID，用来关联 AgentStep
            tool_name=tool_name,  # 保存工具名称
            tool_input=tool_input,  # 保存工具输入参数
            tool_output=tool_output,  # 保存工具输出结果
            latency_ms=latency_ms,  # 保存工具执行耗时
            cost=cost,  # 保存工具调用成本
            status=status,  # 保存工具调用状态
            error=error,  # 保存工具错误信息
        )  # 工具调用日志对象创建结束

        session.add(tool_call)  # 把工具调用日志加入数据库会话
        session.commit()  # 提交事务，把日志保存到数据库
        session.refresh(tool_call)  # 刷新对象，拿到数据库生成的 id 等最新字段

        return tool_call  # 返回创建后的工具调用日志对象


def create_rag_retrieval_log(  # 定义创建 RAG 检索日志的函数
    task_id: int | None,  # 接收 AgentTask ID，用来关联一次完整任务
    step_id: int | None,  # 接收 AgentStep ID，用来关联任务里的某个步骤
    knowledge_base_id: int | None,  # 接收知识库 ID，用来记录本次检索的是哪个知识库
    query: str,  # 接收本次检索的问题或查询文本
    top_k: int = 5,  # 接收本次最多检索多少条 chunk，默认是 5
    retrieved_count: int = 0,  # 接收实际命中的 chunk 数量，默认是 0
    matched_chunk_ids: (
        list[int] | None
    ) = None,  # 接收命中的 chunk ID 列表，默认可以为空
    scores: (
        list[dict[str, Any]] | None
    ) = None,  # 接收每个 chunk 的分数信息，默认可以为空
    context: str = "",  # 接收最终拼接给 LLM 的上下文内容，默认是空字符串
    latency_ms: int = 0,  # 接收本次检索耗时，单位是毫秒
    status: str = "success",  # 接收检索状态，默认是 success
    error: str | None = None,  # 接收错误信息，成功时为空
) -> RagRetrievalLog:  # 返回创建后的 RagRetrievalLog 数据库对象
    if matched_chunk_ids is None:  # 判断命中的 chunk ID 列表是否为空
        matched_chunk_ids = []  # 如果为空，就使用空列表，方便 JSON 字段保存

    if scores is None:  # 判断分数列表是否为空
        scores = []  # 如果为空，就使用空列表，方便 JSON 字段保存

    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        retrieval_log = RagRetrievalLog(  # 创建一条 RAG 检索日志对象
            task_id=task_id,  # 保存任务 ID
            step_id=step_id,  # 保存步骤 ID
            knowledge_base_id=knowledge_base_id,  # 保存知识库 ID
            query=query,  # 保存检索问题
            top_k=top_k,  # 保存 top_k
            retrieved_count=retrieved_count,  # 保存实际命中数量
            matched_chunk_ids=matched_chunk_ids,  # 保存命中的 chunk ID 列表
            scores=scores,  # 保存分数信息
            context=context,  # 保存最终上下文
            latency_ms=latency_ms,  # 保存检索耗时
            status=status,  # 保存检索状态
            error=error,  # 保存错误信息
        )  # RAG 检索日志对象创建结束

        session.add(retrieval_log)  # 把 RAG 检索日志加入数据库会话
        session.commit()  # 提交事务，把日志保存到数据库
        session.refresh(retrieval_log)  # 刷新对象，拿到数据库生成的 id 等最新字段

        return retrieval_log  # 返回创建后的 RAG 检索日志对象


