from fastapi import (  # 从 FastAPI 导入常用组件
    APIRouter,  # APIRouter 用来创建路由分组
    Depends,  # Depends 用来注入依赖
    HTTPException,  # HTTPException 用来返回 HTTP 错误响应
)  # FastAPI 组件导入结束
from sqlmodel import Session  # 导入 Session 操作数据库

from database import get_session  # 导入 get_session，用来获取数据库会话
from models import KnowledgeBase  # 导入 KnowledgeBase 模型，用来校验知识库是否存在
from routers.users import get_current_user  # 导入 get_current_user，用来获取当前登录用户
from schemas import (  # 导入知识库检索请求体和响应体模型
    KnowledgeBaseSearchRequest,  # 导入知识库检索请求模型
    KnowledgeBaseSearchResponse,  # 导入知识库检索响应模型
)  # schemas 导入结束
from services.project_permission_service import (  # 导入项目空间权限判断函数
    can_view_project,  # 判断当前用户是否可以查看项目空间
)  # 项目空间权限函数导入结束
from services.retrieval_service import (  # 导入统一检索函数
    search_top_chunks,  # 根据知识库 ID 和问题检索 top-k chunks
)  # retrieval_service 导入结束

router = APIRouter(  # 创建知识库检索路由对象
    tags=["知识库检索"]  # 在 Swagger 中归类到“知识库检索”分组
)  # 路由对象创建结束


@router.post(  # 注册知识库检索接口
    "/knowledge-bases/{knowledge_base_id}/search",  # 接口路径，knowledge_base_id 表示要检索的知识库
    response_model=KnowledgeBaseSearchResponse,  # 指定接口响应模型
)  # 路由装饰器结束
def search_knowledge_base(  # 定义知识库检索接口函数
    knowledge_base_id: int,  # 接收路径参数 knowledge_base_id，表示要检索哪个知识库
    search_data: KnowledgeBaseSearchRequest,  # 接收请求体，里面包含 question 和 top_k
    session: Session = Depends(get_session),  # 注入数据库会话，用来查询知识库和调用检索服务
    current_user=Depends(get_current_user),  # 注入当前登录用户，用来做权限校验
):  # 函数参数定义结束
    knowledge_base = session.get(  # 根据主键查询知识库
        KnowledgeBase,  # 要查询的模型是 KnowledgeBase
        knowledge_base_id,  # 使用路径中的 knowledge_base_id 查询
    )  # 知识库查询结束

    if knowledge_base is None:  # 判断知识库是否不存在
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=404,  # 404 表示资源不存在
            detail="知识库不存在",  # 返回错误提示
        )  # HTTPException 结束

    if not can_view_project(  # 判断当前用户是否可以查看该知识库所属项目空间
        session=session,  # 传入数据库会话
        project_id=knowledge_base.project_id,  # 使用知识库的 project_id 判断项目权限
        user=current_user,  # 传入当前登录用户
    ):  # 权限判断结束
        raise HTTPException(  # 如果没有查看权限
            status_code=404,  # 返回 404，避免泄露知识库是否真实存在
            detail="知识库不存在或无权访问",  # 返回错误提示
        )  # HTTPException 结束

    question = search_data.question.strip()  # 去掉用户问题前后的空白字符

    if not question:  # 判断问题是否为空
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=400,  # 400 表示请求参数不合法
            detail="问题不能为空",  # 返回错误提示
        )  # HTTPException 结束

    top_k = search_data.top_k  # 从请求体中读取 top_k，表示返回最相关的前几个 chunks

    if top_k <= 0:  # 判断 top_k 是否小于等于 0
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=400,  # 400 表示请求参数不合法
            detail="top_k 必须大于 0",  # 返回错误提示
        )  # HTTPException 结束

    top_results = search_top_chunks(  # 调用统一检索服务，获取 top-k 相关 chunks
        session=session,  # 传入当前数据库会话
        knowledge_base_id=knowledge_base_id,  # 传入当前知识库 ID
        question=question,  # 传入用户问题
        top_k=top_k,  # 传入要返回的 chunks 数量
    )  # top-k 检索结束

    return KnowledgeBaseSearchResponse(  # 返回知识库检索响应
        question=question,  # 返回用户原始问题
        top_k=top_k,  # 返回本次使用的 top_k
        results=top_results,  # 返回检索到的 top-k chunks
    )  # 响应对象创建结束
