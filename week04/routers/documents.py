import os  # 导入 os 模块，用来创建文件夹、拼接文件路径
import uuid  # 导入 uuid 模块，用来生成唯一文件名，避免不同用户上传同名文件时互相覆盖
import json  # 导入 json 模块，用来把 embedding 列表转换成 JSON 字符串保存到数据库
from typing import List  # 导入 List 类型，用来声明接口返回的是文档列表
from datetime import datetime  # 导入 datetime，用来更新文档的 updated_at 时间
from settings import settings  # 导入项目统一配置对象，用来读取上传文件大小限制
from fastapi import (  # 从 FastAPI 导入常用组件
    APIRouter,  # APIRouter 用来创建路由分组
    Depends,  # Depends 用来注入依赖，例如数据库会话和当前登录用户
    File,  # File 用来声明文件上传字段
    HTTPException,  # HTTPException 用来返回 HTTP 错误
    UploadFile,  # UploadFile 用来接收上传文件
)  # FastAPI 组件导入结束

from sqlalchemy import (
    text,
)  # 导入 text，用来执行原生 SQL，把 embedding 写入 pgvector 字段
from sqlmodel import Session, select  # 导入 Session 操作数据库，select 用来写查询语句

from database import get_session  # 导入 get_session，用来获取数据库会话

from models import (  # 从 models.py 导入数据库模型
    Document,  # 导入 Document 模型，用来操作 documents 表
    DocumentChunk,  # 导入 DocumentChunk 模型，用来操作 document_chunks 表
    KnowledgeBase,  # 导入 KnowledgeBase 模型，用来操作 knowledge_bases 表
)  # models 导入结束

from schemas import (  # 从 schemas.py 导入响应模型
    DocumentChunkRead,  # 导入文档 chunk 响应模型
    DocumentRead,  # 导入文档响应模型
)  # schemas 导入结束

from routers.users import (
    get_current_user,
)  # 导入 get_current_user，用来获取当前登录用户

from services.document_parser import (
    parse_document,
)  # 导入文档解析函数，用来把上传文件解析成纯文本
from services.embedding_service import (
    generate_embedding,
)  # 导入 embedding 生成函数，用来给 chunk 生成向量
from services.text_splitter import (
    split_text,
)  # 导入文本切块函数，用来把纯文本切成多个 chunks

from services.project_permission_service import (  # 导入项目空间权限判断函数
    can_manage_project,  # 判断当前用户是否可以管理项目空间
    can_view_project,  # 判断当前用户是否可以查看项目空间
    can_write_project,  # 判断当前用户是否可以写入项目空间
)  # 项目权限函数导入结束

router = APIRouter(tags=["文档"])  # 创建文档路由对象，并在 Swagger 中归类到“文档”分组


UPLOAD_DIR = "uploads"  # 定义上传文件保存的根目录名称


ALLOWED_FILE_TYPES = {"pdf", "docx", "md", "html", "txt"}  # 定义允许上传的文件类型集合


def get_file_type(filename: str) -> str:  # 定义获取文件类型的工具函数，参数是原始文件名
    if "." not in filename:  # 判断文件名里是否没有点号，如果没有点号就无法判断扩展名
        return ""  # 返回空字符串，表示没有识别到文件类型

    return filename.rsplit(".", 1)[1].lower()  # 从最后一个点号后面取扩展名，并转成小写


def embedding_to_pgvector_text(  # 定义把 Python embedding 列表转换成 pgvector 可识别字符串的函数
    embedding: list[float],  # embedding 向量列表，例如 [0.1, 0.2, 0.3]
) -> str:  # 返回字符串，例如 "[0.1,0.2,0.3]"
    vector_text = (
        "[" + ",".join(str(value) for value in embedding) + "]"
    )  # 拼接成 pgvector 可以识别的字符串格式

    return vector_text  # 返回 pgvector 字符串


def get_knowledge_base_or_404(  # 定义工具函数：根据知识库 ID 查询知识库，不存在就抛出 404
    session: Session,  # 数据库会话对象
    knowledge_base_id: int,  # 知识库 ID
) -> KnowledgeBase:  # 返回 KnowledgeBase 对象
    knowledge_base = session.get(  # 根据主键查询知识库
        KnowledgeBase,  # 要查询的模型是 KnowledgeBase
        knowledge_base_id,  # 查询传入的知识库 ID
    )  # 查询知识库结束

    if knowledge_base is None:  # 如果知识库不存在
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=404,  # 404 表示资源不存在
            detail="知识库不存在",  # 返回错误提示
        )  # HTTPException 结束

    return knowledge_base  # 返回查询到的知识库对象


def get_document_or_404(  # 定义工具函数：根据文档 ID 查询文档，不存在就抛出 404
    session: Session,  # 数据库会话对象
    document_id: int,  # 文档 ID
) -> Document:  # 返回 Document 对象
    document = session.get(  # 根据主键查询文档
        Document,  # 要查询的模型是 Document
        document_id,  # 查询传入的文档 ID
    )  # 查询文档结束

    if document is None:  # 如果文档不存在
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=404,  # 404 表示资源不存在
            detail="文档不存在",  # 返回错误提示
        )  # HTTPException 结束

    return document  # 返回查询到的文档对象


def get_document_knowledge_base_or_404(  # 定义工具函数：根据文档找到它所属的知识库
    session: Session,  # 数据库会话对象
    document: Document,  # 文档对象
) -> KnowledgeBase:  # 返回文档所属的 KnowledgeBase 对象
    knowledge_base = session.get(  # 根据文档里的 knowledge_base_id 查询知识库
        KnowledgeBase,  # 要查询的模型是 KnowledgeBase
        document.knowledge_base_id,  # 使用文档所属知识库 ID 进行查询
    )  # 查询知识库结束

    if knowledge_base is None:  # 如果文档所属知识库不存在
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=404,  # 404 表示资源不存在
            detail="文档所属知识库不存在",  # 返回错误提示
        )  # HTTPException 结束

    return knowledge_base  # 返回文档所属知识库对象


@router.post(  # 注册文档上传接口
    "/knowledge-bases/{knowledge_base_id}/documents/upload",  # 路径中包含知识库 ID
    response_model=DocumentRead,  # 返回 DocumentRead 响应模型
)  # 上传接口装饰器结束
async def upload_document(  # 定义上传文档接口函数
    knowledge_base_id: int,  # 路径参数，表示要上传到哪个知识库
    file: UploadFile = File(...),  # 接收上传文件
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user=Depends(get_current_user),  # 注入当前登录用户
):  # 函数参数定义结束
    knowledge_base = get_knowledge_base_or_404(  # 查询知识库是否存在
        session=session,  # 传入数据库会话
        knowledge_base_id=knowledge_base_id,  # 传入知识库 ID
    )  # 知识库查询结束

    if not can_write_project(  # 判断当前用户是否可以写入该知识库所属项目空间
        session=session,  # 传入数据库会话
        project_id=knowledge_base.project_id,  # 使用知识库的 project_id 判断项目权限
        user=current_user,  # 传入当前登录用户
    ):  # 权限判断结束
        raise HTTPException(  # 如果没有写入权限，就返回 403
            status_code=403,  # 403 表示没有权限
            detail="没有权限往该知识库上传文档",  # 返回错误提示
        )  # HTTPException 结束

    original_filename = (
        file.filename or ""
    )  # 获取用户上传的原始文件名，如果为空就使用空字符串
    file_type = get_file_type(
        original_filename
    )  # 根据原始文件名获取文件类型，例如 pdf、docx、md、html、txt

    if file_type not in ALLOWED_FILE_TYPES:  # 判断文件类型是否不在允许上传的类型集合中
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=400,  # 400 表示请求不合法
            detail="暂不支持该文件类型",  # 返回错误提示
        )  # HTTPException 结束

    file_content = await file.read()  # 异步读取上传文件的全部二进制内容

    file_size = len(file_content)  # 计算文件大小，单位是字节

    max_file_size_bytes = (  # 计算最大允许上传的文件大小，单位是字节
        settings.max_upload_file_size_mb
        * 1024
        * 1024  # 把 MB 转换成字节，例如 10MB = 10 * 1024 * 1024
    )  # 最大文件大小计算结束

    if file_size > max_file_size_bytes:  # 判断当前上传文件是否超过最大限制
        raise HTTPException(  # 如果文件过大，就抛出 HTTP 错误
            status_code=400,  # 400 表示请求不符合要求
            detail=f"文件大小不能超过 {settings.max_upload_file_size_mb}MB",  # 返回清晰的错误提示
        )  # HTTPException 结束

    os.makedirs(
        UPLOAD_DIR, exist_ok=True
    )  # 创建 uploads 文件夹，如果已经存在就不重复创建

    unique_filename = f"{uuid.uuid4().hex}_{original_filename}"  # 生成唯一文件名，避免同名文件互相覆盖
    save_path = os.path.join(
        UPLOAD_DIR, unique_filename
    )  # 拼接文件最终保存路径，例如 uploads/uuid_xxx.pdf

    with open(save_path, "wb") as f:  # 以二进制写入模式打开保存路径
        f.write(file_content)  # 把上传文件的二进制内容写入服务器本地文件

    document = Document(  # 创建 Document 数据库对象
        knowledge_base_id=knowledge_base_id,  # 设置文档所属知识库 ID
        filename=original_filename,  # 设置原始文件名
        file_type=file_type,  # 设置文件类型
        file_path=save_path,  # 设置文件保存路径
        file_size=file_size,  # 设置文件大小
        status="parsing",  # 初始状态设置为 parsing，表示正在解析
    )  # Document 对象创建结束

    session.add(document)  # 第一次保存文档基础记录，状态是 parsing
    session.commit()  # 提交事务，让 document 真正进入 documents 表
    session.refresh(document)  # 刷新对象，拿到数据库生成的 document.id

    try:  # 开始尝试解析文档和切块
        if document.id is None:  # 判断文档 ID 是否生成失败
            raise ValueError(
                "文档 ID 生成失败"
            )  # 主动抛出错误，避免后续 chunk 没有关联文档

        parsed_text = parse_document(  # 调用文档解析函数
            document.file_path,  # 传入文档保存路径
            document.file_type,  # 传入文档类型
        )  # 文档解析结束

        if not parsed_text.strip():  # 判断解析出的文本是否为空
            raise ValueError(
                "文档解析成功，但没有提取到有效文本内容"
            )  # 如果为空，主动抛出错误

        chunks = split_text(  # 调用文本切块函数
            parsed_text,  # 传入解析后的纯文本
            chunk_size=500,  # 每个 chunk 最大 500 字符
            chunk_overlap=100,  # 相邻 chunk 重叠 100 字符
        )  # 文本切块结束

        if not chunks:  # 判断是否没有生成任何 chunk
            raise ValueError(
                "文本切块失败，没有生成任何 chunk"
            )  # 没有 chunk 则主动抛出错误

        for chunk_index, chunk_content in enumerate(
            chunks
        ):  # 遍历所有 chunks，同时拿到序号和内容
            document_chunk = DocumentChunk(  # 创建文本块对象
                document_id=document.id,  # 设置当前 chunk 所属文档 ID
                chunk_index=chunk_index,  # 设置当前 chunk 的顺序编号
                content=chunk_content,  # 设置 chunk 正文内容
                page_number=None,  # 当前阶段暂时不记录页码
                token_count=len(chunk_content),  # 当前阶段用字符数临时代替 token 数
            )  # DocumentChunk 对象创建结束

            session.add(
                document_chunk
            )  # 把文本块对象加入数据库会话，准备写入 document_chunks 表

        document.status = "parsed"  # 所有 chunks 创建完成后，把文档状态改成 parsed
        document.error_message = None  # 解析成功时清空错误信息
        document.updated_at = datetime.utcnow()  # 更新文档更新时间

        session.add(document)  # 保存文档的新状态
        session.commit()  # 提交事务，保存 chunks 和 parsed 状态
        session.refresh(document)  # 刷新文档对象，拿到最新状态

    except Exception as error:  # 捕获解析、切块、保存 chunks 过程中的任何错误
        session.rollback()  # 回滚还没有成功提交的 chunks 或状态修改

        document.status = "failed"  # 失败后把文档状态改成 failed
        document.error_message = str(error)  # 保存失败原因
        document.updated_at = datetime.utcnow()  # 更新文档更新时间

        session.add(document)  # 保存失败状态
        session.commit()  # 把 failed 和 error_message 写入数据库
        session.refresh(document)  # 刷新文档对象，拿到最新失败状态

        return document  # 返回失败状态的文档

    return document  # 返回成功解析后的文档


@router.get(  # 注册获取文档列表接口
    "/knowledge-bases/{knowledge_base_id}/documents",  # 路径中包含知识库 ID
    response_model=List[DocumentRead],  # 返回文档列表
)  # 文档列表接口装饰器结束
def list_documents(  # 定义文档列表接口函数
    knowledge_base_id: int,  # 路径参数，知识库 ID
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user=Depends(get_current_user),  # 注入当前登录用户
):  # 函数参数定义结束
    knowledge_base = get_knowledge_base_or_404(  # 查询知识库是否存在
        session=session,  # 传入数据库会话
        knowledge_base_id=knowledge_base_id,  # 传入知识库 ID
    )  # 知识库查询结束

    if not can_view_project(  # 判断当前用户是否可以查看该知识库所属项目空间
        session=session,  # 传入数据库会话
        project_id=knowledge_base.project_id,  # 使用知识库的 project_id 判断项目权限
        user=current_user,  # 传入当前登录用户
    ):  # 权限判断结束
        raise HTTPException(  # 如果没有查看权限，就返回 404
            status_code=404,  # 返回 404，避免泄露知识库是否存在
            detail="知识库不存在或无权访问",  # 返回错误提示
        )  # HTTPException 结束

    document_statement = select(Document).where(  # 构建查询文档列表的 SQL 语句
        Document.knowledge_base_id == knowledge_base_id  # 只查询当前知识库下的所有文档
    )  # 查询语句构造结束

    documents = session.exec(
        document_statement
    ).all()  # 执行查询，并取出所有文档组成列表

    return documents  # 返回当前知识库下的文档列表


@router.get(  # 注册查看文档 chunks 接口
    "/documents/{document_id}/chunks",  # 路径中包含文档 ID
    response_model=List[DocumentChunkRead],  # 返回文本块列表
)  # chunks 接口装饰器结束
def list_document_chunks(  # 定义查看文档 chunks 的接口函数
    document_id: int,  # 路径参数，文档 ID
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user=Depends(get_current_user),  # 注入当前登录用户
):  # 函数参数定义结束
    document = get_document_or_404(  # 查询文档是否存在
        session=session,  # 传入数据库会话
        document_id=document_id,  # 传入文档 ID
    )  # 文档查询结束

    knowledge_base = get_document_knowledge_base_or_404(  # 根据文档查询它所属的知识库
        session=session,  # 传入数据库会话
        document=document,  # 传入文档对象
    )  # 文档所属知识库查询结束

    if not can_view_project(  # 判断当前用户是否可以查看该文档所属项目空间
        session=session,  # 传入数据库会话
        project_id=knowledge_base.project_id,  # 使用知识库的 project_id 判断项目权限
        user=current_user,  # 传入当前登录用户
    ):  # 权限判断结束
        raise HTTPException(  # 如果没有查看权限，就返回 404
            status_code=404,  # 返回 404，避免泄露文档是否存在
            detail="文档不存在或无权访问",  # 返回错误提示
        )  # HTTPException 结束

    chunk_statement = (  # 构建查询当前文档 chunks 的 SQL 语句
        select(DocumentChunk)  # 查询 DocumentChunk 表
        .where(DocumentChunk.document_id == document_id)  # 只查询当前文档下面的 chunks
        .order_by(DocumentChunk.chunk_index)  # 按 chunk_index 排序，保证顺序和原文一致
    )  # 查询语句构造结束

    chunks = session.exec(
        chunk_statement
    ).all()  # 执行 chunks 查询，并取出所有文本块组成列表

    return chunks  # 返回当前文档下的文本块列表


@router.post(  # 注册文档索引接口
    "/documents/{document_id}/index"  # 路径中包含文档 ID
)  # 文档索引接口装饰器结束
def index_document(  # 定义文档索引接口函数
    document_id: int,  # 路径参数，表示要索引哪个文档
    session: Session = Depends(
        get_session
    ),  # 注入数据库会话，用来查询文档和更新 chunks
    current_user=Depends(get_current_user),  # 注入当前登录用户，用来做权限校验
):  # 函数参数定义结束
    document = get_document_or_404(  # 查询文档是否存在
        session=session,  # 传入数据库会话
        document_id=document_id,  # 传入文档 ID
    )  # 文档查询结束

    knowledge_base = get_document_knowledge_base_or_404(  # 根据文档查询它所属的知识库
        session=session,  # 传入数据库会话
        document=document,  # 传入文档对象
    )  # 文档所属知识库查询结束

    if not can_write_project(  # 判断当前用户是否可以写入该文档所属项目空间
        session=session,  # 传入数据库会话
        project_id=knowledge_base.project_id,  # 使用知识库的 project_id 判断项目权限
        user=current_user,  # 传入当前登录用户
    ):  # 权限判断结束
        raise HTTPException(  # 如果没有写入权限，就返回 403
            status_code=403,  # 403 表示没有权限
            detail="没有权限索引该文档",  # 返回错误提示
        )  # HTTPException 结束

    chunk_statement = (  # 构建查询文档 chunks 的 SQL 语句
        select(DocumentChunk)  # 查询 DocumentChunk 表
        .where(DocumentChunk.document_id == document_id)  # 只查询当前文档下面的 chunks
        .order_by(DocumentChunk.chunk_index.asc())  # 按 chunk_index 正序排列
    )  # 查询语句构造结束

    chunks = session.exec(
        chunk_statement
    ).all()  # 执行查询，得到当前文档下的所有 chunks

    if not chunks:  # 判断当前文档是否没有 chunks
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=400,  # 400 表示当前文档状态不适合索引
            detail="当前文档没有可索引的文本块",  # 返回错误提示
        )  # HTTPException 结束

    indexed_count = 0  # 定义成功索引的 chunk 数量，初始为 0

    for chunk in chunks:  # 遍历当前文档下的每一个 chunk
        if not chunk.content.strip():  # 判断当前 chunk 内容是否为空
            continue  # 如果内容为空，就跳过当前 chunk

        embedding = generate_embedding(
            chunk.content
        )  # 调用真实 embedding 服务，把当前 chunk 文本转换成向量

        chunk.embedding_json = json.dumps(
            embedding
        )  # 把 embedding 列表转换成 JSON 字符串，保存到 embedding_json 字段

        session.add(chunk)  # 把修改后的 chunk 加入数据库会话，准备保存 embedding_json

        vector_text = embedding_to_pgvector_text(
            embedding
        )  # 把 Python list[float] 转成 pgvector 可以识别的字符串格式

        update_vector_statement = text("""
            UPDATE document_chunks
            SET embedding_vector = CAST(:embedding_vector AS vector)
            WHERE id = :chunk_id
            """)  # 构建原生 SQL，用来更新 embedding_vector 字段  # SQL 构建结束

        session.execute(  # 执行原生 SQL，把真实 embedding 写入 pgvector 字段
            update_vector_statement,  # 传入 SQL 语句
            {  # 传入 SQL 参数
                "embedding_vector": vector_text,  # 把 pgvector 字符串传给 :embedding_vector
                "chunk_id": chunk.id,  # 把当前 chunk 的 ID 传给 :chunk_id
            },  # 参数字典结束
        )  # SQL 执行结束

        indexed_count += 1  # 成功处理一个 chunk 后，索引数量加 1

    document.status = "indexed"  # 把文档状态改成 indexed，表示 chunks 已经完成向量索引
    document.updated_at = datetime.utcnow()  # 更新文档更新时间

    session.add(document)  # 把修改后的 document 添加到数据库会话中
    session.commit()  # 提交数据库事务，保存 chunk embedding 和文档状态

    return {  # 返回索引结果
        "document_id": document.id,  # 返回文档 ID
        "chunk_count": len(chunks),  # 返回当前文档总 chunk 数量
        "indexed_count": indexed_count,  # 返回成功生成 embedding 的 chunk 数量
        "status": document.status,  # 返回文档最新状态
        "message": "文档索引完成，chunks 已重新生成真实 embedding_json",  # 返回提示信息
    }  # 响应返回结束

@router.delete("/documents/{document_id}")  # 注册删除文档接口，最终路径是 DELETE /documents/{document_id}
def delete_document(  # 定义删除文档接口函数
    document_id: int,  # 路径参数，表示要删除的文档 ID
    session: Session = Depends(get_session),  # 注入数据库会话，用来查询和删除数据
    current_user=Depends(get_current_user),  # 注入当前登录用户，用来做权限判断
):  # 函数参数定义结束
    document = get_document_or_404(  # 根据文档 ID 查询文档，如果不存在就抛出 404
        session=session,  # 传入数据库会话
        document_id=document_id,  # 传入文档 ID
    )  # 文档查询结束

    knowledge_base = get_document_knowledge_base_or_404(  # 根据文档找到它所属的知识库
        session=session,  # 传入数据库会话
        document=document,  # 传入文档对象
    )  # 文档所属知识库查询结束

    if not can_manage_project(  # 判断当前用户是否可以管理该文档所属项目空间
        session=session,  # 传入数据库会话
        project_id=knowledge_base.project_id,  # 使用知识库的 project_id 判断项目权限
        user=current_user,  # 传入当前登录用户
    ):  # 权限判断结束
        raise HTTPException(  # 如果没有管理权限，就抛出 HTTP 错误
            status_code=403,  # 403 表示没有权限
            detail="没有权限删除该文档",  # 返回错误提示
        )  # HTTPException 结束

    chunk_statement = select(DocumentChunk).where(  # 构建查询文档 chunks 的 SQL 语句
        DocumentChunk.document_id == document_id  # 只查询当前文档下面的 chunks
    )  # 查询语句构造结束

    chunks = session.exec(chunk_statement).all()  # 执行查询，取出当前文档下的所有 chunks

    for chunk in chunks:  # 遍历当前文档下的每一个 chunk
        session.delete(chunk)  # 删除当前 chunk，避免直接删除 document 时被外键约束拦住

    file_path = document.file_path  # 先保存文件路径，因为后面删除 document 后还要尝试删除本地文件

    session.delete(document)  # 删除文档数据库记录
    session.commit()  # 提交事务，让 chunks 和 document 删除真正生效

    if file_path and os.path.exists(file_path):  # 如果本地文件路径存在，并且文件确实还在服务器上
        os.remove(file_path)  # 删除服务器本地保存的上传文件

    return {  # 返回删除结果
        "success": True,  # 表示删除成功
        "message": "文档删除成功",  # 返回提示信息
        "document_id": document_id,  # 返回被删除的文档 ID
    }  # 响应返回结束
