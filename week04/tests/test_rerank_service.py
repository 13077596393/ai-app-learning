from services.rerank_service import (  # 从 rerank_service 中导入要测试的函数
    deduplicate_chunks,  # 导入 chunk 去重函数
    get_result_score,  # 导入统一读取结果分数的函数
    rerank_chunks,  # 导入 chunk 精排函数
)  # 结束导入


def test_get_result_score_should_use_rerank_score_first():  # 测试 get_result_score 是否优先使用 rerank_score
    result = {  # 构造一条假的检索结果
        "rerank_score": 0.86,  # Rerank 精排分数，优先级最高
        "hybrid_score": 0.72,  # Hybrid 混合检索分数，优先级低于 rerank_score
        "final_score": 0.68,  # 旧版最终分数，优先级低于 hybrid_score
    }  # 结束测试数据构造

    score = get_result_score(result)  # 调用被测试函数，读取最终分数

    assert score == 0.86  # 断言返回 rerank_score，说明优先级正确


def test_get_result_score_should_fallback_to_hybrid_score():  # 测试没有 rerank_score 时是否退回使用 hybrid_score
    result = {  # 构造一条没有 rerank_score 的检索结果
        "hybrid_score": 0.72,  # 提供 hybrid_score
        "final_score": 0.68,  # 提供 final_score
    }  # 结束测试数据构造

    score = get_result_score(result)  # 调用被测试函数

    assert score == 0.72  # 断言返回 hybrid_score，说明 fallback 逻辑正确


def test_get_result_score_should_clamp_score_to_one():  # 测试分数超过 1 时是否会被裁剪到 1
    result = {  # 构造一条分数异常的检索结果
        "rerank_score": "bad-value",  # rerank_score 无法转换成 float，应该被跳过
        "hybrid_score": 1.5,  # hybrid_score 超过最大值 1，应该被裁剪
    }  # 结束测试数据构造

    score = get_result_score(result)  # 调用被测试函数

    assert score == 1.0  # 断言最终分数被限制在 1.0


def test_rerank_chunks_should_add_rerank_score_and_sort_desc():  # 测试 rerank_chunks 是否会添加 rerank_score 并按分数降序排序
    chunks = [  # 构造候选 chunk 列表
        {  # 第一个 chunk
            "chunk_id": 1,  # chunk ID
            "document_id": 1,  # 文档 ID
            "content": "这是一段普通背景介绍内容，主要描述公司内部管理信息。",  # 内容长度合理，但没有明显答案型关键词
            "hybrid_score": 0.70,  # Hybrid 分数
        },  # 结束第一个 chunk
        {  # 第二个 chunk
            "chunk_id": 2,  # chunk ID
            "document_id": 1,  # 文档 ID
            "content": "员工报销流程需要提交发票和费用说明材料，由负责人审批后处理。",  # 内容包含流程、材料、审批等答案型关键词
            "hybrid_score": 0.69,  # Hybrid 分数略低
        },  # 结束第二个 chunk
    ]  # 结束候选 chunk 列表

    reranked_chunks = rerank_chunks(  # 调用精排函数
        question="员工报销流程是什么？",  # 传入用户问题
        chunks=chunks,  # 传入候选 chunks
    )  # 得到精排后的 chunks

    assert (
        "rerank_score" in reranked_chunks[0]
    )  # 断言第一条结果已经新增 rerank_score 字段
    assert (
        "rerank_score" in reranked_chunks[1]
    )  # 断言第二条结果也新增 rerank_score 字段
    assert reranked_chunks[0]["chunk_id"] == 2  # 断言更像答案的 chunk 被排到第一位
    assert (
        reranked_chunks[0]["rerank_score"] >= reranked_chunks[1]["rerank_score"]
    )  # 断言结果按 rerank_score 降序排列


def test_deduplicate_chunks_should_remove_duplicate_chunks_and_limit_same_document():  # 测试 deduplicate_chunks 是否能去重并限制同一文档数量
    chunks = [  # 构造已经按分数排好序的 chunks
        {  # 第一条，高分，应该保留
            "chunk_id": 1,  # chunk ID
            "document_id": 1,  # 文档 ID
            "content": "试用期员工离职需要提前 3 天通知公司，并完成工作交接。",  # chunk 内容
            "rerank_score": 0.95,  # 精排分数
        },  # 结束第一条
        {  # 第二条，chunk_id 重复，应该跳过
            "chunk_id": 1,  # 和第一条 chunk_id 相同
            "document_id": 1,  # 文档 ID
            "content": "试用期员工离职需要提前 3 天通知公司，并完成工作交接。",  # 内容也相同
            "rerank_score": 0.90,  # 精排分数
        },  # 结束第二条
        {  # 第三条，内容重复，应该跳过
            "chunk_id": 2,  # chunk_id 不同
            "document_id": 1,  # 文档 ID
            "content": "试用期员工离职需要提前 3 天通知公司，并完成工作交接。",  # 内容指纹和第一条相同
            "rerank_score": 0.88,  # 精排分数
        },  # 结束第三条
        {  # 第四条，同文档第二条有效内容，应该保留
            "chunk_id": 3,  # chunk ID
            "document_id": 1,  # 和第一条同一个文档
            "content": "正式员工离职通常需要提前 30 天提交离职申请。",  # 不同内容
            "rerank_score": 0.80,  # 精排分数
        },  # 结束第四条
        {  # 第五条，同文档第三条有效内容，应该因为超过同文档上限被跳过
            "chunk_id": 4,  # chunk ID
            "document_id": 1,  # 仍然是文档 1
            "content": "员工离职后需要归还公司资产并完成账号权限移交。",  # 不同内容
            "rerank_score": 0.75,  # 精排分数
        },  # 结束第五条
        {  # 第六条，新文档内容，应该保留
            "chunk_id": 5,  # chunk ID
            "document_id": 2,  # 新文档 ID
            "content": "员工报销需要提交发票、费用说明和审批记录。",  # chunk 内容
            "rerank_score": 0.70,  # 精排分数
        },  # 结束第六条
    ]  # 结束测试数据构造

    deduplicated_chunks = deduplicate_chunks(chunks)  # 调用去重函数

    kept_chunk_ids = [
        chunk["chunk_id"] for chunk in deduplicated_chunks
    ]  # 提取最终保留下来的 chunk_id

    assert kept_chunk_ids == [1, 3, 5]  # 断言最终只保留高分去重后的 chunk
