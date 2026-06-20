from openai import OpenAI  # 导入 OpenAI 客户端，用来调用 OpenAI 兼容 API

from settings import settings  # 导入项目统一配置对象，用来读取 .env 里的 embedding 配置


def get_embedding_client() -> (
    OpenAI
):  # 定义创建 embedding 客户端的函数，返回 OpenAI 客户端对象
    if not settings.embedding_api_key:  # 判断是否缺少 embedding API Key
        raise ValueError(
            "缺少 EMBEDDING_API_KEY 配置"
        )  # 如果没有配置 API Key，就主动抛出错误

    if not settings.embedding_base_url:  # 判断是否缺少 embedding 接口地址
        raise ValueError(
            "缺少 EMBEDDING_BASE_URL 配置"
        )  # 如果没有配置接口地址，就主动抛出错误

    client = OpenAI(  # 创建 OpenAI 客户端，用来调用 embeddings.create 接口
        api_key=settings.embedding_api_key,  # 设置 embedding API Key
        base_url=settings.embedding_base_url,  # 设置 embedding 接口地址
        timeout=settings.embedding_timeout,  # 设置请求超时时间
    )  # 结束 OpenAI 客户端创建

    return client  # 返回创建好的 embedding 客户端


def generate_embedding(
    text: str,
) -> list[float]:  # 定义生成文本 embedding 的函数，输入文本，返回浮点数向量列表
    cleaned_text = text.strip()  # 去掉文本前后的空白字符，避免传入无意义空白

    if not cleaned_text:  # 判断文本是否为空
        raise ValueError("生成 embedding 的文本不能为空")  # 如果文本为空，主动抛出错误

    client = get_embedding_client()  # 创建 embedding 客户端

    response = client.embeddings.create(  # 调用 OpenAI embeddings API，把文本转成向量
        model=settings.embedding_model_name,  # 指定 embedding 模型，例如 text-embedding-3-small
        input=cleaned_text,  # 传入要向量化的文本内容
        encoding_format="float",  # 指定返回 float 格式的向量
    )  # 结束 embeddings API 调用

    embedding = response.data[0].embedding  # 从响应结果中取出第一条 embedding 向量

    return list(embedding)  # 把 embedding 转成普通 Python list[float] 后返回


