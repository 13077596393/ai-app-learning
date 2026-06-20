#1. 能调用检索函数拿到 top_results
#2. 能把 top_results 构造成 citations
#3. 能构建 RAG prompt
#4. 能调用 LLM 生成 answer
#5. 能校验 [资料 1] 引用
#6. 能检查 expected_keywords
#7. 能检查 expected_document_name
#8. 能判断 passed=True
#9. 能保留 rerank_score

from models import (
    RagEvalCase,
)  # 导入 RAG 评测用例模型，用来构造一条假的 Golden Set 用例

from services import (
    eval_service,
)  # 导入整个 eval_service 模块，方便 monkeypatch 替换模块里的函数


def test_run_eval_case_logic_should_use_mock_llm_and_pass(
    monkeypatch,
):  # 测试单条评测逻辑：mock LLM 和检索结果后应该通过
    call_counter = {  # 创建调用计数字典，用来确认 fake 函数真的被调用了
        "search": 0,  # 记录 fake_search_top_chunks 被调用次数
        "llm": 0,  # 记录 fake_call_llm_with_prompt 被调用次数
    }  # 结束计数字典创建

    def fake_search_top_chunks(  # 定义假的检索函数，用来替代真实 search_top_chunks
        session,  # 接收数据库会话参数，保持和真实函数调用兼容
        knowledge_base_id: int,  # 接收知识库 ID
        question: str,  # 接收评测问题
        top_k: int,  # 接收 top_k
        min_score: float,  # 接收最低分数阈值
    ) -> list[dict]:  # 返回假的检索结果列表
        call_counter["search"] += 1  # 记录检索函数被调用了一次

        assert knowledge_base_id == 1  # 断言传入的知识库 ID 是测试用例里的知识库 ID
        assert question == "试用期离职需要提前几天？"  # 断言检索问题是评测用例的问题
        assert top_k == eval_service.EVAL_TOP_K  # 断言使用的是评测默认 top_k
        assert (
            min_score == eval_service.EVAL_MIN_RELEVANCE_SCORE
        )  # 断言使用的是评测最低相关度阈值

        return [  # 返回一条假的高质量检索结果
            {  # 第一条检索结果
                "chunk_id": 1,  # 设置 chunk ID
                "document_id": 1,  # 设置文档 ID
                "document_name": "企业制度知识库测试文档.txt",  # 设置文档名称，用来命中 expected_document_name
                "chunk_index": 0,  # 设置 chunk 序号
                "content": "试用期员工离职需要提前 3 天通知公司。",  # 设置 chunk 内容，用来命中 expected_keywords
                "vector_score": 0.82,  # 设置向量分数
                "keyword_score": 0.70,  # 设置关键词分数
                "hybrid_score": 0.78,  # 设置混合检索分数
                "final_score": 0.78,  # 设置兼容旧字段的最终分数
                "rerank_score": 0.90,  # 设置 Rerank 精排分数，用于高置信度判断
            }  # 结束第一条检索结果
        ]  # 结束检索结果列表

    def fake_call_llm_with_prompt(
        prompt: str,
    ) -> str:  # 定义假的 LLM 函数，用来替代真实大模型调用
        call_counter["llm"] += 1  # 记录 LLM 函数被调用了一次

        assert "试用期离职需要提前几天？" in prompt  # 断言 prompt 里包含评测问题
        assert (
            "试用期员工离职需要提前 3 天通知公司" in prompt
        )  # 断言 prompt 里包含检索到的知识库资料

        return "根据资料，试用期员工离职需要提前 3 天通知公司。[资料 1]"  # 返回固定答案，避免真实调用 LLM

    monkeypatch.setattr(  # 使用 monkeypatch 替换 eval_service 模块里的检索函数
        eval_service,  # 指定要修改的模块对象
        "search_top_chunks",  # 指定要替换的函数名
        fake_search_top_chunks,  # 替换成假的检索函数
    )  # 结束检索函数替换

    monkeypatch.setattr(  # 使用 monkeypatch 替换 eval_service 模块里的 LLM 函数
        eval_service,  # 指定要修改的模块对象
        "call_llm_with_prompt",  # 指定要替换的函数名
        fake_call_llm_with_prompt,  # 替换成假的 LLM 函数
    )  # 结束 LLM 函数替换

    eval_case = RagEvalCase(  # 构造一条假的 Golden Set 评测用例
        id=1,  # 设置评测用例 ID
        knowledge_base_id=1,  # 设置所属知识库 ID
        question="试用期离职需要提前几天？",  # 设置评测问题
        expected_answer="试用期员工离职需要提前 3 天通知公司。",  # 设置参考答案
        expected_keywords="试用期,离职,提前,3 天",  # 设置期望命中的关键词
        expected_document_name="企业制度知识库测试文档",  # 设置期望命中的文档名称
        should_refuse=False,  # 设置该题期望正常回答
    )  # 结束评测用例构造

    result = eval_service.run_eval_case_logic(  # 调用真实评测逻辑，但内部 LLM 和检索已经被 mock
        session=None,  # 传入 None，因为 fake_search_top_chunks 不需要真实数据库会话
        knowledge_base_id=1,  # 传入知识库 ID
        eval_case=eval_case,  # 传入评测用例
    )  # 得到评测结果

    assert call_counter["search"] == 1  # 断言 fake_search_top_chunks 确实被调用了一次
    assert call_counter["llm"] == 1  # 断言 fake_call_llm_with_prompt 确实被调用了一次
    assert result.passed is True  # 断言这条评测通过
    assert result.actual_refused is False  # 断言系统没有拒答
    assert result.citation_valid is True  # 断言答案引用 [资料 1] 是有效引用
    assert result.hit_expected_keywords is True  # 断言关键词全部命中
    assert result.hit_expected_document is True  # 断言命中了期望文档
    assert result.confidence_level == "high"  # 断言 rerank_score=0.90 对应高置信度
    assert (
        result.actual_answer
        == "根据资料，试用期员工离职需要提前 3 天通知公司。[资料 1]"
    )  # 断言实际答案来自 fake LLM
    assert (
        result.citations[0].rerank_score == 0.90
    )  # 断言 citation 里保留了 rerank_score
