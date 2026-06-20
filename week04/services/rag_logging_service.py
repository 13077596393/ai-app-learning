#这个文件做了
#1. 从 citations 中提取 chunk_id
#2. 从 citations 中提取 score / final_score
#3. 提取 context
#4. 写入 rag_retrieval_logs 表
import time  # 导入 time 模块，用来计算 RAG 检索耗时

from typing import Any  # 导入 Any 类型，用来表示字典里可以保存任意结构的数据

from services.observability_service import (
    create_rag_retrieval_log,
)  # 导入 RAG 检索日志写入函数，用来保存 rag_retrieval_logs 记录


def extract_chunk_ids_from_citations(  # 定义从 citations 中提取 chunk_id 列表的函数
    citations: list[dict[str, Any]],  # 接收引用来源列表，每个元素通常是一个字典
) -> list[int]:  # 返回命中的 chunk ID 列表
    chunk_ids = []  # 创建空列表，用来保存提取出来的 chunk_id

    for citation in citations:  # 遍历每一条引用来源
        chunk_id = citation.get("chunk_id")  # 尝试从引用来源中取出 chunk_id 字段

        if chunk_id is None:  # 判断当前引用里是否没有 chunk_id
            chunk_id = citation.get(
                "document_chunk_id"
            )  # 如果没有 chunk_id，就尝试读取 document_chunk_id

        if chunk_id is None:  # 判断是否仍然没有拿到 chunk ID
            continue  # 如果没有拿到，就跳过这一条 citation

        try:  # 尝试把 chunk_id 转成整数
            chunk_ids.append(int(chunk_id))  # 把整数类型的 chunk_id 加入列表
        except (TypeError, ValueError):  # 捕获类型错误或数值转换错误
            continue  # 如果转换失败，就跳过这一条 citation

    return chunk_ids  # 返回最终提取出来的 chunk ID 列表


def extract_scores_from_citations(  # 定义从 citations 中提取分数信息的函数
    citations: list[dict[str, Any]],  # 接收引用来源列表
) -> list[dict[str, Any]]:  # 返回每个 chunk 的分数信息列表
    scores = []  # 创建空列表，用来保存分数信息

    for citation in citations:  # 遍历每一条引用来源
        chunk_id = citation.get("chunk_id")  # 尝试获取 chunk_id

        if chunk_id is None:  # 判断当前引用里是否没有 chunk_id
            chunk_id = citation.get(
                "document_chunk_id"
            )  # 如果没有，就尝试获取 document_chunk_id

        score = citation.get("score")  # 尝试获取普通相似度分数

        final_score = citation.get(
            "final_score"
        )  # 尝试获取最终综合分数，比如 rerank 后的分数

        scores.append(  # 把当前 chunk 的分数信息加入 scores 列表
            {  # 创建当前 chunk 的分数字典
                "chunk_id": chunk_id,  # 保存 chunk ID
                "score": score,  # 保存普通分数
                "final_score": final_score,  # 保存最终分数
            }  # 当前分数字典结束
        )  # 当前分数记录追加结束

    return scores  # 返回所有分数信息


def record_rag_retrieval_from_tool_result(  # 定义根据工具结果写入 RAG 检索日志的函数
    task_id: int | None,  # 接收 AgentTask ID，用来关联一次完整任务，也就是 trace
    step_id: int | None,  # 接收 AgentStep ID，用来关联任务中的某个步骤，也就是 span
    knowledge_base_id: int | None,  # 接收知识库 ID，用来记录本次检索的是哪个知识库
    query: str,  # 接收本次检索问题，也就是用户问题或改写后的检索问题
    top_k: int,  # 接收本次检索最多返回多少条 chunk
    tool_result: dict[str, Any],  # 接收 search_knowledge_base 工具返回的完整结果
    latency_ms: int = 0,  # 接收检索耗时，默认是 0，后面接入时可以传真实耗时
) -> None:  # 这个函数只负责写日志，不需要返回业务结果
    success = bool(
        tool_result.get("success")
    )  # 从工具结果中读取 success，并转换成布尔值

    error_message = tool_result.get("error")  # 从工具结果中读取错误信息，成功时通常为空

    data = tool_result.get(
        "data", {}
    )  # 从工具结果中读取 data 字典，里面通常包含 context 和 citations

    context = data.get("context", "")  # 从 data 中取出最终拼接给 LLM 的上下文

    citations = data.get("citations", [])  # 从 data 中取出引用来源列表

    if citations is None:  # 判断 citations 是否为 None
        citations = []  # 如果是 None，就改成空列表，避免后面遍历时报错

    matched_chunk_ids = extract_chunk_ids_from_citations(  # 调用辅助函数，从 citations 中提取 chunk ID 列表
        citations  # 传入引用来源列表
    )  # chunk ID 提取结束

    scores = extract_scores_from_citations(  # 调用辅助函数，从 citations 中提取分数信息
        citations  # 传入引用来源列表
    )  # 分数信息提取结束

    create_rag_retrieval_log(  # 写入一条 RAG 检索日志
        task_id=task_id,  # 保存任务 ID
        step_id=step_id,  # 保存步骤 ID
        knowledge_base_id=knowledge_base_id,  # 保存知识库 ID
        query=query,  # 保存检索问题
        top_k=top_k,  # 保存 top_k
        retrieved_count=len(matched_chunk_ids),  # 保存实际命中的 chunk 数量
        matched_chunk_ids=matched_chunk_ids,  # 保存命中的 chunk ID 列表
        scores=scores,  # 保存每个 chunk 的分数信息
        context=context,  # 保存最终上下文
        latency_ms=latency_ms,  # 保存检索耗时
        status=(
            "success" if success else "failed"
        ),  # 根据工具执行结果保存 success 或 failed
        error=error_message,  # 保存错误信息
    )  # RAG 检索日志写入结束
