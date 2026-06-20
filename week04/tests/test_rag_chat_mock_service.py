#被 mock 的函数	                为什么 mock
#can_view_project()	        避免依赖真实项目权限数据
#check_rate_limit()	        避免依赖真实限流状态
#get_recent_messages()	    避免查询真实聊天历史
#search_top_chunks()	    避免真实 pgvector 检索
#call_llm_with_prompt()	    避免真实调用 LLM
#update_conversation_summary_if_needed()	避免历史摘要再次调用 LLM



from types import (
    SimpleNamespace,
)  # 导入 SimpleNamespace，用来快速构造假的 current_user 对象

from models import (
    ChatSession,
    KnowledgeBase,
)  # 导入知识库和聊天会话模型，用来构造假的数据库对象
from schemas import RagChatRequest  # 导入 RAG 问答请求模型，用来构造接口请求体

from routers import rag  # 导入 RAG 路由模块，方便 monkeypatch 替换该模块里的函数


class FakeExecResult:  # 定义假的查询结果对象，用来模拟 session.exec(...).first()
    def __init__(self, row):  # 初始化时接收一条要返回的数据
        self.row = row  # 保存要返回的数据

    def first(self):  # 模拟 SQLModel 查询结果的 first() 方法
        return self.row  # 返回预设的数据


class FakeSession:  # 定义假的数据库 Session，用来避免测试连接真实数据库
    def __init__(
        self, knowledge_base, chat_session
    ):  # 初始化时接收假的知识库和聊天会话
        self.knowledge_base = knowledge_base  # 保存假的知识库对象
        self.chat_session = chat_session  # 保存假的聊天会话对象
        self.exec_call_count = 0  # 记录 session.exec() 被调用的次数
        self.added_objects = []  # 记录 session.add() 添加过的对象
        self.committed = False  # 记录是否调用过 commit()

    def exec(self, statement):  # 模拟 session.exec()
        self.exec_call_count += 1  # 每调用一次 exec，计数加 1

        if self.exec_call_count == 1:  # 第一次查询是查询 KnowledgeBase
            return FakeExecResult(self.knowledge_base)  # 返回假的知识库结果

        if self.exec_call_count == 2:  # 第二次查询是查询 ChatSession
            return FakeExecResult(self.chat_session)  # 返回假的聊天会话结果

        return FakeExecResult(None)  # 其他查询默认返回 None

    def add(self, obj):  # 模拟 session.add()
        self.added_objects.append(obj)  # 保存被添加的对象，方便断言是否保存了消息

    def commit(self):  # 模拟 session.commit()
        self.committed = True  # 标记事务已经提交


def test_rag_chat_should_return_mock_answer_and_citations(
    monkeypatch,
):  # 测试 RAG 问答接口在 mock 检索和 mock LLM 后是否返回固定答案和引用
    call_counter = {  # 创建调用计数字典，用来确认 mock 函数是否真的被调用
        "search": 0,  # 记录 fake_search_top_chunks 被调用次数
        "llm": 0,  # 记录 fake_call_llm_with_prompt 被调用次数
        "rate_limit": 0,  # 记录 fake_check_rate_limit 被调用次数
    }  # 结束计数字典创建

    knowledge_base = KnowledgeBase(  # 创建假的知识库对象
        id=1,  # 设置知识库 ID
        name="企业制度知识库",  # 设置知识库名称
        description="测试知识库",  # 设置知识库描述
        user_id=1,  # 设置创建用户 ID
        project_id=1,  # 设置所属项目空间 ID
    )  # 结束知识库对象创建

    chat_session = ChatSession(  # 创建假的聊天会话对象
        id=10,  # 设置会话 ID
        title="测试会话",  # 设置会话标题
        user_id=1,  # 设置创建用户 ID
        project_id=1,  # 设置所属项目空间 ID，必须和知识库 project_id 一致
        conversation_summary=None,  # 设置长期历史摘要为空
    )  # 结束聊天会话对象创建

    fake_session = FakeSession(  # 创建假的数据库会话
        knowledge_base=knowledge_base,  # 传入假的知识库
        chat_session=chat_session,  # 传入假的聊天会话
    )  # 结束 fake_session 创建

    current_user = SimpleNamespace(
        id=1, username="test_user"
    )  # 创建假的当前登录用户对象

    def fake_can_view_project(
        session, project_id: int, user
    ):  # 定义假的项目空间查看权限函数
        assert project_id == 1  # 断言传入的项目空间 ID 正确
        assert user.id == 1  # 断言传入的是当前测试用户
        return True  # 返回 True，表示当前用户有权限查看该项目

    def fake_check_rate_limit(user_id: int, action: str):  # 定义假的限流函数
        call_counter["rate_limit"] += 1  # 记录限流函数被调用了一次
        assert user_id == 1  # 断言限流使用当前用户 ID
        assert action == "rag_chat"  # 断言限流动作为 rag_chat
        return None  # 不做真实限流，直接通过

    def fake_get_recent_messages(
        session, chat_session_id: int, limit: int
    ):  # 定义假的历史消息读取函数
        assert chat_session_id == 10  # 断言读取的是当前测试会话
        return []  # 返回空历史，避免依赖真实 chat_messages 表

    def fake_search_top_chunks(
        session, knowledge_base_id: int, question: str, top_k: int, min_score: float
    ):  # 定义假的检索函数
        call_counter["search"] += 1  # 记录检索函数被调用了一次
        assert knowledge_base_id == 1  # 断言检索的是当前知识库
        assert "试用期离职需要提前几天" in question  # 断言检索问题包含用户问题
        assert top_k == 3  # 断言 top_k 来自请求体
        assert min_score == rag.MIN_RELEVANCE_SCORE  # 断言使用 RAG 最低相关度阈值

        return [  # 返回固定检索结果，避免真实查 pgvector
            {  # 第一条模拟 chunk
                "chunk_id": 1,  # 设置 chunk ID
                "document_id": 1,  # 设置文档 ID
                "document_name": "企业制度知识库测试文档.txt",  # 设置文档名称
                "chunk_index": 0,  # 设置 chunk 序号
                "content": "试用期员工离职需要提前 3 天通知公司。",  # 设置引用内容
                "vector_score": 0.82,  # 设置向量相似度分数
                "keyword_score": 0.70,  # 设置关键词分数
                "hybrid_score": 0.78,  # 设置 Hybrid 分数
                "final_score": 0.78,  # 设置兼容旧字段的 final_score
                "rerank_score": 0.90,  # 设置 Rerank 分数，保证置信度为 high
            }  # 结束第一条模拟 chunk
        ]  # 结束模拟检索结果列表

    def fake_call_llm_with_prompt(prompt: str) -> str:  # 定义假的 LLM 调用函数
        call_counter["llm"] += 1  # 记录 LLM 函数被调用了一次
        assert "试用期离职需要提前几天？" in prompt  # 断言 prompt 里包含用户问题
        assert (
            "试用期员工离职需要提前 3 天通知公司" in prompt
        )  # 断言 prompt 里包含检索资料
        return "根据资料，试用期员工离职需要提前 3 天通知公司。[资料 1]"  # 返回固定答案，避免真实调用大模型

    def fake_update_conversation_summary_if_needed(
        **kwargs,
    ):  # 定义假的历史摘要更新函数
        return None  # 不做真实摘要更新，避免再次调用 LLM

    monkeypatch.setattr(
        rag, "can_view_project", fake_can_view_project
    )  # 替换 RAG 路由里的权限函数
    monkeypatch.setattr(
        rag, "check_rate_limit", fake_check_rate_limit
    )  # 替换 RAG 路由里的限流函数
    monkeypatch.setattr(
        rag, "get_recent_messages", fake_get_recent_messages
    )  # 替换历史消息读取函数
    monkeypatch.setattr(
        rag, "search_top_chunks", fake_search_top_chunks
    )  # 替换 RAG 路由里的检索函数
    monkeypatch.setattr(
        rag, "call_llm_with_prompt", fake_call_llm_with_prompt
    )  # 替换 RAG 路由里的 LLM 函数
    monkeypatch.setattr(
        rag,
        "update_conversation_summary_if_needed",
        fake_update_conversation_summary_if_needed,
    )  # 替换历史摘要更新函数

    request_data = RagChatRequest(  # 创建 RAG 问答请求体
        session_id=10,  # 设置聊天会话 ID
        question="试用期离职需要提前几天？",  # 设置用户问题
        top_k=3,  # 设置检索 top_k
    )  # 结束请求体创建

    response = rag.rag_chat(  # 直接调用 RAG 路由函数
        knowledge_base_id=1,  # 传入知识库 ID
        rag_data=request_data,  # 传入请求体
        session=fake_session,  # 传入假的数据库会话
        current_user=current_user,  # 传入假的当前用户
    )  # 得到 RAG 响应

    assert call_counter["rate_limit"] == 1  # 断言限流函数被调用一次
    assert call_counter["search"] == 1  # 断言检索函数被调用一次
    assert call_counter["llm"] == 1  # 断言 LLM 函数被调用一次
    assert response.question == "试用期离职需要提前几天？"  # 断言返回原始问题
    assert (
        response.answer == "根据资料，试用期员工离职需要提前 3 天通知公司。[资料 1]"
    )  # 断言答案来自 fake LLM
    assert response.confidence_level == "high"  # 断言 rerank_score=0.90 时置信度为 high
    assert len(response.citations) == 1  # 断言返回 1 条引用
    assert response.citations[0].source_index == 1  # 断言引用编号是资料 1
    assert response.citations[0].rerank_score == 0.90  # 断言引用里保留 rerank_score
    assert (
        "试用期员工离职需要提前 3 天" in response.citations[0].content
    )  # 断言引用内容正确
    assert fake_session.committed is True  # 断言最终保存了用户消息和助手消息
    assert (
        len(fake_session.added_objects) == 2
    )  # 断言保存了 2 条消息：用户消息和助手消息
