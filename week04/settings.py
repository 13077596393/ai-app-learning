from pydantic_settings import (  # 从 pydantic_settings 导入配置相关工具
    BaseSettings,  # BaseSettings 用来定义从环境变量读取的配置类
    SettingsConfigDict,  # SettingsConfigDict 用来配置 .env 文件读取规则
)  # 导入结束


class Settings(BaseSettings):  # 定义项目运行时配置类
    database_url: str  # 数据库连接地址，对应 .env 里的 DATABASE_URL

    llm_api_key: str  # 大模型 API Key，对应 .env 里的 LLM_API_KEY
    llm_base_url: str  # 大模型服务地址，对应 .env 里的 LLM_BASE_URL
    llm_model_name: str  # 大模型名称，对应 .env 里的 LLM_MODEL_NAME
    llm_timeout: int = 30  # 大模型请求超时时间默认 30 秒
    llm_temperature: float = 0.7  # 大模型回复随机性默认 0.7

    embedding_api_key: str  # Embedding API Key，对应 .env 里的 EMBEDDING_API_KEY
    embedding_base_url: str = (
        "https://dashscope.aliyuncs.com/compatible-mode/v1"  # Embedding 接口地址
    )
    embedding_model_name: str = "text-embedding-v3"  # Embedding 模型名称
    embedding_timeout: int = 30  # Embedding 请求超时时间默认 30 秒

    jwt_secret_key: str  # JWT 签名密钥，对应 .env 里的 JWT_SECRET_KEY
    jwt_algorithm: str = "HS256"  # JWT 签名算法，默认 HS256
    jwt_expire_minutes: int = 1440  # JWT 过期分钟数，默认 1 天

    redis_url: str = "redis://localhost:6379/0"  # Redis 连接地址，默认本地 Redis

    max_upload_file_size_mb: int = 10  # 上传文件最大大小，单位 MB，默认限制为 10MB

    rate_limit_window_seconds: int = 60  # 限流时间窗口，单位秒，默认 60 秒
    rate_limit_chat_max_requests: int = 20  # 聊天接口在一个限流窗口内允许的最大请求次数
    rate_limit_rag_max_requests: int = (
        10  # RAG 问答接口在一个限流窗口内允许的最大请求次数
    )
    rate_limit_agent_max_requests: int = (
        5  # Agent 后台任务接口在一个限流窗口内允许的最大请求次数
    )

    model_config = SettingsConfigDict(  # 配置 Settings 如何读取环境变量文件
        env_file=".env",  # 指定从项目根目录的 .env 文件读取配置
        env_file_encoding="utf-8",  # 指定 .env 文件编码为 UTF-8
        extra="ignore",  # 忽略 .env 中未声明的额外字段
    )  # 配置字典结束


settings = Settings()  # 实例化全局配置对象，其他模块统一导入 settings 使用
