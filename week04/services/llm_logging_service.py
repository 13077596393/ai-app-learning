# 这个文件做了
# 1. 记录开始时间
# 2. 调用 LLM
# 3. 计算 latency_ms
# 4. 估算 input_tokens / output_tokens / total_tokens
# 5. 估算 cost
# 6. 写入 llm_calls 表
# 7. 返回模型回答

import time  # 导入 time 模块，用来记录 LLM 调用开始和结束时间，从而计算耗时

from services.ai_service import (
    call_llm_api,
)  # 从 ai_service.py 导入原来的 LLM 调用函数，真正负责请求模型

from services.observability_service import (
    create_llm_call,
)  # 导入 create_llm_call，用来把 LLM 调用日志保存到 llm_calls 表


def estimate_llm_tokens(
    text: str,
) -> int:  # 定义一个简单的 token 估算函数，接收一段文本并返回估算 token 数
    if not text:  # 判断文本是否为空，如果为空字符串或 None，就直接返回 0
        return 0  # 空文本没有 token，所以返回 0

    return max(
        1, len(text) // 2
    )  # 用简单规则估算 token 数：大约每 2 个字符算 1 个 token，至少返回 1


def estimate_llm_cost(  # 定义一个简单的 LLM 成本估算函数
    model_name: str,  # 接收模型名称，例如 deepseek-chat、qwen-plus
    input_tokens: int,  # 接收输入 token 数
    output_tokens: int,  # 接收输出 token 数
) -> float:  # 返回本次调用的预估成本
    input_price_per_1k = (
        0.001  # 设置每 1000 个输入 token 的示例价格，这里先用学习版假价格
    )

    output_price_per_1k = (
        0.002  # 设置每 1000 个输出 token 的示例价格，这里先用学习版假价格
    )

    input_cost = input_tokens / 1000 * input_price_per_1k  # 计算输入 token 的预估费用

    output_cost = (
        output_tokens / 1000 * output_price_per_1k
    )  # 计算输出 token 的预估费用

    total_cost = input_cost + output_cost  # 把输入费用和输出费用相加，得到总费用

    return round(total_cost, 6)  # 返回保留 6 位小数的成本，方便数据库保存和前端展示


def normalize_ai_messages(  # 定义标准化消息函数
    prompt: str | None = None,  # 接收 prompt 字符串，可以为空
    ai_messages: list[dict] | None = None,  # 接收完整 messages 列表，可以为空
) -> tuple[list[dict], str]:  # 返回标准 messages 列表和日志文本
    if (
        prompt is not None and ai_messages is not None
    ):  # 判断是否同时传了 prompt 和 ai_messages
        raise ValueError(
            "prompt 和 ai_messages 不能同时传，请二选一"
        )  # 同时传会造成歧义，所以直接报错

    if ai_messages is not None:  # 如果传了 ai_messages，就使用 ai_messages
        prompt_for_log = "\n".join(  # 把 ai_messages 转成日志文本
            f"{message.get('role', '')}: {message.get('content', '')}"  # 每条消息转换成 role: content
            for message in ai_messages  # 遍历消息列表
        )  # 拼接结束

        return ai_messages, prompt_for_log  # 返回 messages 和日志文本

    if prompt is None:  # 如果 prompt 和 ai_messages 都没传
        raise ValueError("prompt 和 ai_messages 不能同时为空")  # 抛出参数错误

    final_ai_messages = [  # 把 prompt 包装成 messages
        {  # 创建一条用户消息
            "role": "user",  # 设置角色为 user
            "content": prompt,  # 设置消息内容为 prompt
        }  # 用户消息结束
    ]  # messages 构造结束

    return final_ai_messages, prompt  # 返回 messages 和日志文本


def call_llm_with_logging(  # 定义带日志记录的大模型调用函数
    task_id: int | None,  # 接收 AgentTask ID，用来关联一次完整 Agent 任务
    step_id: int | None,  # 接收 AgentStep ID，用来关联某个执行步骤
    prompt: str | None = None,  # 接收 prompt 字符串，适合简单调用场景
    ai_messages: (
        list[dict] | None
    ) = None,  # 接收完整 messages 列表，适合 system prompt、历史对话、RAG 场景
    model_name: str = "default",  # 接收模型名称，这里主要用于日志记录
    prompt_name: str | None = None,  # 接收 prompt 名称，用于 prompt 版本追踪
    prompt_version: str | None = None,  # 接收 prompt 版本，用于 bad case 复盘
) -> str:  # 返回模型生成的文本结果
    start_time = time.time()  # 记录大模型调用开始时间，用来计算耗时

    prompt_for_log = prompt or ""  # 先准备日志用 prompt 文本，避免异常时变量不存在

    try:  # 使用 try 包住大模型调用，方便成功和失败都能写入日志
        final_ai_messages, prompt_for_log = (
            normalize_ai_messages(  # 标准化输入，把 prompt 或 ai_messages 转成统一 messages
                prompt=prompt,  # 传入 prompt 字符串
                ai_messages=ai_messages,  # 传入完整 messages 列表
            )
        )  # 输入标准化结束

        response_text = call_llm_api(  # 调用 ai_service.py 中真正请求大模型的函数
            final_ai_messages  # 传入标准化后的 messages 列表
        )  # 大模型调用结束，拿到回复文本

        latency_ms = int(
            (time.time() - start_time) * 1000
        )  # 计算本次模型调用耗时，单位毫秒

        input_tokens = estimate_llm_tokens(
            prompt_for_log
        )  # 根据完整输入文本估算输入 token 数

        output_tokens = estimate_llm_tokens(
            response_text
        )  # 根据模型回复文本估算输出 token 数

        total_tokens = input_tokens + output_tokens  # 计算总 token 数

        cost = estimate_llm_cost(  # 调用成本估算函数
            model_name=model_name,  # 传入模型名称
            input_tokens=input_tokens,  # 传入输入 token 数
            output_tokens=output_tokens,  # 传入输出 token 数
        )  # 成本估算结束

        create_llm_call(  # 写入 LLM 调用日志
            task_id=task_id,  # 保存任务 ID
            step_id=step_id,  # 保存步骤 ID
            model_name=model_name,  # 保存模型名称
            prompt=prompt_for_log,  # 保存完整输入文本
            response=response_text,  # 保存模型回复文本
            input_tokens=input_tokens,  # 保存输入 token 数
            output_tokens=output_tokens,  # 保存输出 token 数
            total_tokens=total_tokens,  # 保存总 token 数
            cost=cost,  # 保存预估成本
            latency_ms=latency_ms,  # 保存模型调用耗时
            status="success",  # 保存调用状态为成功
            error=None,  # 成功时错误信息为空
            prompt_name=prompt_name,  # 保存 prompt 名称
            prompt_version=prompt_version,  # 保存 prompt 版本
        )  # LLM 调用日志写入结束

        return response_text  # 返回模型回复文本

    except Exception as exc:  # 捕获大模型调用或日志写入过程中的异常
        latency_ms = int((time.time() - start_time) * 1000)  # 即使失败，也计算调用耗时

        error_message = str(exc)  # 把异常对象转成字符串，方便保存到数据库

        create_llm_call(  # 失败时也写入 LLM 调用日志
            task_id=task_id,  # 保存任务 ID
            step_id=step_id,  # 保存步骤 ID
            model_name=model_name,  # 保存模型名称
            prompt=prompt_for_log,  # 保存失败时的输入内容
            response="",  # 失败时没有正常回复，所以保存空字符串
            input_tokens=estimate_llm_tokens(prompt_for_log),  # 估算失败请求的输入 token
            output_tokens=0,  # 失败时没有输出 token
            total_tokens=estimate_llm_tokens(prompt_for_log),  # 总 token 暂时等于输入 token
            cost=0.0,  # 失败时成本先记为 0
            latency_ms=latency_ms,  # 保存失败调用耗时
            status="failed",  # 保存调用状态为失败
            error=error_message,  # 保存错误信息
            prompt_name=prompt_name,  # 保存 prompt 名称
            prompt_version=prompt_version,  # 保存 prompt 版本
        )  # 失败日志写入结束

        raise  # 继续把异常抛给上层，让接口知道调用失败了
