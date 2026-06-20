import os  # 导入 os 模块，用来删除知识库下文档对应的本地文件
from typing import List  # 导入 List 类型，用来声明接口返回的是一个列表

from fastapi import (  # 从 FastAPI 导入常用组件
    APIRouter,  # APIRouter 用来创建路由分组
    HTTPException,  # HTTPException 用来返回 HTTP 错误
    Depends,  # Depends 用来注入依赖，例如数据库会话和当前登录用户
)  # 结束 FastAPI 组件导入

from sqlmodel import Session, select  # 导入 Session 操作数据库，select 用来构造查询语句

from database import get_session  # 导入 get_session，用来获取数据库会话

from models import (  # 从 models.py 导入数据库模型
    Document,  # 导入 Document 模型，用来删除知识库下的文档记录
    DocumentChunk,  # 导入 DocumentChunk 模型，用来删除文档下的文本块记录
    KnowledgeBase,  # 导入 KnowledgeBase 模型，用来操作 knowledge_bases 表
    ProjectSpace,  # 导入 ProjectSpace 模型，用来判断项目空间是否存在
)  # 结束 models 导入

from schemas import (  # 从 schemas.py 导入知识库相关 Schema
    KnowledgeBaseCreate,  # 导入知识库创建请求模型
    KnowledgeBaseRead,  # 导入知识库响应模型
)  # 结束 schemas 导入

from routers.users import (  # 从用户路由中导入当前登录用户依赖
    get_current_user,  # get_current_user 用来获取当前登录用户
)  # 结束用户依赖导入

from services.project_permission_service import (  # 导入项目权限判断函数
    can_manage_project,  # 判断当前用户是否可以管理项目空间
    can_view_project,  # 判断当前用户是否可以查看项目空间
    can_write_project,  # 判断当前用户是否可以写入项目空间
)  # 结束权限函数导入

router = APIRouter(  # 创建知识库路由对象
    prefix="/knowledge-bases",  # 知识库接口统一前缀，注意这里修正了原来的 konwledge 拼写错误
    tags=["知识库"],  # Swagger 中显示的分组名称
)  # 路由对象创建结束


@router.post(
    "", response_model=KnowledgeBaseRead
)  # 注册创建知识库接口，最终路径是 POST /knowledge-bases
def create_knowledge_base(  # 定义创建知识库接口函数
    knowledge_base_data: KnowledgeBaseCreate,  # 接收前端传入的知识库创建数据，包括 project_id、name、description
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user=Depends(get_current_user),  # 注入当前登录用户
):  # 函数参数定义结束
    if current_user.id is None:  # 判断当前用户是否没有有效 ID
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=400,  # 400 表示当前请求数据或用户状态不合法
            detail="当前用户没有有效 ID，无法创建知识库",  # 返回错误提示
        )  # 结束 HTTPException

    project_space = session.get(  # 根据 project_id 查询项目空间
        ProjectSpace,  # 要查询的数据库模型是 ProjectSpace
        knowledge_base_data.project_id,  # 使用请求体里的 project_id 作为查询主键
    )  # 项目空间查询结束

    if project_space is None:  # 如果项目空间不存在
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=404,  # 404 表示项目空间不存在
            detail="项目空间不存在",  # 返回错误提示
        )  # 结束 HTTPException

    if not can_write_project(  # 判断当前用户是否有写入该项目空间的权限
        session=session,  # 传入数据库会话
        project_id=knowledge_base_data.project_id,  # 传入项目空间 ID
        user=current_user,  # 传入当前登录用户
    ):  # 权限判断结束
        raise HTTPException(  # 如果没有写入权限，抛出 HTTP 错误
            status_code=403,  # 403 表示没有权限
            detail="没有权限在该项目空间创建知识库",  # 返回错误提示
        )  # 结束 HTTPException

    knowledge_base = KnowledgeBase(  # 创建 KnowledgeBase 数据库对象
        name=knowledge_base_data.name,  # 设置知识库名称
        description=knowledge_base_data.description,  # 设置知识库描述
        user_id=current_user.id,  # 设置知识库创建者 ID，沿用你项目原来的 user_id 字段
        project_id=knowledge_base_data.project_id,  # 设置知识库所属项目空间 ID
    )  # 知识库对象创建结束

    session.add(knowledge_base)  # 把新建的知识库对象添加到数据库会话中
    session.commit()  # 提交数据库事务，让新增知识库真正保存到数据库
    session.refresh(
        knowledge_base
    )  # 刷新对象，获取数据库自动生成的 id、created_at 等字段

    return knowledge_base  # 返回创建成功后的知识库对象给前端


@router.get(
    "", response_model=List[KnowledgeBaseRead]
)  # 注册获取项目空间下知识库列表接口，最终路径是 GET /knowledge-bases
def list_knowledge_bases(  # 定义知识库列表接口函数
    project_id: int,  # 从 query 参数中接收项目空间 ID，例如 /knowledge-bases?project_id=1
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user=Depends(get_current_user),  # 注入当前登录用户
):  # 函数参数定义结束
    project_space = session.get(  # 根据 project_id 查询项目空间
        ProjectSpace,  # 要查询的模型是 ProjectSpace
        project_id,  # 查询传入的项目空间 ID
    )  # 项目空间查询结束

    if project_space is None:  # 如果项目空间不存在
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=404,  # 404 表示项目空间不存在
            detail="项目空间不存在",  # 返回错误提示
        )  # 结束 HTTPException

    if not can_view_project(  # 判断当前用户是否有查看该项目空间的权限
        session=session,  # 传入数据库会话
        project_id=project_id,  # 传入项目空间 ID
        user=current_user,  # 传入当前登录用户
    ):  # 权限判断结束
        raise HTTPException(  # 如果没有查看权限，抛出 HTTP 错误
            status_code=404,  # 返回 404，避免泄露项目空间是否真实存在
            detail="项目空间不存在或无权访问",  # 返回错误提示
        )  # 结束 HTTPException

    statement = select(KnowledgeBase).where(  # 构造查询知识库的 SQL 语句
        KnowledgeBase.project_id == project_id  # 只查询当前项目空间下的知识库
    )  # 查询语句构造结束

    knowledge_bases = session.exec(
        statement
    ).all()  # 执行查询，取出当前项目空间下的所有知识库

    return knowledge_bases  # 返回知识库列表


@router.get(
    "/{knowledge_base_id}", response_model=KnowledgeBaseRead
)  # 注册获取知识库详情接口
def get_knowledge_base_detail(  # 定义获取知识库详情接口函数
    knowledge_base_id: int,  # 路径参数，知识库 ID
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user=Depends(get_current_user),  # 注入当前登录用户
):  # 函数参数定义结束
    knowledge_base = session.get(  # 根据知识库 ID 查询知识库
        KnowledgeBase,  # 要查询的模型是 KnowledgeBase
        knowledge_base_id,  # 查询传入的知识库 ID
    )  # 知识库查询结束

    if knowledge_base is None:  # 如果知识库不存在
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=404,  # 404 表示知识库不存在
            detail="知识库不存在",  # 返回错误提示
        )  # 结束 HTTPException

    if not can_view_project(  # 判断当前用户是否能查看知识库所属项目空间
        session=session,  # 传入数据库会话
        project_id=knowledge_base.project_id,  # 使用知识库自己的 project_id 判断权限
        user=current_user,  # 传入当前登录用户
    ):  # 权限判断结束
        raise HTTPException(  # 如果无权查看，抛出 HTTP 错误
            status_code=404,  # 返回 404，避免泄露知识库是否真实存在
            detail="知识库不存在或无权访问",  # 返回错误提示
        )  # 结束 HTTPException

    return knowledge_base  # 返回知识库详情


@router.delete(
    "/{knowledge_base_id}"
)  # 注册删除知识库接口，最终路径是 DELETE /knowledge-bases/{knowledge_base_id}
def delete_knowledge_base(  # 定义删除知识库接口函数
    knowledge_base_id: int,  # 路径参数，知识库 ID
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user=Depends(get_current_user),  # 注入当前登录用户
):  # 函数参数定义结束
    knowledge_base = session.get(  # 根据知识库 ID 查询知识库
        KnowledgeBase,  # 要查询的模型是 KnowledgeBase
        knowledge_base_id,  # 查询传入的知识库 ID
    )  # 知识库查询结束

    if knowledge_base is None:  # 判断知识库是否不存在
        raise HTTPException(  # 抛出 HTTP 异常
            status_code=404,  # 状态码 404
            detail="知识库不存在",  # 错误提示
        )  # 结束异常抛出

    if not can_manage_project(  # 判断当前用户是否有管理知识库所属项目空间的权限
        session=session,  # 传入数据库会话
        project_id=knowledge_base.project_id,  # 传入知识库所属项目空间 ID
        user=current_user,  # 传入当前登录用户
    ):  # 权限判断结束
        raise HTTPException(  # 抛出 HTTP 异常
            status_code=403,  # 状态码 403
            detail="没有权限删除该知识库",  # 错误提示
        )  # 结束异常抛出

    documents = session.exec(  # 查询当前知识库下的所有文档
        select(Document).where(  # 构建文档查询语句
            Document.knowledge_base_id == knowledge_base_id  # 只查询当前知识库下的文档
        )  # 查询条件结束
    ).all()  # 执行查询，得到文档列表

    file_paths = [  # 先保存本地文件路径，避免删除数据库记录后拿不到文件路径
        document.file_path  # 取出当前文档在服务器上的保存路径
        for document in documents  # 遍历当前知识库下的所有文档
        if document.file_path  # 只保留非空文件路径
    ]  # 本地文件路径列表创建结束

    try:  # 使用事务保护知识库、文档、chunks 删除过程
        for document in documents:  # 遍历当前知识库下的每一个文档
            chunks = session.exec(  # 查询当前文档下的所有文本块
                select(DocumentChunk).where(  # 构建文本块查询语句
                    DocumentChunk.document_id
                    == document.id  # 只查询当前文档对应的 chunks
                )  # 查询条件结束
            ).all()  # 执行查询，得到 chunks 列表

            for chunk in chunks:  # 遍历当前文档下的每一个 chunk
                session.delete(chunk)  # 先删除 chunk，避免外键约束阻止删除 document

            session.delete(document)  # 删除文档记录

        session.delete(knowledge_base)  # 最后删除知识库对象
        session.commit()  # 提交事务，让 chunks、documents、knowledge_base 删除真正生效

    except Exception:  # 如果删除过程中出现异常
        session.rollback()  # 回滚事务，避免只删除一部分数据造成不一致
        raise  # 继续抛出原始异常，交给 FastAPI 返回错误

    for file_path in file_paths:  # 数据库删除成功后，再尝试删除本地文件
        try:  # 本地文件删除失败不应该影响已经完成的数据库删除
            if os.path.exists(file_path):  # 判断本地文件是否存在
                os.remove(file_path)  # 删除本地上传文件
        except OSError:  # 如果文件正在被占用或路径异常
            pass  # 忽略本地文件删除异常，避免接口在数据库已删除后又返回失败

    return {  # 返回删除结果
        "message": "知识库删除成功",  # 返回提示信息
        "knowledge_base_id": knowledge_base_id,  # 返回被删除的知识库 ID
        "deleted_document_count": len(documents),  # 返回本次一起删除的文档数量
    }  # 结束响应返回
