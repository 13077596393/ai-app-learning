from redis import Redis  # 从 redis 库导入 Redis 客户端类，用来连接 Redis 服务

from rq import Queue  # 从 rq 库导入 Queue 类，用来创建任务队列

from settings import settings  # 导入项目统一配置对象，用来读取 .env 里的 Redis 配置

redis_connection = Redis.from_url(  # 根据 Redis URL 创建 Redis 连接对象
    settings.redis_url,  # 从 settings 中读取 Redis 连接地址，对应 .env 里的 REDIS_URL
    decode_responses=False,  # RQ 内部需要处理二进制数据，所以这里必须保持 False
)  # Redis 连接对象创建结束


agent_task_queue = Queue(  # 创建 RQ 队列对象
    "agent_tasks",  # 队列名称叫 agent_tasks，后面 Agent 后台任务也会用这个队列
    connection=redis_connection,  # 指定这个队列使用上面创建的 Redis 连接
)  # RQ 队列对象创建结束
