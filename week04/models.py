from datetime import datetime  # 导入日期时间类型用于记录创建和更新时间
from enum import Enum  # 导入 Enum，用来定义固定选项，例如用户角色
from sqlalchemy import UniqueConstraint  # 导入唯一约束，用来限制同一个用户不能重复加入同一个项目
from typing import Optional, Any  #  导入 Optional，用来表示某些字段可以为空
from sqlalchemy import (
    Column,
    Text,
    JSON,
)  # 导入 Column 和 Text，用来定义长文本数据库字段
from sqlmodel import SQLModel, Field  # 导入 SQLModel 模型基类和字段配置工具


class User(SQLModel, table=True):  # 定义用户表模型
    __tablename__ = "users"  # 指定用户表在数据库中的表名

    id: int | None = Field(
        default=None, primary_key=True
    )  # 定义用户主键 ID，由数据库自动生成，创建对象时，id 可以是 None，保存到数据库后，id 就不是 None 了，数据库操作这个session.refresh()之后就生成id了
    username: str = Field(index=True)  # 定义用户名字段并创建索引方便查询
    hashed_password: str  # 保存哈希后的密码
    created_at: datetime = Field(default_factory=datetime.utcnow)  # 记录用户创建时间
    updated_at: datetime = Field(default_factory=datetime.utcnow)  # 记录用户更新时间

class ChatSession(SQLModel, table=True):  # 定义聊天会话表模型
    __tablename__ = "chat_sessions"  # 指定聊天会话表名

    id: int | None = Field(  # 会话 ID
        default=None,  # 默认 None，表示创建时由数据库自动生成
        primary_key=True,  # 设置为主键
    )  # 结束 id 字段定义

    title: str = Field(  # 会话标题
        default="新会话",  # 默认标题是“新会话”
        max_length=200,  # 限制标题最长 200 个字符
        index=True,  # 给标题加索引，方便后面搜索会话
    )  # 结束 title 字段定义

    user_id: int = Field(  # 创建这个会话的用户 ID
        foreign_key="users.id",  # 外键，指向 users 表
        index=True,  # 建立索引，方便查询某个用户创建的会话
    )  # 结束 user_id 字段定义

    project_id: int = Field(  # 当前会话所属的项目空间 ID
        foreign_key="project_spaces.id",  # 外键，指向 project_spaces 表
        index=True,  # 建立索引，方便查询某个项目空间下的所有会话
    )  # 结束 project_id 字段定义
    conversation_summary: Optional[str] = Field(
        default=None, sa_column=Column(Text)
    )  # 保存当前会话的长期历史摘要，历史太长时用摘要代替完整历史
    created_at: datetime = Field(default_factory=datetime.utcnow)  # 记录会话创建时间
    updated_at: datetime = Field(default_factory=datetime.utcnow)  # 记录会话更新时间


class ChatMessage(SQLModel, table=True):  # 定义聊天消息表模型
    __tablename__ = "chat_messages"  # 指定聊天消息表名

    id: int | None = Field(
        default=None, primary_key=True
    )  # 定义消息主键 ID，由数据库自动生成
    session_id: int = Field(
        foreign_key="chat_sessions.id", index=True
    )  # 关联所属聊天会话 ID 并建立索引
    role: str  # 保存消息角色，例如 user 或 assistant
    content: str  # 保存消息正文内容
    created_at: datetime = Field(default_factory=datetime.utcnow)  # 记录消息创建时间


class KnowledgeBase(SQLModel, table=True):  # 定义知识库表，用来保存一个知识库的基本信息
    __tablename__ = "knowledge_bases"  # 指定数据库表名为 knowledge_bases

    id: int | None = Field(default=None, primary_key=True)  # 知识库 ID，数据库会自动生成

    name: str = Field(  # 知识库名称，例如“产品需求知识库”
        index=True,  # 给知识库名称建立索引，方便后续按名称搜索
        max_length=100,  # 限制知识库名称最长 100 个字符
    )  # 结束 name 字段定义

    description: str | None = Field(  # 知识库描述，用来说明这个知识库的用途
        default=None,  # 描述可以为空
        max_length=500,  # 限制描述最长 500 个字符
    )  # 结束 description 字段定义

    user_id: int = Field(foreign_key="users.id")

    project_id: int = Field(  # 当前知识库所属的项目空间 ID
        foreign_key="project_spaces.id",  # 外键，指向 project_spaces 表
        index=True,  # 建索引，方便按项目空间查询知识库列表
    )  # 结束 project_id 字段定义

    created_at: datetime = Field(  # 知识库创建时间
        default_factory=datetime.utcnow,  # 创建记录时自动填入当前 UTC 时间
    )  # 结束 created_at 字段定义

    updated_at: datetime = Field(  # 知识库更新时间
        default_factory=datetime.utcnow,  # 创建时默认等于当前 UTC 时间
    )  # 结束 updated_at 字段定义

class Document(SQLModel, table=True):  # 定义文档模型，并让它对应 documents 表
    __tablename__ = "documents"  # 指定数据库表名为 documents
    id: Optional[int] = Field(
        default=None, primary_key=True
    )  # 文档 ID，主键，由数据库自动生成
    knowledge_base_id: int = Field(
        foreign_key="knowledge_bases.id", index=True
    )  # 所属知识库 ID，关联 knowledge_bases 表
    filename: str = Field(max_length=255)  # 原始文件名，例如 AI 学习计划.pdf
    file_type: str = Field(max_length=50)  # 文件类型，例如 pdf、docx、md、html、txt
    file_path: str = Field(max_length=500)  # 文件保存在服务器上的路径
    file_size: int = Field(default=0)  # 文件大小，单位是字节
    status: str = Field(
        default="uploaded", max_length=50
    )  # 文档状态，例如 uploaded、parsing、parsed、failed、indexed
    error_message: Optional[str] = Field(
        default=None, sa_column=Column(Text)
    )  # 错误信息，解析失败时保存原因
    created_at: datetime = Field(default_factory=datetime.utcnow)  # 文档创建时间
    updated_at: datetime = Field(default_factory=datetime.utcnow)  # 文档更新时间


class DocumentChunk(
    SQLModel, table=True
):  # 定义文本块模型，并让它对应 document_chunks 表
    __tablename__ = "document_chunks"  # 指定数据库表名为 document_chunks
    id: Optional[int] = Field(
        default=None, primary_key=True
    )  # 文本块 ID，主键，由数据库自动生成
    document_id: int = Field(
        foreign_key="documents.id", index=True
    )  # 所属文档 ID，关联 documents 表
    chunk_index: int = Field(index=True)  # 当前 chunk 在文档中的序号，通常从 0 开始
    content: str = Field(
        sa_column=Column(Text, nullable=False)
    )  # chunk 正文内容，使用 Text 保存较长文本，并且不能为空
    page_number: Optional[int] = Field(
        default=None
    )  # 来源页码，PDF 解析时可用，当前阶段可以为空
    token_count: int = Field(
        default=0
    )  # 当前 chunk 的大致 token 数，当前阶段先用字符数代替
    embedding_json: Optional[str] = Field(
        default=None, sa_column=Column(Text)
    )  # 保存当前 chunk 的 embedding 向量 JSON 字符串，暂时代替 pgvector
    created_at: datetime = Field(default_factory=datetime.utcnow)  # chunk 创建时间
    updated_at: datetime = Field(default_factory=datetime.utcnow)  # chunk 更新时间


class RagEvalCase(
    SQLModel, table=True
):  # 定义 RAG 评测用例表，用来保存固定测试问题和期望结果
    __tablename__ = "rag_eval_cases"  # 指定数据库表名为 rag_eval_cases

    id: int | None = Field(default=None, primary_key=True)  # 主键 ID，数据库自动生成

    knowledge_base_id: int = Field(  # 所属知识库 ID，表示这条评测用例用于测试哪个知识库
        foreign_key="knowledge_bases.id"
    )  # 设置外键，关联 knowledge_bases 表

    question: str  # 评测问题，例如“Day8 的目标是什么？”

    expected_answer: str = ""  # 参考答案，用来人工或简单规则判断回答是否接近预期

    expected_keywords: str = (
        ""  # 期望命中的关键词，先用逗号分隔字符串保存，例如 Day8,embedding,相似度检索
    )

    expected_document_name: str = (
        ""  # 期望命中的文档名称，用来判断 citations 是否命中正确文档
    )

    should_refuse: bool = False  # 是否期望系统拒答，True 表示这个问题知识库不应回答

    created_at: datetime = Field(  # 创建时间
        default_factory=datetime.utcnow
    )  # 默认使用当前 UTC 时间

    updated_at: datetime = Field(  # 更新时间
        default_factory=datetime.utcnow
    )  # 默认使用当前 UTC 时间


class RagEvalRun(
    SQLModel, table=True
):  # 定义 RAG 批量评测运行记录表，用来保存一次 run-all 的整体统计结果
    __tablename__ = "rag_eval_runs"  # 指定数据库表名为 rag_eval_runs

    id: int | None = Field(default=None, primary_key=True)  # 主键 ID，数据库自动生成

    knowledge_base_id: int = Field(  # 所属知识库 ID，表示这次评测是针对哪个知识库运行的
        foreign_key="knowledge_bases.id"
    )  # 设置外键，关联 knowledge_bases 表

    total: int = 0  # 本次评测运行的用例总数

    passed_count: int = 0  # 本次评测通过的用例数量

    failed_count: int = 0  # 本次评测失败的用例数量

    hit_rate: float = 0.0  # 本次评测通过率，例如 0.8 表示 80%

    created_at: datetime = Field(  # 创建时间，也可以理解为本次评测运行时间
        default_factory=datetime.utcnow
    )  # 默认使用当前 UTC 时间


class RagEvalResult(
    SQLModel, table=True
):  # 定义 RAG 单题评测结果表，用来保存某次评测运行中每一道题的详细结果
    __tablename__ = "rag_eval_results"  # 指定数据库表名为 rag_eval_results

    id: int | None = Field(default=None, primary_key=True)  # 主键 ID，数据库自动生成

    eval_run_id: int = Field(  # 所属评测运行 ID，表示这条结果属于哪一次批量评测
        foreign_key="rag_eval_runs.id"
    )  # 设置外键，关联 rag_eval_runs 表

    eval_case_id: int = Field(  # 所属评测用例 ID，表示这条结果对应哪一道评测题
        foreign_key="rag_eval_cases.id"
    )  # 设置外键，关联 rag_eval_cases 表

    knowledge_base_id: int = Field(  # 所属知识库 ID，方便按知识库查询评测结果
        foreign_key="knowledge_bases.id"
    )  # 设置外键，关联 knowledge_bases 表

    question: str  # 本次评测问题，保存快照，避免后面 eval_case 被修改后历史结果看不懂

    expected_answer: str = ""  # 参考答案快照

    actual_answer: str = ""  # RAG 实际返回的答案或者拒答提示

    should_refuse: bool = False  # 这道题是否期望拒答

    actual_refused: bool = False  # 系统本次是否实际拒答

    confidence_level: str = ""  # 本次回答置信度，例如 high、medium、low

    expected_keywords: str = ""  # 期望关键词快照

    matched_keywords: str = ""  # 实际命中的关键词，先用逗号分隔字符串保存

    missing_keywords: str = ""  # 未命中的关键词，先用逗号分隔字符串保存

    hit_expected_keywords: bool = False  # 是否命中期望关键词

    expected_document_name: str = ""  # 期望命中文档名快照

    hit_expected_document: bool = False  # 是否命中期望文档

    citation_valid: bool = False  # answer 是否包含有效 [资料 X] 引用

    passed: bool = False  # 本条评测是否通过

    notes: str = ""  # 评测说明，记录 bad case 类型和失败原因

    citations_json: str = ""  # citations 的 JSON 字符串快照，用来保存本次命中的引用来源

    created_at: datetime = Field(  # 创建时间，也就是这条评测结果保存时间
        default_factory=datetime.utcnow
    )  # 默认使用当前 UTC 时间


class AgentRun(SQLModel, table=True):  # 定义 Agent 执行结果表模型
    __tablename__ = "agent_runs"  # 指定数据库表名为 agent_runs

    id: int | None = Field(default=None, primary_key=True)  # 主键 ID，数据库自动生成

    task_id: int | None = Field(default=None, index=True)  # 关联 AgentTask ID，用来查询完整 trace

    user_input: str = Field(default="", sa_column=Column(Text))  # 保存用户原始输入

    task_type: str = Field(default="unknown", index=True)  # 保存任务类型，例如 normal_chat、rag_chat、report

    answer: str = Field(default="", sa_column=Column(Text))  # 保存 Agent 最终回答

    context: str = Field(default="", sa_column=Column(Text))  # 保存 RAG 检索上下文

    citations: list = Field(
        default_factory=list, sa_column=Column(JSON)
    )  # 保存引用来源列表，使用 default_factory 避免多个对象共享同一个列表

    steps: list = Field(
        default_factory=list, sa_column=Column(JSON)
    )  # 保存 Agent 执行步骤列表，使用 default_factory 避免多个对象共享同一个列表

    session_id: int | None = Field(default=None, index=True)  # 关联聊天会话 ID

    knowledge_base_id: int | None = Field(default=None, index=True)  # 关联知识库 ID

    status: str = Field(default="success", index=True)  # 保存执行状态，例如 success、failed

    error: str | None = Field(default=None, sa_column=Column(Text))  # 保存错误信息

    created_at: datetime = Field(default_factory=datetime.now, index=True)  # 保存创建时间

    updated_at: datetime = Field(default_factory=datetime.now)  # 保存更新时间

class Report(SQLModel, table=True):  # 定义报告表模型，并声明它是一张数据库表
    __tablename__ = "reports"  # 指定数据库表名为 reports

    id: int | None = Field(
        default=None, primary_key=True
    )  # 报告主键 ID，新增数据时由数据库自动生成

    title: str = Field(index=True)  # 报告标题，添加索引方便后面按标题查询

    report_type: str = Field(
        default="study_report", index=True
    )  # 报告类型，默认是 study_report，后面可以扩展 summary、project_report 等

    content: str = Field(
        sa_column=Column(Text)
    )  # 报告正文，使用 Text 类型，避免长报告内容被截断

    source_type: str = Field(
        default="manual", index=True
    )  # 报告来源类型，例如 manual、knowledge_base、agent_runs

    source_metadata: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON)
    )  # 报告来源补充信息，使用 JSON 保存结构化数据

    agent_run_id: int | None = Field(
        default=None, index=True
    )  # 关联的 AgentRun ID，可以为空，方便知道这份报告由哪次 Agent 执行生成

    markdown_file_path: str | None = Field(
        default=None
    )  # Markdown 文件导出路径，未导出时为空

    created_at: datetime = Field(
        default_factory=datetime.now, index=True
    )  # 创建时间，默认使用当前时间

    updated_at: datetime = Field(
        default_factory=datetime.now
    )  # 更新时间，默认使用当前时间


class AgentTask(SQLModel, table=True):  # 定义 Agent 任务表模型，并声明它是一张数据库表
    __tablename__ = "agent_tasks"  # 指定数据库表名为 agent_tasks

    id: int | None = Field(
        default=None, primary_key=True
    )  # 任务主键 ID，新增任务时由数据库自动生成

    task_type: str = Field(
        default="unknown", index=True
    )  # 任务类型，例如 report、rag_chat、normal_chat

    status: str = Field(
        default="created", index=True
    )  # # 任务状态，例如 created、queued、running、waiting_approval、completed、failed、rejected、cancelled

    user_input: str = Field(
        sa_column=Column(Text)
    )  # 用户原始输入，使用 Text 类型避免长文本被截断

    knowledge_base_id: int | None = Field(
        default=None, index=True
    )  # 当前任务使用的知识库 ID，可以为空

    session_id: int | None = Field(
        default=None, index=True
    )  # 当前任务关联的会话 ID，可以为空

    context: str = Field(
        default="", sa_column=Column(Text)
    )  # 知识库检索上下文，等待确认后可以继续使用

    citations: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON)
    )  # 知识库引用来源列表，使用 JSON 保存多个引用对象

    answer: str = Field(
        default="", sa_column=Column(Text)
    )  # 任务最终回答，任务未完成时可以为空字符串

    report_id: int | None = Field(
        default=None, index=True
    )  # 任务生成报告后对应的 Report ID，可以为空

    markdown_file_path: str | None = Field(
        default=None
    )  # 报告导出的 Markdown 文件路径，可以为空

    progress: int = Field(default=0, index=True)  # 任务进度，范围是 0 到 100，默认是 0，表示任务还没开始执行

    current_step: str = Field(default="任务已创建", sa_column=Column(Text))  # 当前任务执行到哪一步，用文字描述给前端或用户查看

    job_id: str | None = Field(default=None, index=True)  # RQ 后台任务的 Job ID，用来关联 Redis Queue 里的任务

    queued_at: datetime | None = Field(default=None)  # 任务加入队列的时间，任务还没入队时为空

    started_at: datetime | None = Field(default=None)  # Worker 开始执行任务的时间，任务还没开始执行时为空

    finished_at: datetime | None = Field(default=None)  # 任务成功或失败结束的时间，任务还没结束时为空

    error: str | None = Field(
        default=None, sa_column=Column(Text)
    )  # 任务失败原因，成功时为空
    retry_count: int = Field(default=0, index=True)  # 记录当前任务已经重试了几次，默认是 0 次

    max_retries: int = Field(default=3)  # 记录当前任务最多允许重试几次，默认最多重试 3 次

    last_retry_at: datetime | None = Field(default=None)  # 记录最后一次重试时间，没有重试过时为空

    failed_at: datetime | None = Field(default=None)  # 记录任务失败时间，任务没有失败时为空
    created_at: datetime = Field(
        default_factory=datetime.now, index=True
    )  # 任务创建时间，默认使用当前时间

    updated_at: datetime = Field(
        default_factory=datetime.now
    )  # 任务更新时间，默认使用当前时间

class AgentStep(SQLModel, table=True):  # 定义 Agent 任务步骤表模型，并声明它是一张数据库表
    __tablename__ = "agent_steps"  # 指定数据库表名为 agent_steps

    id: int | None = Field(default=None, primary_key=True)  # 步骤主键 ID，新增步骤时由数据库自动生成

    task_id: int = Field(index=True)  # 关联的 AgentTask ID，表示这个步骤属于哪个任务

    step_name: str = Field(index=True)  # 步骤名称，例如 classify_task、retrieve_knowledge、wait_for_approval

    step_type: str = Field(default="system", index=True)  # 步骤类型，例如 node、tool、approval、database、file、system

    status: str = Field(default="success", index=True)  # 步骤状态，例如 pending、running、success、failed、waiting_approval

    input_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))  # 步骤输入数据，使用 JSON 保存结构化参数

    output_data: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))  # 步骤输出数据，使用 JSON 保存工具或节点返回结果

    error: str | None = Field(default=None, sa_column=Column(Text))  # 步骤错误信息，执行成功时为空
    retry_count: int = Field(default=0, index=True)  # 记录这个步骤属于第几次重试，第一次正常执行时是 0

    is_retry: bool = Field(default=False, index=True)  # 标记这个步骤是不是重试过程中产生的步骤
    started_at: datetime | None = Field(default=None)  # 步骤开始时间，可以为空

    finished_at: datetime | None = Field(default=None)  # 步骤结束时间，可以为空

    created_at: datetime = Field(default_factory=datetime.now, index=True)  # 步骤记录创建时间，默认使用当前时间


class LlmCall(SQLModel, table=True):  # 定义 LLM 调用日志表模型，并声明它是一张数据库表
    __tablename__ = "llm_calls"  # 指定数据库表名为 llm_calls

    id: int | None = Field(
        default=None, primary_key=True
    )  # 日志主键 ID，新增记录时由数据库自动生成

    task_id: int | None = Field(
        default=None, index=True
    )  # 关联 AgentTask ID，用来表示这次 LLM 调用属于哪个任务

    step_id: int | None = Field(
        default=None, index=True
    )  # 关联 AgentStep ID，用来表示这次 LLM 调用属于哪个步骤

    model_name: str = Field(
        default="", index=True
    )  # 保存本次调用的模型名称，例如 deepseek-chat、qwen-plus、gpt-4o-mini

    prompt_name: str | None = Field(
        default=None, index=True
    )  # 保存 prompt 名称，例如 generate_report_prompt，后面做 prompt 版本管理会用到

    prompt_version: str | None = Field(
        default=None, index=True
    )  # 保存 prompt 版本，例如 v1、v2、v3

    prompt: str = Field(
        default="", sa_column=Column(Text)
    )  # 保存发送给模型的完整 prompt，使用 Text 避免内容太长被截断

    response: str = Field(
        default="", sa_column=Column(Text)
    )  # 保存模型返回的完整文本结果，使用 Text 避免长回答被截断

    input_tokens: int = Field(
        default=0, index=True
    )  # 保存输入 token 数，也就是 prompt tokens

    output_tokens: int = Field(
        default=0, index=True
    )  # 保存输出 token 数，也就是 completion tokens

    total_tokens: int = Field(
        default=0, index=True
    )  # 保存总 token 数，通常等于 input_tokens + output_tokens

    cost: float = Field(default=0.0)  # 保存本次模型调用的预估成本，默认是 0

    latency_ms: int = Field(default=0, index=True)  # 保存本次模型调用耗时，单位是毫秒

    status: str = Field(
        default="success", index=True
    )  # 保存调用状态，例如 success 或 failed

    error: str | None = Field(
        default=None, sa_column=Column(Text)
    )  # 保存错误信息，成功时为空，失败时记录异常原因

    created_at: datetime = Field(
        default_factory=datetime.now, index=True
    )  # 保存日志创建时间，默认使用当前时间

    updated_at: datetime = Field(
        default_factory=datetime.now
    )  # 保存日志更新时间，默认使用当前时间

class ToolCall(SQLModel, table=True):  # 定义工具调用日志表模型，并声明它是一张数据库表
    __tablename__ = "tool_calls"  # 指定数据库表名为 tool_calls

    id: int | None = Field(default=None, primary_key=True)  # 工具调用日志主键 ID，新增记录时由数据库自动生成

    task_id: int | None = Field(default=None, index=True)  # 关联 AgentTask ID，用来表示这次工具调用属于哪个任务

    step_id: int | None = Field(default=None, index=True)  # 关联 AgentStep ID，用来表示这次工具调用属于哪个步骤

    tool_name: str = Field(default="", index=True)  # 保存工具名称，例如 search_knowledge_base、export_markdown

    tool_input: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))  # 保存工具输入参数，使用 JSON 保存字典结构

    tool_output: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))  # 保存工具输出结果，使用 JSON 保存字典结构

    latency_ms: int = Field(default=0, index=True)  # 保存工具执行耗时，单位是毫秒

    cost: float = Field(default=0.0)  # 保存工具调用成本，普通本地工具一般是 0，调用付费外部 API 时可以记录费用

    status: str = Field(default="success", index=True)  # 保存工具调用状态，例如 success 或 failed

    error: str | None = Field(default=None, sa_column=Column(Text))  # 保存工具调用失败原因，成功时为空

    created_at: datetime = Field(default_factory=datetime.now, index=True)  # 保存日志创建时间，默认使用当前时间

    updated_at: datetime = Field(default_factory=datetime.now)  # 保存日志更新时间，默认使用当前时间

class RagRetrievalLog(
    SQLModel, table=True
):  # 定义 RAG 检索日志表模型，并声明它是一张数据库表
    __tablename__ = "rag_retrieval_logs"  # 指定数据库表名为 rag_retrieval_logs

    id: int | None = Field(
        default=None, primary_key=True
    )  # 日志主键 ID，新增记录时由数据库自动生成

    task_id: int | None = Field(
        default=None, index=True
    )  # 关联 AgentTask ID，用来表示这次检索属于哪个后台任务

    step_id: int | None = Field(
        default=None, index=True
    )  # 关联 AgentStep ID，用来表示这次检索属于哪个执行步骤

    knowledge_base_id: int | None = Field(
        default=None, index=True
    )  # 当前检索使用的知识库 ID

    query: str = Field(
        sa_column=Column(Text)
    )  # 本次检索的问题文本，使用 Text 类型避免长问题被截断

    top_k: int = Field(default=5)  # 本次检索最多返回多少条 chunk，默认是 5

    retrieved_count: int = Field(default=0, index=True)  # 本次实际检索命中的 chunk 数量

    matched_chunk_ids: list[int] = Field(
        default_factory=list, sa_column=Column(JSON)
    )  # 命中的 chunk ID 列表，使用 JSON 保存多个 ID

    scores: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON)
    )  # 每个命中 chunk 的分数信息，例如相似度分数、重排分数

    context: str = Field(
        default="", sa_column=Column(Text)
    )  # 最终拼接给 LLM 使用的上下文内容

    latency_ms: int = Field(default=0, index=True)  # 本次 RAG 检索耗时，单位是毫秒

    status: str = Field(
        default="success", index=True
    )  # 本次检索状态，例如 success 或 failed

    error: str | None = Field(
        default=None, sa_column=Column(Text)
    )  # 检索失败原因，成功时为空

    created_at: datetime = Field(
        default_factory=datetime.now, index=True
    )  # 日志创建时间，默认使用当前时间


class PromptVersion(
    SQLModel, table=True
):  # 定义 PromptVersion 模型，并声明它是一张数据库表
    __tablename__ = "prompt_versions"  # 指定数据库表名为 prompt_versions

    id: int | None = Field(
        default=None, primary_key=True
    )  # 主键 ID，新增记录时由数据库自动生成

    prompt_name: str = Field(
        default="", index=True
    )  # prompt 名称，例如 generate_agent_answer_prompt

    prompt_version: str = Field(
        default="v1", index=True
    )  # prompt 版本号，例如 v1、v2、v3

    prompt_content: str = Field(
        default="", sa_column=Column(Text)
    )  # prompt 的完整内容，使用 Text 避免内容太长被截断

    description: str | None = Field(
        default=None, sa_column=Column(Text)
    )  # prompt 说明，例如这个版本解决了什么问题

    task_type: str | None = Field(
        default=None, index=True
    )  # 适用任务类型，例如 normal_chat、rag_chat、report

    is_active: bool = Field(
        default=True, index=True
    )  # 是否启用，True 表示这个 prompt 版本仍然可用

    created_at: datetime = Field(
        default_factory=datetime.now, index=True
    )  # 创建时间，默认使用当前时间

    updated_at: datetime = Field(
        default_factory=datetime.now
    )  # 更新时间，默认使用当前时间


class BadCase(SQLModel, table=True):  # 定义 BadCase 模型，并声明它是一张数据库表
    __tablename__ = "bad_cases"  # 指定数据库表名为 bad_cases

    id: int | None = Field(
        default=None, primary_key=True
    )  # bad case 主键 ID，新增记录时由数据库自动生成

    task_id: int | None = Field(
        default=None, index=True
    )  # 关联 AgentTask ID，用来知道这个 bad case 来自哪一次任务

    user_id: int | None = Field(
        default=None, index=True
    )  # 关联用户 ID，用来知道是谁触发了这个 bad case，如果暂时没有用户信息可以为空

    task_type: str | None = Field(
        default=None, index=True
    )  # 保存任务类型，例如 normal_chat、rag_chat、report

    user_input: str = Field(
        default="", sa_column=Column(Text)
    )  # 保存用户原始问题，使用 Text 避免长问题被截断

    answer: str = Field(
        default="", sa_column=Column(Text)
    )  # 保存 AI 当时生成的错误回答，方便后续复盘

    expected_answer: str | None = Field(
        default=None, sa_column=Column(Text)
    )  # 保存期望的正确答案，可以由开发者或用户补充

    reason: str = Field(
        default="", sa_column=Column(Text)
    )  # 保存为什么这个回答不好，例如答非所问、引用错误、资料不足

    category: str = Field(
        default="unknown", index=True
    )  # 保存 bad case 分类，例如 rag_no_hit、prompt_issue、llm_answer_error

    severity: str = Field(
        default="medium", index=True
    )  # 保存严重程度，例如 low、medium、high

    status: str = Field(
        default="open", index=True
    )  # 保存处理状态，例如 open、fixed、ignored

    feedback_source: str = Field(
        default="developer", index=True
    )  # 保存反馈来源，例如 developer、user、eval

    prompt_name: str | None = Field(
        default=None, index=True
    )  # 保存当时使用的 prompt 名称

    prompt_version: str | None = Field(
        default=None, index=True
    )  # 保存当时使用的 prompt 版本

    trace_snapshot: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON)
    )  # 保存当时调用链的简要快照，方便以后回看

    fixed_note: str | None = Field(
        default=None, sa_column=Column(Text)
    )  # 保存修复说明，例如改了 prompt、优化了检索、调整了工具

    created_at: datetime = Field(
        default_factory=datetime.now, index=True
    )  # 保存 bad case 创建时间

    updated_at: datetime = Field(default_factory=datetime.now)  # 保存 bad case 更新时间

    fixed_at: datetime | None = Field(
        default=None, index=True
    )  # 保存修复时间，如果还没修复就为空


class ProjectRole(
    str, Enum
):  # 定义项目角色枚举；继承 str 是为了让数据库和接口里保存字符串值
    ADMIN = "admin"  # 管理员角色：可以管理项目、成员、知识库、文档等资源
    MEMBER = "member"  # 普通成员角色：可以使用项目、创建知识库、上传文档、创建任务
    VIEWER = "viewer"  # 只读成员角色：只能查看项目内容和进行只读操作


class ProjectSpace(
    SQLModel, table=True
):  # 定义项目空间表，用来表示一个业务项目或部门空间
    __tablename__ = (
        "project_spaces"  # 指定数据库表名为 project_spaces，方便后续外键引用
    )

    id: int | None = Field(
        default=None, primary_key=True
    )  # 项目空间 ID，数据库会自动生成

    name: str = Field(  # 项目空间名称，例如“产品部知识库”或“客服部知识库”
        index=True,  # 给名称字段建立索引，方便后续按名称搜索项目空间
        max_length=100,  # 限制名称最长 100 个字符，避免用户输入过长
    )  # 结束 name 字段定义

    description: str | None = Field(  # 项目空间描述，用来说明这个项目空间的用途
        default=None,  # 描述可以为空，不强制用户填写
        max_length=500,  # 限制描述最长 500 个字符
    )  # 结束 description 字段定义

    owner_id: int = Field(  # 项目空间创建者的用户 ID
        foreign_key="users.id",  # 外键，指向 users 表的 id 字段；如果你的用户表名不是 users，需要按实际表名修改
        index=True,  # 建立索引，方便查询某个用户创建了哪些项目空间
    )  # 结束 owner_id 字段定义

    created_at: datetime = Field(  # 项目空间创建时间
        default_factory=datetime.utcnow,  # 创建记录时自动填入当前 UTC 时间
    )  # 结束 created_at 字段定义

    updated_at: datetime = Field(  # 项目空间更新时间
        default_factory=datetime.utcnow,  # 创建时默认等于当前 UTC 时间，后续修改项目时再更新
    )  # 结束 updated_at 字段定义


class ProjectMember(
    SQLModel, table=True
):  # 定义项目成员表，用来记录用户在某个项目空间里的角色
    __tablename__ = (
        "project_members"  # 指定数据库表名为 project_members，避免默认表名不直观
    )

    __table_args__ = (  # 定义数据库表级别约束
        UniqueConstraint(  # 创建唯一约束，防止重复成员记录
            "project_id",  # 约束字段之一：项目空间 ID
            "user_id",  # 约束字段之二：用户 ID
            name="uq_project_member_project_user",  # 给这个唯一约束起名字，方便以后排查数据库问题
        ),  # 结束唯一约束定义
    )  # 结束表级别约束定义

    id: int | None = Field(
        default=None, primary_key=True
    )  # 项目成员记录 ID，数据库自动生成

    project_id: int = Field(  # 当前成员所属的项目空间 ID
        foreign_key="project_spaces.id",  # 外键，指向后面要创建的 project_spaces 表
        index=True,  # 建索引，方便按项目空间查询成员列表
    )  # 结束 project_id 字段定义

    user_id: int = Field(  # 当前成员对应的用户 ID
        foreign_key="users.id",  # 外键，指向用户表；如果你的用户表名不是 users，这里要按你的实际表名修改
        index=True,  # 建索引，方便按用户查询他加入了哪些项目
    )  # 结束 user_id 字段定义

    role: str = Field(  # 当前用户在这个项目空间里的角色
        default=ProjectRole.VIEWER.value,  # 默认角色是 viewer，避免新成员默认拥有过高权限
        index=True,  # 建索引，方便后续按角色筛选成员
    )  # 结束 role 字段定义

    created_at: datetime = Field(  # 创建时间
        default_factory=datetime.utcnow,  # 插入数据库时自动生成当前 UTC 时间
    )  # 结束 created_at 字段定义

    updated_at: datetime = Field(  # 更新时间
        default_factory=datetime.utcnow,  # 创建时先默认等于当前 UTC 时间
    )  # 结束 updated_at 字段定义
