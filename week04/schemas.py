from datetime import datetime  # 导入日期时间类型用于响应中的时间字段
from typing import (
    Any,
    Optional,
    List,
    TypedDict,
    Literal,
)  # 导入 Any 类型用于表示任意工具结果,导入 Optional，用来表示某些字段可以为空
from sqlmodel import Field  # 导入 SQLModel 模型基类和字段配置工具
from pydantic import BaseModel  # 导入 Pydantic 基类用于定义请求和响应模型

class UserRegister(BaseModel):  # 定义用户注册请求数据结构
    username: str  # 注册用户名
    password: str  # 注册密码明文


class UserLogin(BaseModel):  # 定义用户登录请求数据结构
    username: str  # 登录用户名
    password: str  # 登录密码明文


class UserResponse(BaseModel):  # 定义返回给客户端的用户信息结构
    id: int  # 用户 ID
    username: str  # 用户名
    created_at: datetime  # 用户创建时间
    updated_at: datetime  # 用户更新时间


class TokenResponse(BaseModel):  # 定义登录成功后的令牌响应结构
    access_token: str  # JWT 访问令牌
    token_type: str  # 令牌类型，通常为 bearer


class ChatSessionCreate(BaseModel):  # 定义创建聊天会话的请求模型
    project_id: int = Field(  # 项目空间 ID，表示这个会话属于哪个项目空间
        gt=0,  # project_id 必须大于 0，避免传入无效 ID
        description="所属项目空间 ID",  # Swagger 文档中的字段说明
    )  # 结束 project_id 字段定义

    title: str | None = Field(  # 会话标题，可以为空
        default=None,  # 默认 None，表示用户不传时后端自动使用默认标题
        max_length=200,  # 限制标题最长 200 个字符
        description="会话标题",  # Swagger 文档中的字段说明
    )  # 结束 title 字段定义


class ChatSessionResponse(BaseModel):  # 定义聊天会话响应结构
    id: int  # 会话 ID
    user_id: int  # 会话所属用户 ID
    project_id: int  # 所属项目空间 ID
    title: str  # 会话标题
    created_at: datetime  # 会话创建时间
    updated_at: datetime  # 会话更新时间


class ChatMessageCreate(BaseModel):  # 定义创建聊天消息的请求结构
    session_id: int  # 消息所属会话 ID
    role: str  # 消息角色
    content: str  # 消息正文


class ChatMessageResponse(BaseModel):  # 定义聊天消息响应结构
    id: int  # 消息 ID
    session_id: int  # 消息所属会话 ID
    role: str  # 消息角色
    content: str  # 消息正文
    created_at: datetime  # 消息创建时间


class ChatResponse(BaseModel):  # 定义发送消息接口的完整响应结构
    user_message: ChatMessageResponse  # 保存后的用户消息
    assistant_message: ChatMessageResponse  # 保存后的助手消息
    tool_result: dict[str, Any] | None = None  # 工具调用结果，未调用工具时为空


class KnowledgeBaseCreate(BaseModel):  # 定义创建知识库时前端需要提交的数据结构
    project_id: int = Field(  # 项目空间 ID，表示这个知识库要创建在哪个项目空间下面
        gt=0,  # project_id 必须大于 0，避免传入 0 或负数这种无效 ID
        description="所属项目空间 ID",  # Swagger 文档中显示的字段说明
    )  # 结束 project_id 字段定义

    name: str = Field(  # 知识库名称，由前端传入
        min_length=1,  # 名称最少 1 个字符，避免空字符串
        max_length=100,  # 名称最多 100 个字符，和数据库模型保持一致
        description="知识库名称",  # Swagger 文档中显示的字段说明
    )  # 结束 name 字段定义

    description: str | None = Field(  # 知识库描述，可以为空
        default=None,  # 默认值为 None，表示可以不填写描述
        max_length=500,  # 描述最多 500 个字符，和数据库模型保持一致
        description="知识库描述",  # Swagger 文档中显示的字段说明
    )  # 结束 description 字段定义


class KnowledgeBaseRead(BaseModel):  # 定义创建成功后返回给前端的数据结构
    id: int  # 知识库 ID，由数据库自动生成
    project_id: int  # 所属项目空间 ID
    name: str  # 知识库名称
    description: Optional[str] = None  # 知识库描述，可能为空
    user_id: int  # 创建该知识库的用户 ID
    created_at: datetime  # 知识库创建时间
    updated_at: datetime  # 知识库更新时间


class DocumentRead(BaseModel):  # 定义文档响应模型，用来规定接口返回给前端的文档数据结构
    id: int  # 文档 ID，由数据库自动生成
    knowledge_base_id: int  # 文档所属的知识库 ID
    filename: str  # 文档原始文件名，例如 AI应用开发6周学习计划.pdf
    file_type: str  # 文件类型，例如 pdf、docx、md、html、txt
    file_path: str  # 文件保存在服务器上的路径
    file_size: int  # 文件大小，单位是字节
    status: str  # 文档状态，例如 uploaded、parsed、failed、indexed
    error_message: Optional[str] = None  # 错误信息，如果文档处理失败就保存失败原因
    created_at: datetime  # 文档创建时间
    updated_at: datetime  # 文档更新时间


class DocumentChunkRead(
    BaseModel
):  # 定义文档文本块响应模型，用来规定 chunks 接口返回给前端的数据结构
    id: int  # 文本块 ID，由数据库自动生成
    document_id: int  # 当前文本块所属的文档 ID
    chunk_index: int  # 当前文本块在这个文档中的序号，通常从 0 开始
    content: str  # 文本块正文内容，也就是从文档里解析并切分出来的一小段文本
    page_number: Optional[int] = None  # 文本块来源页码，如果暂时没有页码信息就为 None
    token_count: int  # 当前文本块的大致 token 数，后面控制上下文长度时会用到
    embedding_json: Optional[str] = (
        None  # 当前 chunk 的 embedding JSON 字符串，未索引时为 None
    )
    created_at: datetime  # 文本块创建时间
    updated_at: datetime  # 文本块更新时间


class DocumentIndexResponse(BaseModel):  # 定义文档索引接口的响应模型，用来返回索引结果
    document_id: int  # 当前被索引的文档 ID
    chunk_count: int  # 当前文档一共有多少个 chunks
    indexed_count: int  # 本次成功生成 embedding 并保存的 chunks 数量
    status: str  # 文档当前状态，例如 indexed
    message: str  # 返回给前端看的提示信息


class KnowledgeBaseSearchRequest(BaseModel):  # 定义知识库检索接口的请求体模型
    question: str  # 用户输入的问题，例如“Day8 要学习什么？”
    top_k: int = 3  # 返回最相关的前几个 chunks，默认返回前 3 个


class ChunkSearchResult(BaseModel):  # 定义单个 chunk 检索结果的响应结构
    chunk_id: int  # 当前命中的 chunk ID
    document_id: int  # 当前 chunk 所属的文档 ID
    document_name: str  # 当前 chunk 所属文档的原始文件名
    chunk_index: int  # 当前 chunk 在文档中的序号
    content: str  # 当前 chunk 的正文内容
    vector_score: float  # 当前 chunk 和用户问题的向量相似度分数
    keyword_score: float  # 当前 chunk 和用户问题的关键词命中加分
    hybrid_score: float  # 混合检索综合分数，后续主要用于排序、过滤和解释检索结果
    final_score: float  # 兼容旧字段，当前通常等于 hybrid_score
    rerank_score: float | None = (
        None  # Rerank 精排分数，用来展示当前 chunk 经过二次排序后的最终质量分
    )
    original_question: str | None = None  # 用户原始问题，用于调试 query rewrite 效果
    search_question: str | None = None  # 改写后的检索问题，用于观察最终进入检索的问题


class KnowledgeBaseSearchResponse(BaseModel):  # 定义知识库检索接口的完整响应结构
    question: str  # 返回用户原始问题
    top_k: int  # 返回本次实际使用的 top_k
    results: List[ChunkSearchResult]  # 返回最相关的 chunks 列表


class RagChatRequest(BaseModel):  # 定义 RAG 问答接口的请求体模型
    session_id: int  # 当前 RAG 问答所属的聊天会话 ID，用来读取和保存多轮对话历史
    question: str  # 用户输入的问题，例如“Day8 要学习什么？”
    top_k: int = 3  # 检索最相关的前几个 chunks，默认取前 3 个


class RagCitation(BaseModel):  # 定义 RAG 引用来源响应结构
    source_index: int  # 引用资料编号，对应 answer 里的 [资料 1]、[资料 2]

    chunk_id: int  # 被引用的 chunk 在 document_chunks 表里的 ID

    document_id: int  # 被引用 chunk 所属文档 ID

    document_name: str  # 被引用 chunk 所属文档名称，方便前端展示来源文件

    chunk_index: int  # 被引用 chunk 在原文档中的切块序号

    vector_score: float  # 向量相似度分数，表示语义相关度

    keyword_score: float  # 关键词命中分数，表示关键词匹配程度

    hybrid_score: float  # 混合检索综合分数，用来解释初筛排序

    final_score: float  # 兼容旧字段，当前通常等于 hybrid_score

    rerank_score: float | None = (
        None  # Rerank 精排分数，用来展示该引用资料最终进入上下文的排序依据
    )

    content: str  # 完整引用内容，前端需要展开查看时使用

    preview: str  # 引用内容预览，前端列表展示时使用


class RagChatResponse(BaseModel):  # 定义 RAG 问答接口的响应体模型
    question: str  # 返回用户原始问题，方便前端展示本次问答对应的问题
    answer: str  # LLM 基于知识库 context 生成的最终答案
    confidence_level: str  # 返回回答置信度等级，例如 high、medium、low
    citations: List[RagCitation]  # 当前答案引用的知识库片段列表


class RagEvalCaseCreate(BaseModel):  # 定义创建 RAG 评测用例的请求体
    question: str  # 评测问题，例如“Day8 的目标是什么？”
    expected_answer: str = ""  # 参考答案，用来记录这道题的标准回答
    expected_keywords: str = (
        ""  # 期望命中的关键词，使用逗号分隔，例如 Day8,embedding,相似度检索
    )
    expected_document_name: str = (
        ""  # 期望命中的文档名称，用来判断 citations 是否命中正确文档
    )
    should_refuse: bool = False  # 是否期望系统拒答，True 表示这个问题不应该被知识库回答


class RagEvalCaseResponse(BaseModel):  # 定义 RAG 评测用例响应结构
    id: int  # 评测用例 ID
    knowledge_base_id: int  # 所属知识库 ID
    question: str  # 评测问题
    expected_answer: str  # 参考答案
    expected_keywords: str  # 期望关键词
    expected_document_name: str  # 期望命中的文档名称
    should_refuse: bool  # 是否期望拒答
    created_at: datetime  # 创建时间
    updated_at: datetime  # 更新时间


class RagEvalCaseListResponse(BaseModel):  # 定义 RAG 评测用例列表响应结构
    total: int  # 当前知识库下评测用例总数量
    items: list[RagEvalCaseResponse]  # 评测用例列表


class RagEvalSingleRunResponse(BaseModel):  # 定义单条 RAG 评测运行结果响应结构
    case_id: int  # 当前运行的评测用例 ID

    knowledge_base_id: int  # 当前评测所属知识库 ID

    question: str  # 本次评测问题

    expected_answer: str  # 参考答案

    actual_answer: str  # RAG 实际返回的答案或者拒答提示

    should_refuse: bool  # 这道题是否期望系统拒答

    actual_refused: bool  # 系统本次是否实际拒答

    confidence_level: str  # 本次回答置信度，例如 high、medium、low

    expected_keywords: str  # 期望命中的关键词字符串

    matched_keywords: list[str]  # 实际命中的关键词列表

    missing_keywords: list[str]  # 没有命中的关键词列表

    hit_expected_keywords: (
        bool  # 是否命中所有期望关键词，如果没有设置关键词则默认为 True
    )

    expected_document_name: str  # 期望命中的文档名

    hit_expected_document: (
        bool  # citations 是否命中期望文档，如果没有设置期望文档则默认为 True
    )

    citation_valid: bool  # answer 是否包含有效 [资料 X] 引用，拒答题可视为 True

    passed: bool  # 本条评测是否通过

    notes: str  # 本次评测结果说明

    citations: list[RagCitation]  # 本次 RAG 检索返回的引用来源列表


class RagEvalBatchRunResponse(BaseModel):  # 定义批量 RAG 评测运行结果响应结构
    knowledge_base_id: int  # 当前评测所属知识库 ID
    total: int  # 本次运行的评测用例总数
    passed_count: int  # 通过的评测用例数量
    failed_count: int  # 未通过的评测用例数量
    hit_rate: float  # 评测通过率，例如 0.8 表示 80%
    items: list[RagEvalSingleRunResponse]  # 每一条评测用例的详细运行结果


class RagEvalRunResponse(BaseModel):  # 定义 RAG 批量评测运行记录响应结构
    id: int  # 评测运行记录 ID

    knowledge_base_id: int  # 所属知识库 ID

    total: int  # 本次评测总题数

    passed_count: int  # 本次评测通过数量

    failed_count: int  # 本次评测失败数量

    hit_rate: float  # 本次评测通过率，例如 0.8 表示 80%

    created_at: datetime  # 本次评测运行时间


class RagEvalRunListResponse(BaseModel):  # 定义 RAG 历史评测运行列表响应结构
    total: int  # 历史评测运行总数量

    items: list[RagEvalRunResponse]  # 历史评测运行记录列表


class RagEvalResultResponse(BaseModel):  # 定义单条历史评测结果响应结构
    id: int  # 评测结果 ID

    eval_run_id: int  # 所属评测运行 ID

    eval_case_id: int  # 所属评测用例 ID

    knowledge_base_id: int  # 所属知识库 ID

    question: str  # 本次评测问题快照

    expected_answer: str  # 参考答案快照

    actual_answer: str  # 实际答案或者拒答提示

    should_refuse: bool  # 是否期望拒答

    actual_refused: bool  # 是否实际拒答

    confidence_level: str  # 本次回答置信度

    expected_keywords: str  # 期望关键词

    matched_keywords: str  # 命中的关键词字符串

    missing_keywords: str  # 缺失的关键词字符串

    hit_expected_keywords: bool  # 是否命中期望关键词

    expected_document_name: str  # 期望命中文档名

    hit_expected_document: bool  # 是否命中期望文档

    citation_valid: bool  # 引用校验是否通过

    passed: bool  # 本题是否通过

    notes: str  # bad case 说明

    citations_json: str  # citations 的 JSON 字符串快照

    created_at: datetime  # 结果保存时间


class RagEvalRunDetailResponse(BaseModel):  # 定义某次评测运行详情响应结构
    run: RagEvalRunResponse  # 本次评测运行总览信息

    results: list[RagEvalResultResponse]  # 本次评测中每一道题的详细结果


class AgentChatRequest(BaseModel):  # 定义 Agent 聊天接口的请求体
    message: str  # 用户输入的问题
    knowledge_base_id: int | None = None  # 用户选择的知识库 ID，可以不传
    session_id: int | None = None  # 当前聊天会话 ID，可以不传
    top_k: int = 5  # RAG 检索数量，默认返回 5 条 chunk

class AgentChatResponse(BaseModel):  # 定义 Agent 聊天接口响应体
    answer: str  # Agent 最终回答，普通聊天返回普通回答，报告任务第一次请求返回确认提示

    task_type: str  # Agent 判断出来的任务类型，例如 normal_chat、rag_chat、report

    context: str | None = None  # Agent 检索到的上下文，普通聊天时可以为空

    citations: list[dict[str, Any]] = Field(default_factory=list)  # Agent 引用来源列表，默认空列表

    steps: list[str] = Field(default_factory=list)  # Agent 执行步骤列表，默认空列表

    saved_result_id: int | None = None  # AgentRun 保存到数据库后的记录 ID

    task_id: int | None = None  # 等待确认任务 ID，report 任务进入 waiting_approval 时会返回

    task_status: str | None = None  # 任务状态，例如 waiting_approval、success、failed、rejected

    report_title: str | None = None  # 报告标题，只有报告任务生成正式报告后才会有值

    report_content: str | None = None  # 报告正文，只有报告任务生成正式报告后才会有值

    report_id: int | None = None  # 报告保存到 reports 表后的报告 ID

    markdown_file_path: str | None = None  # 报告导出的 Markdown 文件路径


class AgentTaskActionResponse(
    BaseModel
):  # 定义 Agent 任务操作响应体，用于 approve 和 reject 接口
    success: bool  # 表示本次任务操作是否成功，例如确认成功、拒绝成功

    task_id: int | None = None  # 返回任务 ID，如果任务不存在则可以为空

    task_status: str | None = (
        None  # 返回任务当前状态，例如 waiting_approval、running、success、failed、rejected
    )

    answer: str = (
        ""  # 返回给用户看的提示内容，确认成功时可以是报告正文，拒绝时可以是拒绝提示
    )

    report_id: int | None = None  # 返回生成后的报告 ID，只有确认并成功生成报告后才有值

    markdown_file_path: str | None = (
        None  # 返回导出的 Markdown 文件路径，只有确认并成功导出后才有值
    )

    steps: list[str] = Field(
        default_factory=list
    )  # 返回本次接口执行的步骤列表，默认空列表

    error: str | None = None  # 返回错误信息，成功时为空，失败时保存失败原因


class AgentTaskSummaryResponse(
    BaseModel
):  # 定义 Agent 任务摘要响应体，用于返回失败任务列表中的单条任务
    id: int  # 返回任务 ID

    task_type: str  # 返回任务类型，例如 report、rag_chat、normal_chat

    status: str  # 返回任务状态，例如 failed、success、waiting_approval

    user_input: str  # 返回用户原始输入

    retry_count: int  # 返回当前任务已经重试的次数

    max_retries: int  # 返回当前任务最多允许重试的次数

    error: str | None = None  # 返回任务失败原因，成功任务一般为空

    failed_at: datetime | None = None  # 返回任务失败时间，没有失败时为空

    last_retry_at: datetime | None = None  # 返回最后一次重试时间，没有重试过时为空

    created_at: datetime  # 返回任务创建时间


class AgentTaskCreateRequest(BaseModel):  # 定义创建后台 Agent 任务的请求体
    task_type: str = (
        "report"  # 任务类型，当前先支持 report，后面可以扩展 rag_chat、export_pdf 等
    )

    message: str  # 用户输入的任务内容，例如“请根据知识库生成一份 Redis 学习报告”

    knowledge_base_id: int | None = None  # 知识库 ID，可以为空；report 任务一般需要传

    session_id: int | None = None  # 会话 ID，可以为空，用来关联聊天会话


class AgentTaskCreateResponse(BaseModel):  # 定义创建后台 Agent 任务的响应体
    success: bool  # 表示后台任务是否创建成功

    task_id: int | None = None  # 返回创建出来的 AgentTask ID，创建失败时可以为空

    task_status: str | None = None  # 返回任务当前状态，例如 queued、failed

    job_id: str | None = None  # 返回 RQ Job ID，用来关联 Redis Queue 里的后台任务

    message: str = ""  # 返回给用户看的提示信息

    error: str | None = None  # 返回错误信息，成功时为空


class AgentTaskDetailResponse(BaseModel):  # 定义 Agent 后台任务详情响应体
    success: bool  # 表示本次查询是否成功

    task_id: int | None = None  # 返回任务 ID，如果任务不存在则为空

    task_type: str | None = None  # 返回任务类型，例如 report、rag_chat、normal_chat

    task_status: str | None = (
        None  # 返回任务状态，例如 queued、running、success、failed、cancelled
    )

    progress: int = 0  # 返回任务进度，范围是 0 到 100

    current_step: str = ""  # 返回当前任务执行步骤说明，例如正在检索知识库

    user_input: str = ""  # 返回用户创建任务时输入的原始内容

    answer: str = ""  # 返回任务最终答案，任务未完成时通常为空字符串

    report_id: int | None = None  # 返回报告 ID，只有报告生成成功后才有值

    markdown_file_path: str | None = (
        None  # 返回 Markdown 文件路径，只有导出成功后才有值
    )

    job_id: str | None = None  # 返回 RQ Job ID，用来关联 Redis Queue 里的任务

    error: str | None = None  # 返回任务错误信息，成功时为空

    queued_at: datetime | None = None  # 返回任务入队时间，任务未入队时为空

    started_at: datetime | None = None  # 返回 Worker 开始执行时间，任务未开始时为空

    finished_at: datetime | None = None  # 返回任务结束时间，任务未结束时为空

    created_at: datetime | None = None  # 返回任务创建时间

    updated_at: datetime | None = None  # 返回任务最后更新时间

    message: str = ""  # 返回给用户看的提示信息


class AgentTaskEventItem(
    BaseModel
):  # 定义单个 Agent 任务事件响应体，对应数据库里的一条 AgentStep
    step_id: int | None = None  # 返回步骤 ID，对应 AgentStep.id

    task_id: int  # 返回任务 ID，对应 AgentStep.task_id，表示这个步骤属于哪个任务

    step_name: str  # 返回步骤名称，例如 queue_task、retrieve_knowledge、generate_report

    step_type: str  # 返回步骤类型，例如 queue、worker、tool、system、validation

    status: str  # 返回步骤状态，例如 success、failed、running、waiting_approval

    input_data: dict[str, Any] = Field(
        default_factory=dict
    )  # 返回步骤输入数据，默认是空字典

    output_data: dict[str, Any] = Field(
        default_factory=dict
    )  # 返回步骤输出数据，默认是空字典

    error: str | None = None  # 返回步骤错误信息，成功时为空

    retry_count: int = 0  # 返回当前步骤对应的重试次数，默认是 0

    is_retry: bool = False  # 返回这个步骤是否属于重试过程，默认不是重试

    started_at: datetime | None = None  # 返回步骤开始时间，可以为空

    finished_at: datetime | None = None  # 返回步骤结束时间，可以为空

    created_at: datetime | None = None  # 返回步骤记录创建时间


class AgentTaskEventsResponse(BaseModel):  # 定义 Agent 任务事件列表响应体
    success: bool  # 表示本次事件查询是否成功

    task_id: int | None = None  # 返回任务 ID，任务不存在时可以为空

    task_status: str | None = (
        None  # 返回任务当前状态，例如 queued、running、success、failed
    )

    total: int = 0  # 返回事件总数，也就是 AgentStep 的数量

    events: list[AgentTaskEventItem] = Field(
        default_factory=list
    )  # 返回任务事件列表，默认是空列表

    message: str = ""  # 返回给用户看的提示信息

    error: str | None = None  # 返回错误信息，成功时为空


class AgentTaskCancelResponse(BaseModel):  # 定义取消 Agent 后台任务的响应体
    success: bool  # 表示本次取消操作是否成功

    task_id: int | None = None  # 返回任务 ID，如果任务不存在则为空

    task_status: str | None = (
        None  # 返回任务当前状态，例如 cancelled、running、success、failed
    )

    message: str = ""  # 返回给用户或前端看的提示信息

    error: str | None = None  # 返回错误信息，取消成功时为空

class BadCaseCreateRequest(BaseModel):  # 定义创建 bad case 的请求体模型
    reason: str  # bad case 原因，例如回答错误、引用错误、格式错误

    expected_answer: str | None = None  # 期望答案，可以不传

    category: str = "unknown"  # bad case 分类，默认 unknown

    severity: str = "medium"  # 严重程度，默认 medium

    feedback_source: str = "developer"  # 反馈来源，默认 developer

    prompt_name: str | None = (
        None  # prompt 名称，可以不传，不传时系统尝试自动从 llm_calls 提取
    )

    prompt_version: str | None = (
        None  # prompt 版本，可以不传，不传时系统尝试自动从 llm_calls 提取
    )


class AgentState(TypedDict, total=False):  # 定义 Agent 工作流状态类型
    user_input: str  # 用户原始输入

    task_type: str  # 任务类型，例如 normal_chat、rag_chat、report

    knowledge_base_id: int | None  # 知识库 ID

    session_id: int | None  # 会话 ID

    top_k: int  # RAG 检索数量

    context: str  # RAG 检索上下文

    citations: list[dict[str, Any]]  # RAG 引用来源

    answer: str  # 最终回答

    task_id: int | None  # AgentTask ID

    step_id: int | None  # AgentStep ID

    task_status: str | None  # AgentTask 状态，例如 waiting_approval、completed、failed

    steps: list[str]  # 执行步骤

    saved_result_id: int | None  # AgentRun 保存结果 ID

    report_id: int | None  # 报告 ID

    report_title: str  # 报告标题

    report_content: str  # 报告正文或草稿

    markdown_file_path: str | None  # Markdown 文件路径

    error: str | None  # 错误信息


class ProjectSpaceCreateRequest(BaseModel):  # 定义创建项目空间的请求模型
    name: str = Field(  # 项目空间名称，由前端传入
        min_length=1,  # 名称最少 1 个字符，避免空字符串
        max_length=100,  # 名称最多 100 个字符，和数据库字段限制保持一致
        description="项目空间名称",  # Swagger 文档中显示的字段说明
    )  # 结束 name 字段定义

    description: str | None = Field(  # 项目空间描述，由前端传入，可以为空
        default=None,  # 默认值为 None，表示用户可以不填写描述
        max_length=500,  # 描述最多 500 个字符，和数据库字段限制保持一致
        description="项目空间描述",  # Swagger 文档中显示的字段说明
    )  # 结束 description 字段定义


class ProjectSpaceUpdateRequest(BaseModel):  # 定义更新项目空间的请求模型
    name: str | None = Field(  # 新的项目空间名称，可以不传
        default=None,  # 默认不修改名称
        min_length=1,  # 如果传了名称，最少 1 个字符
        max_length=100,  # 如果传了名称，最多 100 个字符
        description="新的项目空间名称",  # Swagger 文档中显示的字段说明
    )  # 结束 name 字段定义

    description: str | None = Field(  # 新的项目空间描述，可以不传
        default=None,  # 默认不修改描述
        max_length=500,  # 如果传了描述，最多 500 个字符
        description="新的项目空间描述",  # Swagger 文档中显示的字段说明
    )  # 结束 description 字段定义


class ProjectSpaceResponse(BaseModel):  # 定义项目空间响应模型，用来返回给前端
    id: int  # 项目空间 ID
    name: str  # 项目空间名称
    description: str | None  # 项目空间描述，可能为空
    owner_id: int  # 项目空间创建者 ID
    current_user_role: str | None = None  # 当前登录用户在该项目空间里的角色
    created_at: datetime  # 项目空间创建时间
    updated_at: datetime  # 项目空间更新时间


class ProjectSpaceListResponse(BaseModel):  # 定义项目空间列表响应模型
    total: int  # 当前用户可见的项目空间总数
    items: list[ProjectSpaceResponse]  # 项目空间列表

ProjectRoleLiteral = Literal[
    "admin", "member", "viewer"
]  # 定义项目角色类型，只允许 admin、member、viewer 三种字符串


class ProjectMemberAddRequest(BaseModel):  # 定义添加项目成员的请求模型
    user_id: int = Field(  # 要添加到项目空间的用户 ID
        gt=0,  # 用户 ID 必须大于 0，避免传入无效 ID
        description="要添加到项目空间的用户 ID",  # Swagger 文档中的字段说明
    )  # 结束 user_id 字段定义

    role: ProjectRoleLiteral = Field(  # 要给这个用户分配的项目角色
        default="viewer",  # 默认添加为 viewer，避免默认权限过高
        description="成员角色：admin / member / viewer",  # Swagger 文档中的字段说明
    )  # 结束 role 字段定义


class ProjectMemberUpdateRoleRequest(BaseModel):  # 定义修改项目成员角色的请求模型
    role: ProjectRoleLiteral = Field(  # 新的项目角色
        description="新的成员角色：admin / member / viewer",  # Swagger 文档中的字段说明
    )  # 结束 role 字段定义


class ProjectMemberResponse(BaseModel):  # 定义项目成员响应模型
    id: int  # 项目成员记录 ID
    project_id: int  # 项目空间 ID
    user_id: int  # 成员对应的用户 ID
    role: str  # 成员在项目空间里的角色
    created_at: datetime  # 成员加入项目的时间
    updated_at: datetime  # 成员记录最后更新时间


class ProjectMemberListResponse(BaseModel):  # 定义项目成员列表响应模型
    total: int  # 项目成员总数
    items: list[ProjectMemberResponse]  # 项目成员列表


class ProjectAdminOverviewResponse(BaseModel):  # 定义项目管理后台概览响应模型
    project_id: int  # 项目空间 ID
    project_name: str  # 项目空间名称
    current_user_role: str  # 当前用户在该项目空间里的角色，例如 admin/member/viewer
    member_count: int  # 当前项目空间成员数量
    knowledge_base_count: int  # 当前项目空间知识库数量
    document_count: int  # 当前项目空间文档数量
    chat_session_count: int  # 当前项目空间聊天会话数量
    can_write: bool  # 当前用户是否可以写入项目空间，例如创建知识库、上传文档
    can_manage: bool  # 当前用户是否可以管理项目空间，例如删除文档、管理成员
