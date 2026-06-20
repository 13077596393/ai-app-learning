from sqlalchemy import (
    text,
)  # 导入 text，用来执行原生 SQL，让 PostgreSQL 使用 pgvector 做向量排序
from sqlmodel import Session  # 导入 Session，用来操作数据库


from services.embedding_service import (
    generate_embedding,
)  # 导入 generate_embedding，用来把用户问题转换成真实 embedding 向量
from services.rag_service import (
    clean_content_for_display,
    keyword_boost,
)  # 导入内容清理函数和关键词加分函数
from services.rerank_service import (  # 从 Rerank 服务中导入精排和去重函数
    deduplicate_chunks,  # 导入引用去重函数，用来去掉重复或来源过于集中的 chunks
    rerank_chunks,  # 导入批量精排函数，用来给检索结果补 rerank_score 并重新排序
)  # 结束 Rerank 服务函数导入

VECTOR_SCORE_WEIGHT = (
    0.7  # 定义向量相似度权重，真实 embedding 接入后让语义相关性占主要部分
)

KEYWORD_SCORE_WEIGHT = 0.3  # 定义关键词分数权重，让关键词命中作为辅助排序因素

MAX_KEYWORD_SCORE = 2.0  # 定义关键词分数上限，避免关键词加分过大压过向量相似度

QUERY_EXPANSION_KEYWORDS = (
    {  # 定义查询扩展关键词字典，用来把用户短问题补充成更适合检索的问题
        "报销": [
            "报销流程",
            "报销材料",
            "发票要求",
            "审批流程",
        ],  # 如果问题里出现“报销”，就补充报销相关检索词
        "离职": [
            "辞职",
            "提前通知",
            "试用期离职",
            "正式员工离职",
        ],  # 如果问题里出现“离职”，就补充离职相关检索词
        "辞职": [
            "离职",
            "提前通知",
            "离职流程",
        ],  # 如果问题里出现“辞职”，就补充制度文档里更常见的“离职”等词
        "年假": [
            "年假规则",
            "年假结转",
            "休假天数",
        ],  # 如果问题里出现“年假”，就补充年假制度相关词
        "试用期": [
            "试用期员工",
            "试用期离职",
            "提前几天",
        ],  # 如果问题里出现“试用期”，就补充试用期相关检索词
        "合同": [
            "合同编号",
            "付款周期",
            "签署日期",
        ],  # 如果问题里出现“合同”，就补充合同检索常见关键词
        "付款": [
            "付款周期",
            "付款方式",
            "合同编号",
        ],  # 如果问题里出现“付款”，就补充付款相关检索词
    }
)  # 结束查询扩展关键词字典定义


def rewrite_query_for_search(  # 定义轻量版查询改写函数
    question: str,  # 用户原始问题
) -> str:  # 返回改写后的检索问题
    cleaned_question = question.strip()  # 去掉问题前后的空白字符，避免空格影响检索

    if not cleaned_question:  # 判断问题是否为空
        return ""  # 如果问题为空，直接返回空字符串

    expansion_terms: list[str] = (
        []
    )  # 创建扩展词列表，用来保存需要追加到问题后面的检索词

    for (
        trigger_word,
        related_terms,
    ) in QUERY_EXPANSION_KEYWORDS.items():  # 遍历每一个触发词和它对应的扩展词
        if trigger_word in cleaned_question:  # 如果用户问题里包含当前触发词
            for related_term in related_terms:  # 遍历当前触发词对应的所有扩展词
                if (
                    related_term not in cleaned_question
                    and related_term not in expansion_terms
                ):  # 避免重复追加已经存在的词
                    expansion_terms.append(related_term)  # 把新的扩展词加入扩展词列表

    if not expansion_terms:  # 如果没有任何扩展词
        return cleaned_question  # 说明问题不需要改写，直接返回原问题

    rewritten_query = (  # 拼接最终检索问题
        cleaned_question
        + " "
        + " ".join(expansion_terms)  # 保留原问题，并把扩展词追加到后面
    )  # 得到改写后的检索问题

    return rewritten_query  # 返回最终用于检索的改写问题


def calculate_hybrid_score(  # 定义计算混合检索综合分数的函数
    vector_score: float,  # 向量相似度分数，表示语义上和用户问题像不像
    keyword_score: float,  # 关键词命中分数，表示用户问题里的关键词命中了多少
) -> float:  # 返回一个 float 类型的综合分数
    hybrid_score = (  # 使用加权方式计算混合检索综合分数
        vector_score
        * VECTOR_SCORE_WEIGHT  # 向量分数乘以向量权重，让语义相似度占主要部分
        + keyword_score
        * KEYWORD_SCORE_WEIGHT  # 关键词分数乘以关键词权重，让精确命中作为辅助因素
    )  # 结束综合分数计算

    return hybrid_score  # 返回最终 hybrid_score，后续排序和过滤都可以用它


def embedding_to_pgvector_text(
    embedding: list[float],
) -> str:  # 定义把 Python embedding 列表转换成 pgvector 字符串的函数
    vector_text = (
        "[" + ",".join(str(value) for value in embedding) + "]"
    )  # 把 [0.1, -0.2] 转成 "[0.1,-0.2]" 格式

    return vector_text  # 返回 pgvector 可以识别的向量字符串


def search_top_chunks(  # 定义 top-k 检索函数，用 pgvector + 关键词分数从指定知识库中找最相关的 chunks
    session: Session,  # 数据库会话对象，用来执行 SQL 查询
    knowledge_base_id: int,  # 要检索的知识库 ID，保证只在当前知识库范围内搜索
    question: str,  # 用户问题，或者经过历史增强后的检索问题
    top_k: int = 3,  # 最终返回最相关的前几个 chunks，默认返回 3 个
    min_score: (
        float | None
    ) = None,  # 最低相关度分数，如果传入该值，则过滤掉 hybrid_score 低于该值的结果
    document_id: (
        int | None
    ) = None,  # 可选过滤条件：如果传入，只检索指定 document_id 对应文档的 chunks
    file_type: (
        str | None
    ) = None,  # 可选过滤条件：如果传入，只检索指定文件类型的文档，例如 txt、md、html
    document_status: (
        str | None
    ) = None,  # 可选过滤条件：如果传入，只检索指定状态的文档，例如 indexed
    filename_keyword: (
        str | None
    ) = None,  # 可选过滤条件：如果传入，只检索文件名包含该关键词的文档
) -> list[dict]:  # 返回字典列表，每个字典表示一个检索命中的 chunk

    cleaned_question = question.strip()  # 去掉用户原始问题前后的空白字符，避免空格影响后续处理

    search_question = rewrite_query_for_search(  # 调用查询改写函数，把用户问题改写成更适合检索的版本
        cleaned_question  # 传入清洗后的用户问题
    )  # 得到最终用于向量检索和关键词检索的问题
    if not cleaned_question:  # 判断问题是否为空
        return []  # 如果问题为空，直接返回空列表

    if top_k <= 0:  # 判断 top_k 是否不合法
        return []  # 如果 top_k 小于等于 0，直接返回空列表

    question_embedding = generate_embedding(
        search_question  # 使用改写后的检索问题，而不是只使用用户原始问题
    )  # 调用真实 embedding 服务，把检索问题转换成 1024 维向量

    query_vector_text = embedding_to_pgvector_text(
        question_embedding
    )  # 把 Python list[float] 转成 pgvector 可识别的字符串

    candidate_limit = max(
        top_k * 5, 20
    )  # 先从数据库取一批候选结果，后面再结合关键词分重新排序
    filename_keyword_value = (  # 构造文件名模糊搜索值
        f"%{filename_keyword.strip()}%"  # 如果传入 filename_keyword，就在前后加 %，用于 SQL ILIKE 模糊匹配
        if filename_keyword
        and filename_keyword.strip()  # 判断 filename_keyword 是否存在并且不是空字符串
        else None  # 如果没有传入文件名关键词，就设置为 None，表示不过滤文件名
    )  # 结束 filename_keyword_value 构造
    search_statement = text(  # 构建原生 SQL，用 pgvector 查询当前知识库里和问题最相似的候选 chunks
        """
    SELECT
        candidate_chunks.chunk_id AS chunk_id,
        candidate_chunks.document_id AS document_id,
        candidate_chunks.document_name AS document_name,
        candidate_chunks.chunk_index AS chunk_index,
        candidate_chunks.content AS content,
        candidate_chunks.vector_distance AS vector_distance
    FROM (
        SELECT
            dc.id AS chunk_id,
            dc.document_id AS document_id,
            d.filename AS document_name,
            dc.chunk_index AS chunk_index,
            dc.content AS content,
            dc.embedding_vector <=> CAST(:query_vector AS vector) AS vector_distance
        FROM document_chunks AS dc
        JOIN documents AS d ON d.id = dc.document_id
        WHERE d.knowledge_base_id = :knowledge_base_id
            AND dc.embedding_vector IS NOT NULL
            AND (:document_id IS NULL OR d.id = :document_id)
            AND (:file_type IS NULL OR d.file_type = :file_type)
            AND (:document_status IS NULL OR d.status = :document_status)
            AND (:filename_keyword IS NULL OR d.filename ILIKE :filename_keyword)
    ) AS candidate_chunks
    ORDER BY candidate_chunks.vector_distance ASC
    LIMIT :candidate_limit
    """
    )  # 结束 SQL 构建

    rows = (
        session.execute(  # 执行 SQL 查询，得到 pgvector 排序后的候选 chunks
            search_statement,  # 传入 SQL 语句
            {
                "query_vector": query_vector_text,  # 传入用户问题向量，格式是 "[0.1,-0.2,...]"
                "knowledge_base_id": knowledge_base_id,  # 传入当前知识库 ID，确保只在当前知识库中检索
                "candidate_limit": candidate_limit,  # 传入候选结果数量
                "document_id": document_id,  # 传入可选文档 ID，如果为 None，则不过滤具体文档
                "file_type": file_type,  # 传入可选文件类型，如果为 None，则不过滤文件类型
                "document_status": document_status,  # 传入可选文档状态，如果为 None，则不过滤状态
                "filename_keyword": filename_keyword_value,  # 传入可选文件名模糊匹配值，如果为 None，则不过滤文件名
            },
        )
        .mappings()
        .all()
    )  # 把每一行结果转成类似字典的结构，并取出全部结果

    filtered_results: list[dict] = []  # 创建列表，用来保存带分数的检索结果

    for row in rows:  # 遍历数据库返回的每一个候选 chunk
        vector_distance = float(
            row["vector_distance"]
        )  # 取出 pgvector 计算出的余弦距离，距离越小越相似

        vector_score = 1 - vector_distance  # 把余弦距离转换成相似度分数，分数越大越相似

        content = row["content"] or ""  # 取出 chunk 内容，如果为空就使用空字符串

        keyword_score = keyword_boost(  # 计算关键词命中分数
            search_question,  # 使用改写后的检索问题，这样扩展词也能参与关键词匹配
            content,  # 当前 chunk 正文内容
        )  # 得到当前 chunk 的关键词分数

        limited_keyword_score = min(  # 对关键词分数做上限限制，避免关键词分数过大
            keyword_score,  # 原始关键词分数
            MAX_KEYWORD_SCORE,  # 关键词分数最大值
        )  # 结束关键词分数限制

        hybrid_score = (
            calculate_hybrid_score(  # 调用统一的混合分数计算函数，避免到处手写加权公式
                vector_score=vector_score,  # 传入当前 chunk 的向量相似度分数
                keyword_score=limited_keyword_score,  # 传入当前 chunk 的关键词命中分数
            )
        )  # 得到当前 chunk 的 hybrid_score

        result = {  # 创建当前 chunk 的检索结果字典
            "chunk_id": row["chunk_id"],  # 保存当前 chunk ID
            "document_id": row["document_id"],  # 保存当前 chunk 所属文档 ID
            "document_name": row["document_name"],  # 保存当前 chunk 所属文档名称
            "chunk_index": row["chunk_index"],  # 保存当前 chunk 在文档中的序号
            "content": clean_content_for_display(
                content
            ),  # 清理 chunk 内容，方便前端展示
            "vector_score": vector_score,  # 保存向量相似度分数，越大越相似
            "keyword_score": limited_keyword_score,  # 保存关键词加分
            "hybrid_score": hybrid_score,  # 保存混合检索综合分数，后续主要用它解释检索排序原因
            "final_score": hybrid_score,  # 保留旧字段，避免之前依赖 final_score 的接口或前端突然报错
            "original_question": cleaned_question,  # 用户原始问题
            "search_question": search_question,  # 改写后的检索问题
        }  # 结束 result 字典创建

        filtered_results.append(result)  # 把当前结果添加到结果列表中

    if min_score is not None:  # 判断是否传入了最低相关度分数
        filtered_results = [  # 使用列表推导式创建过滤后的结果列表
            result  # 保留当前检索结果
            for result in filtered_results  # 遍历所有已经计算好分数的检索结果
            if result["hybrid_score"] >= min_score  # 只保留 hybrid_score 大于等于最低分数的结果
        ]  # 结束低分结果过滤

    filtered_results.sort(  # 先按 hybrid_score 对候选结果做一次初步排序
        key=lambda item: item["hybrid_score"],  # 使用 hybrid_score 作为初筛排序依据
        reverse=True,  # 降序排序，分数越高越靠前
    )

    reranked_results = rerank_chunks(  # 调用 Rerank 服务，对候选 chunks 做二次精排
        question=cleaned_question,  # 传入用户原始问题，用来判断 chunk 是否真正适合回答问题
        chunks=filtered_results,  # 传入 Hybrid Search 得到的候选结果
    )
    deduplicated_results = deduplicate_chunks(  # 调用引用去重函数，去掉重复或来源过于集中的 chunks
        chunks=reranked_results,  # 传入已经 rerank 排序后的结果，确保优先保留高分 chunk
    )  # 得到去重后的高质量候选结果

    return deduplicated_results[:top_k]  # 返回 rerank 后排名最高的前 top_k 条结果


# 清理问题
# → 校验 question 和 top_k
# → 生成问题 embedding
# → embedding 转 pgvector 字符串
# → SQL 查询当前知识库下最相似的候选 chunks
# → pgvector 按 vector_distance 排序
# → Python 遍历候选结果
# → vector_distance 转 vector_score
# → 计算 keyword_score
# → 限制关键词分数上限
# → 计算 final_score
# → 低于 min_score 的结果过滤掉
# → 按 final_score 重新排序
# → 返回前 top_k 条
