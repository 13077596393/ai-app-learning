from services.llm_logging_service import (
    call_llm_with_logging,
)  # 导入带日志记录的大模型调用函数


def generate_agent_answer(  # 定义 Agent 回答生成函数
    task_type: str,  # 接收任务类型，例如 normal_chat、rag_chat、report
    user_input: str,  # 接收用户原始输入
    context: str = "",  # 接收 RAG 检索得到的上下文，普通聊天时可以为空
    task_id: int | None = None,  # 接收 AgentTask ID，用来关联 llm_calls 日志
    step_id: int | None = None,  # 接收 AgentStep ID，用来关联 llm_calls 日志
) -> str:  # 返回模型生成的回答文本
    if task_type == "rag_chat":  # 判断当前任务是否是 RAG 问答
        prompt = f"""你是一个严谨的知识库问答助手，请根据参考资料回答用户问题。

参考资料：
{context}

用户问题：
{user_input}

回答要求：
1. 优先根据参考资料回答。
2. 如果参考资料不足，请明确说明“知识库中没有找到足够信息”。
3. 回答要清晰、准确、分点说明。
"""  # 构造 RAG 问答 prompt
    else:  # 如果不是 RAG 问答，就走普通聊天逻辑
        prompt = f"""你是一个 AI 应用助手，请回答用户的问题。

用户问题：
{user_input}

回答要求：
1. 用中文回答。
2. 回答要清晰、简洁。
3. 如果是技术问题，请尽量分步骤解释。
"""  # 构造普通聊天 prompt

    answer = call_llm_with_logging(  # 调用带日志记录的大模型函数
        task_id=task_id,  # 传入任务 ID，用来写入 llm_calls.task_id
        step_id=step_id,  # 传入步骤 ID，用来写入 llm_calls.step_id
        prompt=prompt,  # 传入 prompt 字符串，函数内部会自动包装成 ai_messages
        model_name="default",  # 记录模型名称，这里先用 default，实际模型由 ai_service.py 的 settings 控制
        prompt_name="generate_agent_answer_prompt",  # 记录 prompt 名称，方便后续 bad case 追踪
        prompt_version="v1",  # 记录 prompt 版本，方便后续 prompt 版本管理
    )  # 大模型调用结束，并自动写入 llm_calls 日志

    return answer  # 返回模型回答文本
