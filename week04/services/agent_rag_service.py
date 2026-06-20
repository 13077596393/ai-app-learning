from typing import Any  # 导入 Any，用来兼容字典、对象等不同类型

from sqlmodel import Session  # 导入 SQLModel 的 Session，用来创建数据库会话

from database import engine  # 导入数据库 engine，用来创建真正的数据库 Session

from services.retrieval_service import (
    search_top_chunks,
)  # 导入真实知识库 top-k 检索函数


def get_value(
    obj: Any,  # 接收任意对象，可能是 dict，也可能是 SQLModel 对象
    key: str,  # 接收要读取的字段名
    default: Any = None,  # 接收默认值，如果字段不存在就返回它
) -> Any:  # 返回读取到的字段值
    if isinstance(obj, dict):  # 判断当前对象是否是字典
        return obj.get(key, default)  # 如果是字典，就用 get 读取字段

    return getattr(obj, key, default)  # 如果不是字典，就当对象属性读取


def search_knowledge_base_for_agent(  # 定义给 Agent 使用的真实知识库检索函数
    knowledge_base_id: int | None,  # 接收知识库 ID，可以为空
    question: str,  # 接收用户问题
    top_k: int = 5,  # 默认返回前 5 个相关片段
) -> dict[str, Any]:  # 返回 Agent 需要的 context 和 citations
    if knowledge_base_id is None:  # 判断是否没有传知识库 ID
        return {  # 返回空检索结果
            "context": "",  # 没有上下文
            "citations": [],  # 没有引用来源
        }  # 返回结束

    question = question.strip()  # 去掉用户问题前后的空格

    if not question:  # 判断用户问题是否为空
        return {  # 返回空检索结果
            "context": "",  # 没有上下文
            "citations": [],  # 没有引用来源
        }  # 返回结束

    safe_top_k = max(1, min(top_k, 20))  # 限制 top_k 范围，最少 1，最多 20

    with Session(engine) as session:  # 创建真正的数据库会话，不能用 Depends
        search_results = search_top_chunks(  # 调用真实知识库检索函数
            session=session,  # 传入真实数据库 Session
            knowledge_base_id=knowledge_base_id,  # 传入知识库 ID
            question=question,  # 传入用户问题，注意这里叫 question
            top_k=safe_top_k,  # 传入检索数量
        )  # 检索调用结束

    context_parts: list[str] = []  # 创建上下文片段列表，用来拼接给大模型看的 context

    citations: list[dict[str, Any]] = []  # 创建引用列表，用来保存结构化引用来源

    for index, item in enumerate(  # 遍历真实检索结果
        search_results,  # 使用 search_top_chunks 返回的真实 chunk 结果
        start=1,  # 引用编号从 1 开始
    ):  # 遍历开始
        chunk_id = get_value(item, "chunk_id", None)  # 读取 chunk ID

        document_id = get_value(item, "document_id", None)  # 读取文档 ID

        document_name = get_value(  # 读取文档名称
            item,  # 当前检索结果
            "document_name",  # search_top_chunks 返回的是 document_name
            None,  # 默认值
        )  # 读取结束

        source = get_value(item, "source", None)  # 尝试读取 source 字段

        if source is None:  # 如果没有 source
            source = document_name  # 就使用 document_name 作为来源名称

        if source is None:  # 如果 document_name 也没有
            source = (
                f"document_{document_id}" if document_id else "unknown"
            )  # 生成兜底来源名

        content = get_value(item, "content", "")  # 读取 chunk 正文内容

        final_score = get_value(item, "final_score", None)  # 读取最终相关度分数

        vector_score = get_value(item, "vector_score", None)  # 读取向量相似度分数

        keyword_score = get_value(item, "keyword_score", None)  # 读取关键词加分

        context_parts.append(  # 把当前 chunk 拼接成大模型可读的上下文
            f"[引用{index}] 来源：{source}\n{content}"  # 包含引用编号、来源和正文
        )  # 上下文追加结束

        citations.append(  # 往 citations 里追加一条引用记录
            {  # 构造引用字典
                "source_index": index,  # 保存引用编号
                "document_id": document_id,  # 保存文档 ID
                "chunk_id": chunk_id,  # 保存 chunk ID
                "source": source,  # 保存来源文档名称
                "content": content,  # 保存 chunk 正文
                "preview": content[:200],  # 保存前 200 字预览
                "final_score": final_score,  # 保存最终相关度分数
                "vector_score": vector_score,  # 保存向量相似度分数
                "keyword_score": keyword_score,  # 保存关键词加分
            }  # 引用字典结束
        )  # citations 追加结束

    context = "\n\n".join(context_parts)  # 把多个 chunk 用两个换行拼成完整上下文

    return {  # 返回 Agent 节点需要的检索结果
        "context": context,  # 返回真实知识库上下文
        "citations": citations,  # 返回真实引用来源
    }  # 返回结束
