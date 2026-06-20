#1. 能查询到文档
#2. 能检查写入权限
#3. 能查询 chunks
#4. 会跳过空白 chunk
#5. 会给有效 chunk 生成 embedding
#6. 会保存 embedding_json
#7. 会把 embedding 转成 pgvector 字符串
#8. 会执行 embedding_vector 更新 SQL
#9. 会把 document.status 改成 indexed
#10. 会返回 indexed_count

import json  # 导入 json，用来解析 chunk.embedding_json

from models import (
    Document,
    DocumentChunk,
    KnowledgeBase,
)  # 导入文档、文档块、知识库模型

from routers import (
    documents,
)  # 导入 documents 路由模块，方便 monkeypatch 替换模块里的 generate_embedding


class FakeExecResult:  # 定义假的查询结果对象，用来模拟 session.exec(...).all()
    def __init__(self, rows):  # 初始化时接收要返回的数据列表
        self.rows = rows  # 保存要返回的数据列表

    def all(self):  # 模拟 SQLModel 查询结果的 all() 方法
        return self.rows  # 返回预设的数据列表


class FakeSession:  # 定义假的数据库 Session，用来避免测试连接真实数据库
    def __init__(self, chunks):  # 初始化时接收当前文档下的 chunks
        self.chunks = chunks  # 保存假的 chunks 列表
        self.added_objects = []  # 记录被 session.add() 添加过的对象
        self.executed_params = []  # 记录 session.execute() 执行时传入的参数
        self.committed = False  # 记录是否调用过 commit()

    def exec(self, statement):  # 模拟 session.exec()，这里不解析 SQL 语句
        return FakeExecResult(self.chunks)  # 返回假的 chunks 查询结果

    def add(self, obj):  # 模拟 session.add()
        self.added_objects.append(obj)  # 记录被添加的对象，方便测试断言

    def execute(
        self, statement, params
    ):  # 模拟 session.execute()，用于记录 pgvector 更新参数
        self.executed_params.append(params)  # 保存执行 SQL 时传入的参数字典

    def commit(self):  # 模拟 session.commit()
        self.committed = True  # 标记已经提交过事务


def test_embedding_to_pgvector_text_should_convert_list_to_vector_text():  # 测试 embedding 列表是否能转换成 pgvector 字符串
    vector_text = documents.embedding_to_pgvector_text(  # 调用真实转换函数
        [0.1, 0.2, 0.3]  # 传入假的 embedding 向量
    )  # 得到 pgvector 字符串

    assert vector_text == "[0.1,0.2,0.3]"  # 断言格式符合 pgvector 的向量文本格式


def test_index_document_should_use_mock_embedding_and_update_chunks(
    monkeypatch,
):  # 测试 index_document 是否能使用 mock embedding 完成索引
    call_counter = {  # 创建调用计数器
        "embedding": 0  # 记录 fake_generate_embedding 被调用了几次
    }  # 结束计数器创建

    document = Document(  # 构造假的文档对象
        id=1,  # 文档 ID
        knowledge_base_id=1,  # 所属知识库 ID
        filename="企业制度知识库测试文档.txt",  # 文档名
        file_type="txt",  # 文件类型
        file_path="uploads/test.txt",  # 文件路径
        file_size=100,  # 文件大小
        status="parsed",  # 当前文档状态，表示已经解析并切块
    )  # 结束文档对象创建

    knowledge_base = KnowledgeBase(  # 构造假的知识库对象
        id=1,  # 知识库 ID
        name="企业制度知识库",  # 知识库名称
        description="测试知识库",  # 知识库描述
        user_id=1,  # 创建用户 ID
        project_id=1,  # 所属项目空间 ID
    )  # 结束知识库对象创建

    chunks = [  # 构造假的文档 chunks
        DocumentChunk(  # 第一条有效 chunk
            id=1,  # chunk ID
            document_id=1,  # 所属文档 ID
            chunk_index=0,  # chunk 序号
            content="试用期员工离职需要提前 3 天通知公司。",  # chunk 内容
            token_count=20,  # token 数
        ),  # 结束第一条 chunk
        DocumentChunk(  # 第二条有效 chunk
            id=2,  # chunk ID
            document_id=1,  # 所属文档 ID
            chunk_index=1,  # chunk 序号
            content="员工报销需要提交发票、费用说明和审批记录。",  # chunk 内容
            token_count=24,  # token 数
        ),  # 结束第二条 chunk
        DocumentChunk(  # 第三条空内容 chunk，用来测试空内容会被跳过
            id=3,  # chunk ID
            document_id=1,  # 所属文档 ID
            chunk_index=2,  # chunk 序号
            content="   ",  # 空白内容
            token_count=0,  # token 数
        ),  # 结束第三条 chunk
    ]  # 结束 chunks 列表构造

    fake_session = FakeSession(chunks=chunks)  # 创建假的数据库会话

    def fake_get_document_or_404(session, document_id: int):  # 定义假的文档查询函数
        assert document_id == 1  # 断言传入的文档 ID 正确
        return document  # 返回假的文档对象

    def fake_get_document_knowledge_base_or_404(
        session, document
    ):  # 定义假的文档所属知识库查询函数
        return knowledge_base  # 返回假的知识库对象

    def fake_can_write_project(session, project_id: int, user):  # 定义假的权限判断函数
        assert project_id == 1  # 断言传入的项目空间 ID 正确
        return True  # 返回 True，表示当前用户有写入权限

    def fake_generate_embedding(
        text: str,
    ) -> list[float]:  # 定义假的 embedding 生成函数
        call_counter["embedding"] += 1  # 每调用一次，计数加 1
        assert text.strip()  # 断言传入的文本不是空白内容
        return [0.1, 0.2, 0.3]  # 返回固定 embedding，避免真实调用外部 API

    monkeypatch.setattr(  # 替换 documents 模块里的文档查询函数
        documents,  # 指定 documents 模块
        "get_document_or_404",  # 要替换的函数名
        fake_get_document_or_404,  # 替换成假的函数
    )  # 结束替换

    monkeypatch.setattr(  # 替换 documents 模块里的知识库查询函数
        documents,  # 指定 documents 模块
        "get_document_knowledge_base_or_404",  # 要替换的函数名
        fake_get_document_knowledge_base_or_404,  # 替换成假的函数
    )  # 结束替换

    monkeypatch.setattr(  # 替换 documents 模块里的权限判断函数
        documents,  # 指定 documents 模块
        "can_write_project",  # 要替换的函数名
        fake_can_write_project,  # 替换成假的权限函数
    )  # 结束替换

    monkeypatch.setattr(  # 替换 documents 模块里的 generate_embedding
        documents,  # 指定 documents 模块，也就是使用方
        "generate_embedding",  # 要替换的函数名
        fake_generate_embedding,  # 替换成假的 embedding 函数
    )  # 结束替换

    response = documents.index_document(  # 直接调用真实 index_document 函数
        document_id=1,  # 传入文档 ID
        session=fake_session,  # 传入假的数据库会话
        current_user=object(),  # 传入假的当前用户对象
    )  # 得到索引接口返回结果

    assert (
        call_counter["embedding"] == 2
    )  # 断言只给 2 条有效 chunk 生成 embedding，空白 chunk 被跳过
    assert json.loads(chunks[0].embedding_json) == [
        0.1,
        0.2,
        0.3,
    ]  # 断言第一条 chunk 保存了 embedding_json
    assert json.loads(chunks[1].embedding_json) == [
        0.1,
        0.2,
        0.3,
    ]  # 断言第二条 chunk 保存了 embedding_json
    assert chunks[2].embedding_json is None  # 断言空白 chunk 没有生成 embedding_json
    assert fake_session.executed_params == [  # 断言执行了两次 pgvector 更新 SQL
        {
            "embedding_vector": "[0.1,0.2,0.3]",
            "chunk_id": 1,
        },  # 第一条 chunk 的向量更新参数
        {
            "embedding_vector": "[0.1,0.2,0.3]",
            "chunk_id": 2,
        },  # 第二条 chunk 的向量更新参数
    ]  # 结束断言
    assert document.status == "indexed"  # 断言文档状态被更新为 indexed
    assert fake_session.committed is True  # 断言最终调用了 commit()
    assert response["document_id"] == 1  # 断言返回文档 ID 正确
    assert response["chunk_count"] == 3  # 断言返回当前文档总 chunk 数
    assert response["indexed_count"] == 2  # 断言只索引了 2 条有效 chunk
    assert response["status"] == "indexed"  # 断言返回状态是 indexed
