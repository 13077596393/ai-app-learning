from datetime import datetime  # 导入 datetime，用来更新聊天会话的 updated_at 时间
import logging  # 导入 logging，用来记录异常信息，避免使用临时 print

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)  # 导入 APIRouter 创建路由，Depends 注入依赖，HTTPException 返回错误响应
from sqlmodel import Session, select  # 导入 Session 操作数据库，select 构建查询语句

from database import get_session  # 导入 get_session，用来获取数据库会话
from models import (
    ChatMessage,
    ChatSession,
    KnowledgeBase,
)  # 导入聊天消息、聊天会话和知识库模型
from routers.users import (
    get_current_user,
)  # 导入 get_current_user，用来获取当前登录用户
from schemas import (
    RagChatRequest,
    RagChatResponse,
    RagCitation,
)  # 导入 RAG 请求体、响应体和引用来源模型
from services.llm_service import (
    call_llm_with_prompt,
)  # 导入调用 LLM 的函数，用来生成答案和历史摘要
from services.retrieval_service import (
    search_top_chunks,
)  # 导入统一检索函数，用来获取 top-k chunks
from services.project_permission_service import (  # 导入项目空间权限判断函数
    can_view_project,  # 判断当前用户是否可以查看项目空间
)  # 项目空间权限函数导入结束
from services.rag_service import (  # 从 RAG 服务中导入 prompt、历史、摘要、引用相关工具函数
    build_citation_preview,  # 导入引用预览函数，用来生成 citation 的短 preview
    build_context_from_search_results,  # 导入知识库资料 context 构建函数
    build_history_context,  # 导入历史对话 context 构建函数
    build_rag_prompt,  # 导入 RAG prompt 构建函数
    build_search_history_context,  # 导入检索历史上下文构建函数
    build_search_question,  # 导入检索问题构建函数
    get_recent_messages,  # 导入读取最近历史消息的函数
    update_conversation_summary_if_needed,  # 导入按需更新长期历史摘要的函数
    validate_answer_citations,  # 导入答案引用校验函数，用来判断 answer 是否包含有效 [资料 X]
)
from services.rate_limit_service import (
    check_rate_limit,
)  # 导入限流检查函数，用来限制 RAG 问答调用频率
from services.prompt_security_service import (  # 导入提示词安全检查函数
    validate_prompt_security,  # 用来检查用户问题里是否包含明显 Prompt Injection 内容
)  # 提示词安全服务导入结束
from services.rerank_service import (
    get_result_score,
)  # 导入统一分数读取函数，优先读取 rerank_score

router = APIRouter(
    tags=["RAG问答"]
)  # 创建 RAG 问答路由对象，并在 Swagger 中归类到“RAG问答”分组

logger = logging.getLogger(
    __name__
)  # 创建当前模块 logger，用来记录 RAG 问答过程中的异常

SEARCH_HISTORY_LIMIT = 2  # 定义用于增强检索的最近历史消息数量，通常只读取最近 2 条消息，也就是最近 1 轮问答

ANSWER_HISTORY_LIMIT = 6  # 定义用于生成回答的最近历史消息数量，通常只读取最近 6 条消息，也就是最近 3 轮问答

SUMMARY_TRIGGER_MESSAGE_COUNT = (
    10  # 定义触发历史摘要更新的消息数量，超过这个数量才开始总结历史
)

SUMMARY_KEEP_RECENT_MESSAGES = (
    6  # 定义摘要时保留最近几条消息不压缩，避免刚发生的对话被摘要覆盖
)
MIN_RELEVANCE_SCORE = 0.45  # 定义 RAG 回答的最低相关度阈值，低于这个分数的 chunks 会被过滤，避免模型基于弱相关资料胡编
HIGH_CONFIDENCE_SCORE = (
    0.75  # 定义高置信度分数阈值，最高 final_score 大于等于该值时认为回答可信度较高
)
RAG_NO_RELEVANT_CONTENT_ANSWER = "知识库中没有找到足够相关的内容，无法基于当前资料回答该问题。你可以补充相关文档后再提问，或者换一个和当前知识库内容更相关的问题。"  # 定义低相关度拒答提示语，统一用于没有可信检索结果的情况
RAG_CITATION_VALIDATION_FAILED_ANSWER = "当前回答无法确认可靠引用来源，因此不返回该答案。请换一个更具体的问题，或补充更明确的知识库资料后再试。"  # 定义引用校验失败时的拒答提示语，避免返回没有资料依据的答案


def get_confidence_level(
    best_score: float | None,
) -> str:  # 定义根据最高分判断置信度等级的函数
    if best_score is None:  # 判断是否没有可用分数
        return "low"  # 如果没有分数，说明没有可信检索结果，返回低置信度

    if best_score >= HIGH_CONFIDENCE_SCORE:  # 判断最高分是否达到高置信度阈值
        return "high"  # 如果达到高置信度阈值，返回 high

    if best_score >= MIN_RELEVANCE_SCORE:  # 判断最高分是否达到最低回答阈值
        return "medium"  # 如果达到最低阈值但没有达到高阈值，返回 medium

    return "low"  # 如果低于最低阈值，返回 low


@router.post(
    "/knowledge-bases/{knowledge_base_id}/rag/chat", response_model=RagChatResponse
)  # 注册 RAG 问答接口
def rag_chat(  # 定义 RAG 问答接口函数
    knowledge_base_id: int,  # 接收路径参数 knowledge_base_id，表示要基于哪个知识库问答
    rag_data: RagChatRequest,  # 接收请求体，里面包含 session_id、question 和 top_k
    session: Session = Depends(
        get_session
    ),  # 注入数据库会话，用来查询知识库、会话和消息
    current_user=Depends(get_current_user),  # 注入当前登录用户，用来做权限校验
):  # 结束函数参数定义
    knowledge_base_statement = select(KnowledgeBase).where(  # 构建查询知识库的 SQL 语句
        KnowledgeBase.id
        == knowledge_base_id  # 根据路径里的 knowledge_base_id 查询知识库
    )  # 结束知识库查询语句构建

    knowledge_base = session.exec(
        knowledge_base_statement
    ).first()  # 执行查询，并取出第一条知识库记录

    if knowledge_base is None:  # 判断知识库是否不存在
        raise HTTPException(
            status_code=404, detail="知识库不存在"
        )  # 如果知识库不存在，返回 404 错误

    if not can_view_project(  # 判断当前用户是否可以查看该知识库所属项目空间
        session=session,  # 传入数据库会话
        project_id=knowledge_base.project_id,  # 使用知识库的 project_id 判断项目权限
        user=current_user,  # 传入当前登录用户
    ):  # 权限判断结束
        raise HTTPException(  # 如果没有查看权限
            status_code=404,  # 返回 404，避免泄露知识库是否真实存在
            detail="知识库不存在或无权访问",  # 返回错误提示
        )  # HTTPException 结束

    chat_session_statement = select(ChatSession).where(  # 构建查询聊天会话的 SQL 语句
        ChatSession.id == rag_data.session_id  # 根据请求体里的 session_id 查询聊天会话
    )  # 结束聊天会话查询语句构建

    chat_session = session.exec(
        chat_session_statement
    ).first()  # 执行查询，并取出第一条聊天会话记录

    if chat_session is None:  # 判断聊天会话是否不存在
        raise HTTPException(
            status_code=404, detail="聊天会话不存在"
        )  # 如果会话不存在，返回 404 错误

    if not can_view_project(  # 判断当前用户是否可以查看该会话所属项目空间
        session=session,  # 传入数据库会话
        project_id=chat_session.project_id,  # 使用会话的 project_id 判断项目权限
        user=current_user,  # 传入当前登录用户
    ):  # 权限判断结束
        raise HTTPException(  # 如果没有查看权限
            status_code=404,  # 返回 404，避免泄露会话是否真实存在
            detail="聊天会话不存在或无权访问",  # 返回错误提示
        )  # HTTPException 结束

    if (
        chat_session.project_id != knowledge_base.project_id
    ):  # 判断当前会话和知识库是否不属于同一个项目空间
        raise HTTPException(  # 如果跨项目混用会话和知识库，就拒绝请求
            status_code=400,  # 400 表示请求参数组合不合法
            detail="当前聊天会话和知识库不属于同一个项目空间",  # 返回错误提示
        )  # HTTPException 结束

    question = rag_data.question.strip()  # 去掉用户问题前后的空白字符

    if not question:  # 判断用户问题是否为空
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=400,  # 400 表示请求参数不合法
            detail="问题不能为空",  # 返回问题为空的提示
        )  # HTTPException 结束

    validate_prompt_security(  # 检查用户问题是否包含明显 Prompt Injection 攻击内容
        question  # 只检查用户原始问题，不检查知识库内容和系统 prompt
    )  # 提示词安全检查结束，命中危险内容会直接返回 400

    top_k = rag_data.top_k  # 读取用户传入的 top_k

    if top_k <= 0:  # 判断 top_k 是否小于等于 0
        raise HTTPException(
            status_code=400, detail="top_k 必须大于 0"
        )  # 如果 top_k 不合法，返回 400 错误
    check_rate_limit(  # 检查当前用户调用 RAG 问答接口是否过于频繁
        user_id=current_user.id,  # 使用当前登录用户 ID 做限流维度
        action="rag_chat",  # RAG 问答接口使用 rag_chat 限流规则
    )  # 限流检查结束，超过限制会直接返回 429
    search_history_messages = get_recent_messages(  # 读取用于检索增强的最近历史消息
        session=session,  # 传入当前数据库会话
        chat_session_id=chat_session.id,  # 传入当前聊天会话 ID
        limit=SEARCH_HISTORY_LIMIT,  # 只读取少量历史，避免检索问题过长
    )  # 结束检索历史读取

    recent_search_history_context = build_history_context(  # 把检索用最近历史消息拼成文本，拼成大概这种：用户：Day8 的目标是什么？
        search_history_messages,  # 传入检索用历史消息
        max_message_length=150,  # 每条检索历史最多保留 150 字符
    )  # 结束最近检索历史上下文构建

    search_history_context = build_search_history_context(  # 构建最终检索用历史上下文，把长期摘要和最近对话拼成检索用历史上下文
        conversation_summary=chat_session.conversation_summary,  # 传入当前会话长期历史摘要
        recent_history_context=recent_search_history_context,  # 传入最近几条历史消息
    )  # 结束检索历史上下文构建

    search_question = build_search_question(  # 构建真正用于检索的 question
        question=question,  # 传入当前用户问题
        history_context=search_history_context,  # 传入长期摘要 + 最近历史
    )  # 结束检索问题构建

    top_results = search_top_chunks(  # 调用统一检索服务，获取 top-k 相关 chunks
        session=session,  # 传入当前数据库会话
        knowledge_base_id=knowledge_base_id,  # 传入当前知识库 ID
        question=search_question,  # 传入增强后的检索问题
        top_k=top_k,  # 传入要返回的 chunks 数量
        min_score=MIN_RELEVANCE_SCORE,  # 传入最低相关度阈值，过滤掉 final_score 过低的 chunks
    )  # 结束 top-k 检索

    if not top_results:  # 判断是否没有任何 chunk 达到最低相关度阈值
        return RagChatResponse(  # 返回 RAG 问答响应
            question=question,  # 返回用户原始问题
            answer=RAG_NO_RELEVANT_CONTENT_ANSWER,  # 返回低相关度拒答提示
            confidence_level="low",  # 没有可信检索结果时，置信度固定为 low
            citations=[],  # 没有可信引用来源，所以返回空列表
        )  # 结束拒答响应返回
    best_score = get_result_score(  # 调用统一分数读取函数
        top_results[0]  # 传入排名第一的检索结果
    )  # 得到优先使用 rerank_score 的置信分数

    confidence_level = get_confidence_level(best_score)  # 根据最高分计算回答置信度等级
    context = build_context_from_search_results(
        top_results
    )  # 把 top-k chunks 拼接成知识库资料 context

    answer_history_messages = get_recent_messages(  # 读取用于回答生成的最近历史消息
        session=session,  # 传入当前数据库会话
        chat_session_id=chat_session.id,  # 传入当前聊天会话 ID
        limit=ANSWER_HISTORY_LIMIT,  # 读取最近几轮历史，帮助 LLM 理解上下文
    )  # 结束回答历史读取

    answer_history_context = build_history_context(  # 把回答用历史消息拼成文本，拼成大概这种：用户：Day8 的目标是什么？
        answer_history_messages,  # 传入回答用历史消息
        max_message_length=300,  # 每条回答历史最多保留 300 字符
    )  # 结束回答历史上下文构建

    prompt = build_rag_prompt(  # 构建最终 RAG prompt
        question=question,  # 传入当前用户问题
        context=context,  # 传入知识库检索出来的资料
        history_context=answer_history_context,  # 传入最近对话历史
        conversation_summary=chat_session.conversation_summary,  # 传入长期历史摘要
    )  # 结束 prompt 构建

    citations = [  # 创建 citations 引用来源列表，列表推导式[要放进列表的内容 for 变量 in 可遍历对象 if 条件]
        RagCitation(  # 创建单个引用来源对象
            source_index=source_index,  # 设置引用序号，例如资料 1、资料 2
            chunk_id=result["chunk_id"],  # 设置引用 chunk ID
            document_id=result["document_id"],  # 设置引用文档 ID
            document_name=result["document_name"],  # 设置引用文档名称
            chunk_index=result["chunk_index"],  # 设置引用 chunk 序号
            vector_score=result["vector_score"],  # 设置向量相似度分数
            keyword_score=result["keyword_score"],  # 设置关键词命中加分
            hybrid_score=result.get(  # 设置混合检索综合分数
                "hybrid_score",  # 优先读取新的 hybrid_score
                result["final_score"],  # 如果没有 hybrid_score，就使用旧的 final_score
            ),  # 结束 hybrid_score 设置
            final_score=result[
                "final_score"
            ],  # 保留旧字段，避免旧前端或旧接口依赖时报错
            rerank_score=get_result_score(
                result
            ),  # 设置 Rerank 精排分数，优先使用 rerank_score
            content=result["content"],  # 设置完整引用内容
            preview=build_citation_preview(result["content"]),  # 设置短引用预览文本
        )  # 结束 RagCitation 对象创建
        for source_index, result in enumerate(
            top_results, start=1
        )  # 遍历 top_results，同时生成从 1 开始的引用序号
    ]  # 结束 citations 列表创建
    valid_source_indexes = (
        [  # 创建本次有效资料编号列表，用来校验 answer 中的 [资料 X] 是否真实存在
            citation.source_index  # 取出当前 citation 的 source_index，例如 1、2、3
            for citation in citations  # 遍历本次返回的所有 citations
        ]
    )  # 结束有效资料编号列表创建
    answer = call_llm_with_prompt(
        prompt
    )  # 调用 LLM，让模型根据 RAG prompt 生成最终答案
    citation_valid = (
        validate_answer_citations(  # 校验 LLM 生成的答案是否包含有效引用编号
            answer=answer,  # 传入 LLM 生成的答案文本
            valid_source_indexes=valid_source_indexes,  # 传入本次允许引用的资料编号列表
        )
    )  # 结束引用校验
    if not citation_valid:  # 判断答案是否没有通过引用校验
        return RagChatResponse(  # 返回 RAG 问答响应
            question=question,  # 返回用户原始问题
            answer=RAG_CITATION_VALIDATION_FAILED_ANSWER,  # 返回引用校验失败的拒答提示
            confidence_level="low",  # 引用校验失败时，置信度设为 low
            citations=citations,  # 仍然返回检索到的 citations，方便前端展示系统参考过哪些资料
        )  # 结束引用校验失败响应返回
    user_message = ChatMessage(  # 创建用户消息对象，准备保存到 chat_messages 表
        session_id=chat_session.id,  # 设置消息所属聊天会话 ID
        role="user",  # 设置消息角色为 user
        content=question,  # 保存用户本次问题
        tokens=0,  # 暂时设置 tokens 为 0，后面可以再做 token 统计
    )  # 结束用户消息创建

    assistant_message = ChatMessage(  # 创建助手消息对象，准备保存到 chat_messages 表
        session_id=chat_session.id,  # 设置消息所属聊天会话 ID
        role="assistant",  # 设置消息角色为 assistant
        content=answer,  # 保存 LLM 生成的答案
        tokens=0,  # 暂时设置 tokens 为 0
    )  # 结束助手消息创建

    session.add(user_message)  # 把用户消息加入数据库会话
    session.add(assistant_message)  # 把助手消息加入数据库会话
    session.commit()  # 提交数据库事务，保存本轮问答消息

    try:  # 尝试更新长期历史摘要
        update_conversation_summary_if_needed(  # 调用按需更新会话历史摘要的 service 函数
            session=session,  # 传入当前数据库会话
            chat_session=chat_session,  # 传入当前聊天会话对象
            trigger_message_count=SUMMARY_TRIGGER_MESSAGE_COUNT,  # 传入摘要触发消息数量
            keep_recent_messages=SUMMARY_KEEP_RECENT_MESSAGES,  # 传入需要保留的最近消息数量
        )  # 结束历史摘要更新调用
    except Exception as error:  # 捕获摘要更新过程中的异常
        logger.exception(
            "历史摘要更新失败：%s", error
        )  # 记录异常，但不中断本轮 RAG 响应

    return RagChatResponse(  # 返回 RAG 问答响应
        question=question,  # 返回用户原始问题
        answer=answer,  # 返回模型生成的答案
        confidence_level=confidence_level,  # 返回根据最高检索分数计算出的置信度等级
        citations=citations,  # 返回引用来源列表
    )  # 结束响应返回
