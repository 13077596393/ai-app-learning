from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)  # 导入路由、依赖注入和 HTTP 异常工具
from sqlalchemy import func  # 导入 func，用来执行 count 统计函数
from sqlmodel import Session, select  # 导入数据库会话和查询构造函数

from database import get_session  # 导入数据库会话依赖

from models import (  # 导入数据库模型
    ChatSession,  # 导入聊天会话模型，用来统计项目空间下的会话数量
    Document,  # 导入文档模型，用来统计项目空间下的文档数量
    KnowledgeBase,  # 导入知识库模型，用来统计项目空间下的知识库数量
    ProjectMember,  # 导入项目成员模型，用来统计项目成员数量
    ProjectSpace,  # 导入项目空间模型，用来查询项目空间信息
)  # 模型导入结束

from routers.users import get_current_user  # 导入当前登录用户依赖

from schemas import ProjectAdminOverviewResponse  # 导入管理后台概览响应模型

from services.project_permission_service import (  # 导入项目空间权限判断函数
    can_manage_project,  # 判断当前用户是否可以管理项目空间
    can_view_project,  # 判断当前用户是否可以查看项目空间
    can_write_project,  # 判断当前用户是否可以写入项目空间
    get_project_role,  # 获取当前用户在项目空间里的角色
)  # 权限函数导入结束

router = APIRouter(  # 创建管理后台路由对象
    prefix="/admin",  # 管理后台接口统一使用 /admin 前缀
    tags=["管理后台"],  # Swagger 分组名称
)  # 路由对象创建结束


@router.get(  # 注册项目管理后台概览接口
    "/projects/{project_id}/overview",  # 接口路径，project_id 表示项目空间 ID
    response_model=ProjectAdminOverviewResponse,  # 指定响应模型
)  # 路由装饰器结束
def get_project_admin_overview(  # 定义获取项目管理后台概览的接口函数
    project_id: int,  # 接收路径参数 project_id
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user=Depends(get_current_user),  # 注入当前登录用户
):  # 函数参数定义结束
    project_space = session.get(  # 根据项目空间 ID 查询项目空间
        ProjectSpace,  # 要查询的模型是 ProjectSpace
        project_id,  # 查询传入的项目空间 ID
    )  # 查询项目空间结束

    if project_space is None:  # 如果项目空间不存在
        raise HTTPException(  # 抛出 HTTP 异常
            status_code=404,  # 404 表示资源不存在
            detail="项目空间不存在",  # 返回错误提示
        )  # HTTPException 结束

    if not can_view_project(  # 判断当前用户是否可以查看该项目空间
        session=session,  # 传入数据库会话
        project_id=project_id,  # 传入项目空间 ID
        user=current_user,  # 传入当前登录用户
    ):  # 权限判断结束
        raise HTTPException(  # 如果没有查看权限
            status_code=404,  # 返回 404，避免泄露项目空间是否存在
            detail="项目空间不存在或无权访问",  # 返回错误提示
        )  # HTTPException 结束

    current_user_role = get_project_role(  # 查询当前用户在该项目空间里的角色
        session=session,  # 传入数据库会话
        project_id=project_id,  # 传入项目空间 ID
        user=current_user,  # 传入当前登录用户
    )  # 获取角色结束

    member_count = session.exec(  # 查询当前项目空间成员数量
        select(func.count(ProjectMember.id)).where(  # 构造 count 查询
            ProjectMember.project_id == project_id  # 只统计当前项目空间的成员
        )  # 查询条件结束
    ).one()  # 执行查询并取出数量

    knowledge_base_count = session.exec(  # 查询当前项目空间知识库数量
        select(func.count(KnowledgeBase.id)).where(  # 构造 count 查询
            KnowledgeBase.project_id == project_id  # 只统计当前项目空间的知识库
        )  # 查询条件结束
    ).one()  # 执行查询并取出数量

    knowledge_base_id_statement = select(
        KnowledgeBase.id
    ).where(  # 构造查询知识库 ID 的语句
        KnowledgeBase.project_id == project_id  # 只查询当前项目空间下的知识库 ID
    )  # 查询语句构造结束

    knowledge_base_ids = session.exec(  # 执行知识库 ID 查询
        knowledge_base_id_statement  # 传入查询语句
    ).all()  # 获取所有知识库 ID

    valid_knowledge_base_ids = [  # 创建有效知识库 ID 列表
        knowledge_base_id  # 当前知识库 ID
        for knowledge_base_id in knowledge_base_ids  # 遍历查询结果
        if knowledge_base_id is not None  # 过滤掉 None，避免后面 in 查询异常
    ]  # 有效知识库 ID 列表创建结束

    if valid_knowledge_base_ids:  # 如果当前项目空间下面有知识库
        document_count = session.exec(  # 查询这些知识库下的文档数量
            select(func.count(Document.id)).where(  # 构造 count 查询
                Document.knowledge_base_id.in_(
                    valid_knowledge_base_ids
                )  # 只统计这些知识库下的文档
            )  # 查询条件结束
        ).one()  # 执行查询并取出数量
    else:  # 如果当前项目空间下面没有知识库
        document_count = 0  # 文档数量直接设置为 0

    chat_session_count = session.exec(  # 查询当前项目空间聊天会话数量
        select(func.count(ChatSession.id)).where(  # 构造 count 查询
            ChatSession.project_id == project_id  # 只统计当前项目空间下的会话
        )  # 查询条件结束
    ).one()  # 执行查询并取出数量

    can_write = can_write_project(  # 判断当前用户是否可以写入项目空间
        session=session,  # 传入数据库会话
        project_id=project_id,  # 传入项目空间 ID
        user=current_user,  # 传入当前登录用户
    )  # 写入权限判断结束

    can_manage = can_manage_project(  # 判断当前用户是否可以管理项目空间
        session=session,  # 传入数据库会话
        project_id=project_id,  # 传入项目空间 ID
        user=current_user,  # 传入当前登录用户
    )  # 管理权限判断结束

    return ProjectAdminOverviewResponse(  # 返回项目管理后台概览响应
        project_id=project_space.id or 0,  # 返回项目空间 ID
        project_name=project_space.name,  # 返回项目空间名称
        current_user_role=current_user_role or "unknown",  # 返回当前用户角色
        member_count=member_count,  # 返回成员数量
        knowledge_base_count=knowledge_base_count,  # 返回知识库数量
        document_count=document_count,  # 返回文档数量
        chat_session_count=chat_session_count,  # 返回会话数量
        can_write=can_write,  # 返回当前用户是否可以写入
        can_manage=can_manage,  # 返回当前用户是否可以管理
    )  # 响应对象创建结束
