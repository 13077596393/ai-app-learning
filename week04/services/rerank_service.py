# clamp_score()
#    ↓
# 保证分数在 0 到 1 之间

# calculate_rerank_score()
#    ↓
# 给单个 chunk 计算 rerank_score

# rerank_chunks()
#    ↓
# 给一批 chunks 补 rerank_score 并排序

# deduplicate_chunks()
#    ↓
# 对 rerank 后的 chunks 做引用去重

from typing import Any  # 导入 Any 类型，用来表示 chunk 字典里可以包含各种类型的值

MIN_CONTENT_LENGTH = 20  # 定义 chunk 最小有效长度，太短的内容通常信息量不足

MAX_CONTENT_LENGTH = 1200  # 定义 chunk 最大推荐长度，太长的内容可能包含太多无关信息

CONTENT_LENGTH_BONUS = 0.05  # 定义内容长度合理时的加分，鼓励信息量适中的 chunk

CONTENT_TOO_SHORT_PENALTY = 0.08  # 定义内容太短时的扣分，避免无信息量片段排太前

CONTENT_TOO_LONG_PENALTY = 0.05  # 定义内容太长时的扣分，避免过长片段干扰上下文

ANSWER_KEYWORD_BONUS = (
    0.08  # 定义命中答案型关键词时的加分，鼓励更可能直接回答问题的 chunk
)

MAX_RERANK_SCORE = 1.0  # 定义 rerank_score 最大值，避免分数超过 1

MIN_RERANK_SCORE = 0.0  # 定义 rerank_score 最小值，避免分数小于 0
ANSWER_KEYWORDS = [  # 定义答案型关键词列表，用来判断 chunk 是否更像能直接回答问题的片段
    "提前",  # 常用于离职、通知类问题
    "天",  # 常用于时间、期限类问题
    "流程",  # 常用于流程说明类问题
    "审批",  # 常用于审批制度类问题
    "周期",  # 常用于付款周期、处理周期类问题
    "方式",  # 常用于付款方式、提交方式类问题
    "要求",  # 常用于规则要求类问题
    "规则",  # 常用于制度规则类问题
    "条件",  # 常用于申请条件、使用条件类问题
    "材料",  # 常用于报销材料、申请材料类问题
]  # 结束答案型关键词列表定义

CONTENT_FINGERPRINT_LENGTH = (
    80  # 定义内容指纹长度，用 chunk 内容前 80 个字符判断简单重复
)

MAX_CHUNKS_PER_DOCUMENT = 2  # 定义同一个文档最多保留 2 个 chunk，避免同一文档占满上下文

SCORE_FIELD_PRIORITY = [  # 定义结果分数字段的优先级列表
    "rerank_score",  # 第一优先级：使用 Rerank 精排后的分数
    "hybrid_score",  # 第二优先级：使用 Hybrid Search 综合分数
    "final_score",  # 第三优先级：兼容旧版本 final_score 字段
    "score",  # 第四优先级：兼容某些旧接口可能使用的 score 字段
]  # 结束分数字段优先级定义

def clamp_score(  # 定义分数裁剪函数，用来保证 rerank_score 在合理范围内
    score: float,  # 输入原始分数
) -> float:  # 返回裁剪后的分数
    if score < MIN_RERANK_SCORE:  # 如果分数小于最小值
        return MIN_RERANK_SCORE  # 返回最小分数，避免出现负数

    if score > MAX_RERANK_SCORE:  # 如果分数大于最大值
        return MAX_RERANK_SCORE  # 返回最大分数，避免超过 1

    return score  # 如果分数已经在合理范围内，就直接返回原分数


def get_result_score(  # 定义统一读取检索结果分数的函数
    result: dict[
        str, Any
    ],  # 输入单条检索结果，里面可能包含 rerank_score、hybrid_score、final_score 等字段
) -> float:  # 返回最终用于置信判断的分数
    for score_field in SCORE_FIELD_PRIORITY:  # 按照预设优先级依次检查分数字段
        score_value = result.get(score_field)  # 从当前结果中读取对应字段的值

        if score_value is None:  # 如果当前字段不存在，或者值是 None
            continue  # 跳过当前字段，继续检查下一个分数字段

        try:  # 尝试把分数转换成 float
            score = float(score_value)  # 把分数值转换成浮点数，兼容字符串形式的数字
        except (TypeError, ValueError):  # 如果分数无法转换成 float
            continue  # 跳过当前字段，继续检查下一个分数字段

        return clamp_score(score)  # 返回裁剪后的分数，保证分数在 0 到 1 之间

    return 0.0  # 如果所有分数字段都不存在或不可用，就返回 0 分


def calculate_rerank_score(  # 定义计算单个 chunk 精排分数的函数
    question: str,  # 用户原始问题，用来辅助判断当前 chunk 是否适合回答该问题
    chunk: dict[str, Any],  # 当前候选 chunk，通常来自 Hybrid Search 的检索结果
) -> float:  # 返回 rerank_score 精排分数
    content = str(  # 把 chunk 内容转换成字符串，避免 None 或其他类型导致后续处理报错
        chunk.get("content", "")  # 从 chunk 中读取 content 字段，如果没有就使用空字符串
    )  # 得到当前 chunk 的正文内容

    hybrid_score = float(  # 读取当前 chunk 的 hybrid_score，并转换成 float
        chunk.get(  # 从 chunk 字典中读取分数
            "hybrid_score",  # 优先读取新的 hybrid_score 字段
            chunk.get(
                "final_score", 0.0
            ),  # 如果没有 hybrid_score，就退回读取旧的 final_score
        )  # 得到基础分数
    )  # 转换成 float，避免字符串或 None 影响计算

    rerank_score = hybrid_score  # 先把 hybrid_score 作为 rerank_score 的基础分

    content_length = len(content)  # 计算当前 chunk 内容长度，用来判断信息量是否合适

    if content_length < MIN_CONTENT_LENGTH:  # 如果内容太短，说明信息量可能不足
        rerank_score -= CONTENT_TOO_SHORT_PENALTY  # 给太短的 chunk 扣分
    elif content_length > MAX_CONTENT_LENGTH:  # 如果内容太长，说明可能包含太多无关信息
        rerank_score -= CONTENT_TOO_LONG_PENALTY  # 给太长的 chunk 扣分
    else:  # 如果内容长度处于合理范围
        rerank_score += CONTENT_LENGTH_BONUS  # 给长度合适的 chunk 一点加分

    for keyword in ANSWER_KEYWORDS:  # 遍历答案型关键词列表
        if keyword in content:  # 如果当前 chunk 内容里包含答案型关键词
            rerank_score += ANSWER_KEYWORD_BONUS  # 给当前 chunk 加一点分
            break  # 命中一个答案型关键词就够了，避免重复加分过多

    return clamp_score(  # 返回裁剪后的 rerank_score
        rerank_score  # 传入计算完成的原始精排分数
    )  # 保证最终分数在 0 到 1 之间


def rerank_chunks(  # 定义批量精排函数，用来对一组候选 chunks 重新排序
    question: str,  # 用户原始问题，用来判断每个 chunk 是否真正适合回答该问题
    chunks: list[dict[str, Any]],  # Hybrid Search 返回的候选 chunk 列表
) -> list[dict[str, Any]]:  # 返回带 rerank_score 且重新排序后的 chunk 列表
    reranked_chunks: list[dict[str, Any]] = (
        []
    )  # 创建新的列表，用来保存补充 rerank_score 后的结果

    for chunk in chunks:  # 遍历每一个候选 chunk
        chunk_with_score = dict(chunk)  # 复制当前 chunk，避免直接修改原始输入数据

        rerank_score = calculate_rerank_score(  # 调用单条 chunk 精排函数，计算当前 chunk 的 rerank_score
            question=question,  # 传入用户问题
            chunk=chunk_with_score,  # 传入当前 chunk 数据
        )  # 得到当前 chunk 的精排分数

        chunk_with_score["rerank_score"] = (
            rerank_score  # 把 rerank_score 写入当前 chunk 结果中
        )

        reranked_chunks.append(
            chunk_with_score
        )  # 把补充精排分数后的 chunk 加入结果列表

    reranked_chunks.sort(  # 对所有候选 chunks 重新排序
        key=lambda item: item.get(
            "rerank_score", 0.0
        ),  # 按 rerank_score 从高到低排序，如果没有则按 0 处理
        reverse=True,  # reverse=True 表示降序，分数越高越靠前
    )  # 完成排序

    return reranked_chunks  # 返回重新排序后的 chunks


def deduplicate_chunks(  # 定义候选 chunk 去重函数，用来提高引用质量
    chunks: list[dict[str, Any]],  # 输入已经 rerank 排序后的 chunk 列表
) -> list[dict[str, Any]]:  # 返回去重后的 chunk 列表
    deduplicated_chunks: list[dict[str, Any]] = []  # 创建去重后的结果列表

    seen_chunk_ids: set[int] = (
        set()
    )  # 记录已经保留过的 chunk_id，避免同一个 chunk 重复出现

    seen_content_fingerprints: set[str] = (
        set()
    )  # 记录已经保留过的内容指纹，避免内容重复

    document_chunk_counts: dict[int, int] = (
        {}
    )  # 记录每个 document_id 已经保留了几个 chunk

    for (
        chunk
    ) in (
        chunks
    ):  # 遍历 rerank 后的 chunk 列表，因为前面的分数更高，所以会优先保留高分 chunk
        chunk_id = chunk.get("chunk_id")  # 从 chunk 中读取 chunk_id

        document_id = chunk.get("document_id")  # 从 chunk 中读取 document_id

        content = str(  # 把 chunk 内容转换成字符串，避免 None 类型影响后续处理
            chunk.get("content", "")  # 如果 content 不存在，就使用空字符串
        ).strip()  # 去掉内容前后的空格和换行

        if (
            chunk_id is not None and chunk_id in seen_chunk_ids
        ):  # 如果当前 chunk_id 已经出现过
            continue  # 跳过当前 chunk，避免重复引用同一个片段

        content_fingerprint = content[  # 构造内容指纹
            :CONTENT_FINGERPRINT_LENGTH  # 取内容前 80 个字符作为简单重复判断依据
        ]  # 得到当前 chunk 的内容指纹

        if (
            content_fingerprint and content_fingerprint in seen_content_fingerprints
        ):  # 如果内容指纹已经出现过
            continue  # 跳过当前 chunk，避免内容高度重复

        if document_id is not None:  # 如果当前 chunk 有 document_id
            current_document_count = (
                document_chunk_counts.get(  # 获取当前文档已经保留的 chunk 数量
                    document_id,  # 当前文档 ID
                    0,  # 如果还没有记录，就认为已经保留 0 个
                )
            )  # 得到当前文档已保留数量

            if (
                current_document_count >= MAX_CHUNKS_PER_DOCUMENT
            ):  # 如果当前文档已经达到最大保留数量
                continue  # 跳过当前 chunk，避免同一个文档占用太多上下文位置

        deduplicated_chunks.append(
            chunk
        )  # 当前 chunk 通过所有去重规则，加入最终结果列表

        if chunk_id is not None:  # 如果当前 chunk 有 chunk_id
            seen_chunk_ids.add(
                chunk_id
            )  # 记录当前 chunk_id，后面遇到相同 chunk_id 就跳过

        if content_fingerprint:  # 如果当前 chunk 的内容指纹不是空字符串
            seen_content_fingerprints.add(
                content_fingerprint
            )  # 记录当前内容指纹，后面遇到相同内容就跳过

        if document_id is not None:  # 如果当前 chunk 有 document_id
            document_chunk_counts[document_id] = (
                document_chunk_counts.get(  # 更新当前文档已保留 chunk 数量
                    document_id,  # 当前文档 ID
                    0,  # 如果之前没记录，就从 0 开始
                )
                + 1
            )  # 当前文档保留数量加 1

    return deduplicated_chunks  # 返回去重后的 chunk 列表


    
