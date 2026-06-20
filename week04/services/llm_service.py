from openai import (
    OpenAI,
)  # 导入 OpenAI 客户端，用来调用 DeepSeek / OpenAI 兼容的大模型接口

from settings import settings  # 导入项目统一配置对象，用来读取 .env 里的 LLM 配置
import logging  # 导入 logging 模块，用来记录 LLM 服务日志
logger = logging.getLogger(__name__)  # 创建当前模块 logger

def get_llm_client() -> OpenAI:  # 定义创建 LLM 客户端的函数，返回 OpenAI 客户端对象
    if not settings.llm_api_key:  # 判断是否缺少 LLM API Key
        raise ValueError(  # 主动抛出配置错误
            "缺少 LLM_API_KEY 配置，请检查 .env 文件"  # 提示开发者检查 .env
        )  # ValueError 结束

    if not settings.llm_base_url:  # 判断是否缺少 LLM 接口地址
        raise ValueError(  # 主动抛出配置错误
            "缺少 LLM_BASE_URL 配置，请检查 .env 文件"  # 提示开发者检查 .env
        )  # ValueError 结束

    client = OpenAI(  # 创建 OpenAI 兼容客户端
        api_key=settings.llm_api_key,  # 从 settings 读取 LLM API Key
        base_url=settings.llm_base_url,  # 从 settings 读取 LLM 接口地址
        timeout=settings.llm_timeout,  # 从 settings 读取 LLM 请求超时时间
    )  # OpenAI 客户端创建结束

    return client  # 返回创建好的 LLM 客户端


def get_llm_model_name() -> str:  # 定义获取 LLM 模型名称的函数
    return settings.llm_model_name  # 从 settings 读取模型名称，例如 deepseek-chat


def get_llm_temperature() -> float:  # 定义获取模型温度参数的函数
    return settings.llm_temperature  # 从 settings 读取温度参数


def call_llm_with_prompt(  # 定义调用 LLM 的函数
    prompt: str,  # 接收完整 prompt
) -> str:  # 返回模型生成的文本
    cleaned_prompt = prompt.strip()  # 去掉 prompt 前后空白

    if not cleaned_prompt:  # 判断 prompt 是否为空
        raise ValueError("prompt 不能为空")  # prompt 为空属于调用方错误，直接抛出

    try:  # 尝试调用大模型
        client = get_llm_client()  # 创建 LLM 客户端

        response = client.chat.completions.create(  # 调用聊天补全接口
            model=get_llm_model_name(),  # 从 settings 获取模型名称
            messages=[  # 构造消息列表
                {  # system 消息
                    "role": "system",  # 设置角色为 system
                    "content": "你是一个严谨的企业知识库问答助手。",  # 设置助手身份
                },  # system 消息结束
                {  # user 消息
                    "role": "user",  # 设置角色为 user
                    "content": cleaned_prompt,  # 传入用户 prompt
                },  # user 消息结束
            ],  # 消息列表结束
            temperature=get_llm_temperature(),  # 从 settings 获取温度参数
        )  # LLM 调用结束

        answer = response.choices[0].message.content  # 取出模型回答

        if answer is None:  # 如果模型返回为空
            return ""  # 返回空字符串，避免 None 影响后续逻辑

        return answer.strip()  # 返回清理后的答案

    except Exception:  # 捕获调用 LLM 过程中的异常
        logger.exception("call_llm_with_prompt 调用大模型失败")  # 记录完整异常日志

        return "AI 服务暂时不可用，请稍后再试。"  # 返回统一兜底提示
