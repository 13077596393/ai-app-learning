import json  # 导入 json，用来把 citations 列表序列化成字符串保存到数据库

from sqlmodel import Session  # 导入数据库会话类型，用于类型注解和数据库操作

from models import RagEvalCase, RagEvalResult, RagEvalRun  # 导入评测用例、评测运行和评测结果模型
from schemas import RagCitation, RagEvalSingleRunResponse  # 导入 RAG 引用结构和单条评测响应结构
from services.llm_service import call_llm_with_prompt  # 导入 LLM 调用函数，用 prompt 生成答案
from services.rag_service import (  # 导入 RAG 相关工具函数
    build_citation_preview,  # 构建 citation 预览文本
    build_context_from_search_results,  # 把 top_results 拼成 RAG context
    build_rag_prompt,  # 构建 RAG prompt
    validate_answer_citations,  # 校验 answer 是否包含有效引用编号
)
from services.retrieval_service import search_top_chunks  # 导入检索函数，用于获取 top-k chunks
from services.rerank_service import (
    get_result_score,
)  # 导入统一分数读取函数，用于评测时判断命中质量

EVAL_MIN_RELEVANCE_SCORE = 0.45  # 定义评测最低相关度阈值，和 RAG 问答接口保持一致
EVAL_HIGH_CONFIDENCE_SCORE = 0.75  # 定义高置信度阈值，最高分达到该值时返回 high
EVAL_TOP_K = 3  # 定义评测时默认检索的资料数量

EVAL_NO_RELEVANT_CONTENT_ANSWER = "知识库中没有找到足够相关的内容，无法基于当前资料回答该问题。你可以补充相关文档后再提问，或者换一个和当前知识库内容更相关的问题。"  # 定义无相关资料时的拒答提示
EVAL_CITATION_FAILED_ANSWER = "当前回答无法确认可靠引用来源，因此不返回该答案。请换一个更具体的问题，或补充更明确的知识库资料后再试。"  # 定义引用校验失败时的拒答提示

BAD_CASE_RETRIEVAL_FAILED = (
    "retrieval_failed"  # 定义检索失败类型，表示没有命中期望文档或正确资料
)
BAD_CASE_CITATION_FAILED = (
    "citation_failed"  # 定义引用失败类型，表示答案没有有效 [资料 X] 引用
)
BAD_CASE_ANSWER_FAILED = (
    "answer_failed"  # 定义答案失败类型，表示资料或引用存在，但答案缺少关键内容
)
BAD_CASE_SHOULD_REFUSE_FAILED = (
    "should_refuse_failed"  # 定义应该拒答但没有拒答的失败类型
)
BAD_CASE_OVER_REFUSED = "over_refused"  # 定义误拒答类型，表示知识库应有答案但系统拒答

def get_eval_confidence_level(best_score: float | None) -> str:  # 根据最高 final_score 计算评测置信度等级
    if best_score is None:  # 如果没有分数，说明没有可信检索结果
        return "low"  # 返回低置信度

    if best_score >= EVAL_HIGH_CONFIDENCE_SCORE:  # 如果分数达到高置信度阈值
        return "high"  # 返回高置信度

    if best_score >= EVAL_MIN_RELEVANCE_SCORE:  # 如果分数达到最低回答阈值
        return "medium"  # 返回中等置信度

    return "low"  # 如果低于最低阈值，返回低置信度


def normalize_eval_text(text: str) -> str:  # 标准化评测文本，提升关键词和文档名匹配稳定性
    normalized_text = text.strip()  # 去掉文本前后的空白字符
    normalized_text = normalized_text.lower()  # 英文统一转小写，避免大小写导致匹配失败
    normalized_text = normalized_text.replace("，", ",")  # 中文逗号替换成英文逗号
    normalized_text = normalized_text.replace("。", ".")  # 中文句号替换成英文句号
    normalized_text = " ".join(normalized_text.split())  # 压缩连续空白字符
    return normalized_text  # 返回标准化后的文本


def split_expected_keywords(expected_keywords: str) -> list[str]:  # 把期望关键词字符串切成关键词列表
    normalized_keywords_text = normalize_eval_text(expected_keywords)  # 先标准化关键词字符串

    if not normalized_keywords_text:  # 如果没有配置关键词
        return []  # 返回空列表

    keywords = [  # 创建关键词列表
        keyword.strip()  # 去掉每个关键词前后的空白字符
        for keyword in normalized_keywords_text.split(",")  # 按英文逗号切分，中文逗号已提前替换
        if keyword.strip()  # 过滤空关键词
    ]  # 结束关键词列表创建

    return keywords  # 返回关键词列表


def check_expected_keywords(  # 检查答案和引用内容是否命中期望关键词
    expected_keywords: str,  # 期望关键词字符串
    answer: str,  # RAG 实际答案
    citations: list[RagCitation],  # RAG 返回的引用来源列表
) -> tuple[bool, list[str], list[str]]:  # 返回是否全命中、已命中关键词、缺失关键词
    keywords = split_expected_keywords(expected_keywords)  # 把关键词字符串转成列表

    if not keywords:  # 如果没有配置关键词
        return True, [], []  # 默认关键词检查通过

    citation_text = " ".join(  # 把所有 citation 的完整内容和预览拼成文本
        f"{citation.content} {citation.preview}"  # 拼接当前 citation 的 content 和 preview
        for citation in citations  # 遍历所有 citation
    )  # 结束 citation 文本拼接

    combined_text = f"{answer} {citation_text}"  # 把答案和引用内容拼成待匹配文本
    normalized_combined_text = normalize_eval_text(combined_text)  # 标准化待匹配文本

    matched_keywords: list[str] = []  # 创建已命中关键词列表
    missing_keywords: list[str] = []  # 创建缺失关键词列表

    for keyword in keywords:  # 遍历每个期望关键词
        if keyword in normalized_combined_text:  # 如果关键词出现在答案或引用内容里
            matched_keywords.append(keyword)  # 加入已命中列表
        else:  # 如果关键词没有出现
            missing_keywords.append(keyword)  # 加入缺失列表

    hit_expected_keywords = len(missing_keywords) == 0  # 没有缺失关键词就算命中成功
    return hit_expected_keywords, matched_keywords, missing_keywords  # 返回检查结果


def check_expected_document_hit(  # 检查 citations 是否命中期望文档
    expected_document_name: str,  # 期望文档名
    citations: list[RagCitation],  # RAG 返回的引用来源列表
) -> bool:  # 返回是否命中期望文档
    cleaned_expected_name = normalize_eval_text(expected_document_name)  # 标准化期望文档名

    if not cleaned_expected_name:  # 如果没有配置期望文档名
        return True  # 默认文档命中检查通过

    for citation in citations:  # 遍历所有引用来源
        normalized_document_name = normalize_eval_text(citation.document_name)  # 标准化当前 citation 文档名

        if cleaned_expected_name in normalized_document_name:  # 如果期望文档名包含在 citation 文档名中
            return True  # 命中一个就返回 True

    return False  # 所有 citations 都没命中，返回 False


def build_eval_citations(
    top_results: list[dict],
) -> list[RagCitation]:  # 根据 top_results 构建评测用 citations
    citations = [  # 创建 citations 列表
        RagCitation(  # 创建单个引用来源对象
            source_index=source_index,  # 设置资料编号，从 1 开始
            chunk_id=result["chunk_id"],  # 设置 chunk ID
            document_id=result["document_id"],  # 设置文档 ID
            document_name=result["document_name"],  # 设置文档名称
            chunk_index=result["chunk_index"],  # 设置 chunk 序号
            vector_score=result.get(
                "vector_score", 0.0
            ),  # 设置向量相似度分数，如果没有就使用 0
            keyword_score=result.get(
                "keyword_score", 0.0
            ),  # 设置关键词分数，如果没有就使用 0
            hybrid_score=result.get(  # 设置 Hybrid 混合检索分数
                "hybrid_score",  # 优先读取 hybrid_score
                result.get(
                    "final_score", 0.0
                ),  # 如果没有 hybrid_score，就兼容旧的 final_score
            ),  # 结束 hybrid_score 设置
            final_score=result.get(  # 设置旧版 final_score 字段
                "final_score",  # 优先读取 final_score
                result.get(
                    "hybrid_score", 0.0
                ),  # 如果没有 final_score，就使用 hybrid_score
            ),  # 结束 final_score 设置
            rerank_score=get_result_score(  # 设置 Rerank 精排分数
                result  # 使用统一分数函数，优先 rerank_score，其次 hybrid_score，再其次 final_score
            ),  # 结束 rerank_score 设置
            content=result["content"],  # 设置完整引用内容
            preview=build_citation_preview(result["content"]),  # 设置引用预览文本
        )  # 结束单个 RagCitation 创建
        for source_index, result in enumerate(
            top_results, start=1
        )  # 遍历 top_results 并生成资料编号
    ]  # 结束 citations 列表创建

    return citations  # 返回 citations


def run_eval_case_logic(  # 运行单条 RAG 评测用例的核心业务逻辑
    session: Session,  # 数据库会话
    knowledge_base_id: int,  # 当前知识库 ID
    eval_case: RagEvalCase,  # 当前评测用例对象
) -> RagEvalSingleRunResponse:  # 返回单条评测运行结果
    top_results = search_top_chunks(  # 检索当前问题对应的 top chunks
        session=session,  # 传入数据库会话
        knowledge_base_id=knowledge_base_id,  # 传入知识库 ID
        question=eval_case.question,  # 使用评测用例里的固定问题
        top_k=EVAL_TOP_K,  # 使用默认评测 top_k
        min_score=EVAL_MIN_RELEVANCE_SCORE,  # 使用最低相关度阈值过滤低分 chunks
    )  # 结束检索

    if not top_results:  # 如果没有可信检索结果
        actual_answer = EVAL_NO_RELEVANT_CONTENT_ANSWER  # 使用低相关度拒答提示
        actual_refused = True  # 标记系统实际拒答
        confidence_level = "low"  # 没有可信资料时置信度为 low
        citations: list[RagCitation] = []  # 没有引用来源
        citation_valid = True  # 拒答场景不要求有效引用，视为通过引用要求
    else:  # 如果检索到了可信 chunks
        citations = build_eval_citations(top_results)  # 根据检索结果构建 citations
        valid_source_indexes = [citation.source_index for citation in citations]  # 提取有效引用编号
        context = build_context_from_search_results(top_results)  # 构建 RAG context
        prompt = build_rag_prompt(  # 构建 RAG prompt
            question=eval_case.question,  # 传入评测问题
            context=context,  # 传入知识库资料上下文
        )  # 结束 prompt 构建
        answer = call_llm_with_prompt(prompt)  # 调用 LLM 生成答案
        citation_valid = validate_answer_citations(  # 校验答案是否包含有效引用编号
            answer=answer,  # 传入 LLM 答案
            valid_source_indexes=valid_source_indexes,  # 传入有效资料编号列表
        )  # 结束引用校验

        if not citation_valid:  # 如果引用校验失败
            actual_answer = EVAL_CITATION_FAILED_ANSWER  # 返回引用失败拒答提示
            actual_refused = True  # 引用校验失败也视为拒答
            confidence_level = "low"  # 引用校验失败时置信度为 low
        else:  # 如果引用校验通过
            actual_answer = answer  # 使用模型实际答案
            actual_refused = False  # 标记系统没有拒答
            best_score = get_result_score(  # 调用统一分数读取函数
                top_results[0]  # 传入排名第一的检索结果
            )  # 得到优先使用 rerank_score 的评测分数
            confidence_level = get_eval_confidence_level(best_score)  # 根据最高分计算置信度

    hit_expected_keywords, matched_keywords, missing_keywords = check_expected_keywords(  # 检查关键词是否命中
        expected_keywords=eval_case.expected_keywords,  # 传入期望关键词
        answer=actual_answer,  # 传入实际答案
        citations=citations,  # 传入 citations
    )  # 结束关键词检查

    hit_expected_document = check_expected_document_hit(  # 检查期望文档是否命中
        expected_document_name=eval_case.expected_document_name,  # 传入期望文档名
        citations=citations,  # 传入 citations
    )  # 结束文档命中检查

    bad_case_type = ""  # 初始化 bad case 类型，评测通过时保持为空

    if eval_case.should_refuse:  # 如果这道题期望拒答
        passed = actual_refused  # 只有系统实际拒答，才算通过

        if passed:  # 如果系统正确拒答
            notes = "期望拒答，系统已拒答，通过。说明低置信拒答逻辑生效。"  # 设置拒答通过说明
        else:  # 如果系统没有拒答
            bad_case_type = BAD_CASE_SHOULD_REFUSE_FAILED  # 设置为应该拒答失败，表示系统对无依据问题进行了回答
            notes = (  # 设置失败说明
                f"bad_case_type={bad_case_type}；"  # 写入标准 Bad Case 类型
                "期望拒答，但系统没有拒答，说明低置信拒答没有拦住该问题。"  # 说明核心失败现象
                "可能原因包括：最低相关度阈值偏低、无关 chunk 被错误检索、"  # 说明可能原因一
                "rerank_score 过高、should_refuse 测试题与知识库内容存在意外重叠，"  # 说明可能原因二
                "或者 LLM 在资料不足时仍然生成了看似合理的答案。"  # 说明可能原因三
            )  # 结束失败说明
    else:  # 如果这道题期望正常回答
        passed = (  # 计算正常回答题是否通过
            not actual_refused  # 系统不能拒答，因为这道题知识库里应该有答案
            and hit_expected_keywords  # 答案或引用内容必须命中期望关键词
            and hit_expected_document  # citations 必须命中期望文档
            and citation_valid  # 答案里必须包含有效的 [资料 X] 引用
        )  # 结束通过条件计算

        if passed:  # 如果正常回答题通过
            notes = "期望正常回答，系统回答、关键词命中、文档命中和引用校验均通过。"  # 设置通过说明
        else:  # 如果正常回答题失败
            failed_reasons: list[str] = []  # 创建失败原因列表，用来记录这道题具体失败在哪里

            if actual_refused:  # 如果系统发生了拒答
                bad_case_type = BAD_CASE_OVER_REFUSED  # 设置为误拒答，表示本该回答但系统拒答
                failed_reasons.append(  # 记录误拒答原因
                    "系统发生误拒答，可能是最低相关度阈值偏高、检索召回不足、top_k 太小、embedding 未写入成功，或 query rewrite 没有改写到有效检索词。"  # 说明可能原因
                )  # 结束误拒答原因记录

            elif not citation_valid:  # 如果系统没有拒答，但引用编号无效
                bad_case_type = BAD_CASE_CITATION_FAILED  # 设置为引用失败
                failed_reasons.append(  # 记录引用失败原因
                    "引用校验失败，answer 中没有有效的 [资料 X] 引用，可能是 Prompt 对引用格式约束不够强，或 LLM 没有按要求输出引用编号。"  # 说明可能原因
                )  # 结束引用失败原因记录

            elif not hit_expected_document:  # 如果引用有效，但没有命中期望文档
                bad_case_type = BAD_CASE_RETRIEVAL_FAILED  # 设置为检索失败
                failed_reasons.append(  # 记录检索失败原因
                    "期望文档未命中，说明 citations 没有引用到期望来源，可能是检索召回错误、metadata 过滤不当、文档名配置不匹配，或正确资料没有进入 top_results。"  # 说明可能原因
                )  # 结束检索失败原因记录

            elif not hit_expected_keywords:  # 如果文档命中但关键词没有全部命中
                bad_case_type = BAD_CASE_ANSWER_FAILED  # 设置为答案失败
                failed_reasons.append(  # 记录答案失败原因
                    f"期望关键词未全部命中，缺失关键词：{missing_keywords}，可能是生成答案不完整、上下文片段不够精准，或 expected_keywords 设置过严。"  # 说明缺失关键词和可能原因
                )  # 结束答案失败原因记录

            else:  # 如果没有命中上面任何明确失败原因
                bad_case_type = BAD_CASE_ANSWER_FAILED  # 默认归类为答案失败
                failed_reasons.append(  # 记录兜底失败原因
                    "正常回答题未通过，但未命中明确失败条件，需要人工检查 actual_answer、citations、matched_keywords 和 missing_keywords。"  # 说明需要人工排查
                )  # 结束兜底失败原因记录

            notes = f"bad_case_type={bad_case_type}；" + "；".join(  # 拼接结构化失败说明
                failed_reasons  # 拼接所有失败原因
            )  # 得到最终 notes

    return RagEvalSingleRunResponse(  # 返回单条评测响应对象
        case_id=eval_case.id or 0,  # 返回评测用例 ID
        knowledge_base_id=knowledge_base_id,  # 返回知识库 ID
        question=eval_case.question,  # 返回问题
        expected_answer=eval_case.expected_answer,  # 返回参考答案
        actual_answer=actual_answer,  # 返回实际答案
        should_refuse=eval_case.should_refuse,  # 返回是否期望拒答
        actual_refused=actual_refused,  # 返回是否实际拒答
        confidence_level=confidence_level,  # 返回置信度等级
        expected_keywords=eval_case.expected_keywords,  # 返回期望关键词
        matched_keywords=matched_keywords,  # 返回已命中关键词
        missing_keywords=missing_keywords,  # 返回缺失关键词
        hit_expected_keywords=hit_expected_keywords,  # 返回关键词命中结果
        expected_document_name=eval_case.expected_document_name,  # 返回期望文档名
        hit_expected_document=hit_expected_document,  # 返回文档命中结果
        citation_valid=citation_valid,  # 返回引用校验结果
        passed=passed,  # 返回是否通过
        notes=notes,  # 返回评测说明
        citations=citations,  # 返回引用来源列表
    )  # 结束响应对象创建


def serialize_citations_to_json(citations: list[RagCitation]) -> str:  # 把 citations 转成 JSON 字符串
    citation_dicts = [  # 创建 citation 字典列表
        {
            "source_index": citation.source_index,  # 保存资料编号
            "chunk_id": citation.chunk_id,  # 保存 chunk ID
            "document_id": citation.document_id,  # 保存文档 ID
            "document_name": citation.document_name,  # 保存文档名称
            "chunk_index": citation.chunk_index,  # 保存 chunk 序号
            "vector_score": citation.vector_score,  # 保存向量相似度分数
            "keyword_score": citation.keyword_score,  # 保存关键词分数
            "hybrid_score": citation.hybrid_score,  # 保存 Hybrid 混合检索分数，方便分析初筛排序
            "final_score": citation.final_score,  # 保存旧版 final_score，兼容旧评测结果
            "rerank_score": citation.rerank_score,  # 保存 Rerank 精排分数，方便分析最终排序
            "content": citation.content,  # 保存完整引用内容
            "preview": citation.preview,  # 保存引用预览
        }  # 结束当前 citation 字典
        for citation in citations  # 遍历所有 citation
    ]  # 结束 citation 字典列表

    citations_json = json.dumps(citation_dicts, ensure_ascii=False)  # 序列化为 JSON 字符串并保留中文
    return citations_json  # 返回 JSON 字符串


def save_eval_run_results(  # 保存一次批量评测运行和每一道题的结果
    session: Session,  # 数据库会话
    knowledge_base_id: int,  # 当前知识库 ID
    results: list[RagEvalSingleRunResponse],  # 本次批量评测的所有单题结果
) -> RagEvalRun:  # 返回保存后的评测运行记录
    total = len(results)  # 统计总题数
    passed_count = sum(1 for result in results if result.passed)  # 统计通过题数
    failed_count = total - passed_count  # 计算失败题数
    hit_rate = passed_count / total if total > 0 else 0  # 计算命中率

    eval_run = RagEvalRun(  # 创建评测运行记录
        knowledge_base_id=knowledge_base_id,  # 设置知识库 ID
        total=total,  # 保存总题数
        passed_count=passed_count,  # 保存通过题数
        failed_count=failed_count,  # 保存失败题数
        hit_rate=hit_rate,  # 保存命中率
    )  # 结束评测运行记录创建

    session.add(eval_run)  # 加入数据库会话
    session.commit()  # 提交，生成 eval_run.id
    session.refresh(eval_run)  # 刷新对象，拿到数据库生成的 ID

    for result in results:  # 遍历每一道题的评测结果
        eval_result = RagEvalResult(  # 创建单题评测结果记录
            eval_run_id=eval_run.id,  # 关联本次评测运行 ID
            eval_case_id=result.case_id,  # 保存评测用例 ID
            knowledge_base_id=knowledge_base_id,  # 保存知识库 ID
            question=result.question,  # 保存问题快照
            expected_answer=result.expected_answer,  # 保存参考答案快照
            actual_answer=result.actual_answer,  # 保存实际答案
            should_refuse=result.should_refuse,  # 保存是否期望拒答
            actual_refused=result.actual_refused,  # 保存是否实际拒答
            confidence_level=result.confidence_level,  # 保存置信度
            expected_keywords=result.expected_keywords,  # 保存期望关键词
            matched_keywords=",".join(result.matched_keywords),  # 保存已命中关键词字符串
            missing_keywords=",".join(result.missing_keywords),  # 保存缺失关键词字符串
            hit_expected_keywords=result.hit_expected_keywords,  # 保存关键词命中结果
            expected_document_name=result.expected_document_name,  # 保存期望文档名
            hit_expected_document=result.hit_expected_document,  # 保存文档命中结果
            citation_valid=result.citation_valid,  # 保存引用校验结果
            passed=result.passed,  # 保存是否通过
            notes=result.notes,  # 保存评测说明
            citations_json=serialize_citations_to_json(result.citations),  # 保存 citations 快照
        )  # 结束单题评测结果创建

        session.add(eval_result)  # 把单题结果加入数据库会话

    session.commit()  # 提交所有单题结果
    return eval_run  # 返回评测运行记录
