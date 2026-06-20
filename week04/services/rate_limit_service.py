from fastapi import HTTPException  # 导入 HTTPException，用来在请求太频繁时返回 429 错误

from services.rq_queue import (
    redis_connection,
)  # 复用 RQ 队列里的 Redis 连接，避免重复创建 Redis 客户端
from settings import settings  # 导入统一配置对象，用来读取限流窗口和最大请求次数


def build_rate_limit_key(  # 定义生成限流 Redis key 的函数
    user_id: int,  # 当前登录用户 ID
    action: str,  # 接口动作名称，例如 chat_message、rag_chat、agent_task
) -> str:  # 返回 Redis key 字符串
    return f"rate_limit:{action}:user:{user_id}"  # 拼接限流 key，确保不同用户、不同动作互不影响


def get_max_requests_by_action(  # 定义根据接口动作获取最大请求次数的函数
    action: str,  # 接口动作名称
) -> int:  # 返回该动作在一个时间窗口内允许的最大请求次数
    if action == "chat_message":  # 如果是普通聊天接口
        return settings.rate_limit_chat_max_requests  # 返回聊天接口限流次数

    if action == "rag_chat":  # 如果是 RAG 问答接口
        return settings.rate_limit_rag_max_requests  # 返回 RAG 接口限流次数

    if action == "agent_task":  # 如果是 Agent 后台任务接口
        return settings.rate_limit_agent_max_requests  # 返回 Agent 接口限流次数

    return settings.rate_limit_chat_max_requests  # 如果动作未知，默认使用聊天接口的限制


def check_rate_limit(  # 定义限流检查函数，接口请求开始时调用它
    user_id: int | None,  # 当前登录用户 ID，可能为空，所以这里做保护
    action: str,  # 接口动作名称，例如 chat_message、rag_chat、agent_task
) -> None:  # 没有超过限制就不返回内容，超过限制直接抛出 HTTPException
    if user_id is None:  # 如果当前用户没有有效 ID
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=400,  # 400 表示当前用户状态不合法
            detail="当前用户没有有效 ID，无法进行限流判断",  # 返回错误提示
        )  # HTTPException 结束

    key = build_rate_limit_key(  # 生成 Redis 限流 key
        user_id=user_id,  # 传入当前用户 ID
        action=action,  # 传入接口动作名称
    )  # key 生成结束

    current_count = redis_connection.incr(
        key
    )  # Redis 计数加 1，并返回加 1 后的当前次数

    if current_count == 1:  # 如果这是当前时间窗口内第一次请求
        redis_connection.expire(  # 给 Redis key 设置过期时间
            key,  # 要设置过期时间的 key
            settings.rate_limit_window_seconds,  # 从 settings 读取限流窗口秒数
        )  # 过期时间设置结束

    max_requests = get_max_requests_by_action(  # 获取当前动作允许的最大请求次数
        action=action,  # 传入接口动作名称
    )  # 最大请求次数获取结束

    if current_count > max_requests:  # 如果当前请求次数超过最大限制
        ttl = redis_connection.ttl(key)  # 获取该限流 key 还剩多少秒过期

        retry_after = (
            ttl if ttl > 0 else settings.rate_limit_window_seconds
        )  # 如果 ttl 有效就用 ttl，否则使用默认窗口时间

        raise HTTPException(  # 抛出 HTTP 错误，阻止继续调用大模型
            status_code=429,  # 429 表示 Too Many Requests，请求太频繁
            detail=f"请求太频繁，请 {retry_after} 秒后再试",  # 返回给前端的提示
        )  # HTTPException 结束
