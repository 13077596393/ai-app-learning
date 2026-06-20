import logging  # 导入 logging 模块，用来记录服务运行日志

from openai import OpenAI  # 导入 OpenAI 客户端，用来调用大模型接口

from settings import settings  # 导入项目统一配置对象，用来读取 LLM 配置

logger = logging.getLogger(
    __name__
)  # 创建当前模块的 logger，方便记录 ai_service 里的错误

client = OpenAI(  # 创建大模型 API 客户端
    api_key=settings.llm_api_key,  # 设置 API Key
    base_url=settings.llm_base_url,  # 设置大模型服务地址
    timeout=settings.llm_timeout,  # 设置请求超时时间
)  # 结束客户端初始化


def build_ai_messages(history_messages: list) -> list[dict]:  # 定义把数据库消息转换为模型消息格式的函数
    ai_messages = []  # 初始化发送给大模型的消息列表

    for message in history_messages:  # 遍历历史聊天消息
        ai_message = {  # 构造单条符合 OpenAI 消息格式的数据
            "role": message.role,  # 设置消息角色
            "content": message.content,  # 设置消息内容
        }  # 结束单条消息字典构造

        ai_messages.append(ai_message)  # 把转换后的消息加入模型消息列表

    return ai_messages  # 返回转换完成的模型消息列表

def call_llm_api(ai_messages: list[dict]) -> str:  # 定义普通非流式大模型调用函数
    try:  # 尝试调用大模型接口
        response = client.chat.completions.create(  # 发起聊天补全请求
            model=settings.llm_model_name,  # 指定大模型名称
            messages=ai_messages,  # 传入整理后的上下文消息
            temperature=settings.llm_temperature,  # 设置模型回复随机性
        )  # 结束聊天补全请求

        reply = response.choices[0].message.content  # 读取第一条候选回复内容

        if reply is None:  # 判断模型是否没有返回文本内容
            return "模型没有返回有效内容，请稍后再试。"  # 返回模型空内容的提示语

        return reply  # 返回模型回复文本

    except Exception:  # 捕获调用大模型过程中的异常
        logger.exception("调用大模型 API 失败")  # 记录完整异常日志，包括错误堆栈 traceback

        return "AI 服务暂时不可用，请稍后再试。"  # 返回给前端的兜底提示，不暴露内部错误


def stream_llm_api(ai_message: list[dict]):  # 定义流式大模型调用生成器函数
    try:  # 尝试发起流式请求
        stream = client.chat.completions.create(  # 调用聊天补全接口并获取流式响应
            model=settings.llm_model_name,  # 指定大模型名称
            messages=ai_message,  # 传入整理后的上下文消息
            temperature=settings.llm_temperature,  # 设置模型回复随机性
            stream=True,  # 开启流式返回
        )  # 结束流式请求创建
        for chunk in stream:  # 逐个读取模型返回的流式片段
            content = chunk.choices[0].delta.content  # 提取当前片段中的增量文本
            if content is None:  # 判断当前片段是否没有文本内容
                continue  # 跳过空片段继续等待后续内容
            yield content  # 向调用方产出当前文本片段
    except Exception:  # 捕获流式调用大模型过程中的异常
        logger.exception("流式调用大模型 API 失败")  # 记录完整异常日志，方便后端排查

        yield "AI 服务暂时不可用，请稍后再试。"  # 流式返回兜底提示


def generate_ai_reply(ai_messages: list[dict]) -> str:  # 定义生成助手回复的统一入口函数
    reply = call_llm_api(ai_messages)  # 调用普通大模型接口生成回复

    return reply  # 返回最终助手回复内容
