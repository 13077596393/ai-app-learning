from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)  # 导入 APIRouter 定义路由，Depends 注入依赖，HTTPException 返回错误
from sqlmodel import Session  # 导入 Session，用来操作数据库

from database import get_session  # 导入数据库会话依赖
from models import User  # 导入 User 用户模型，用来标注当前登录用户类型
from routers.users import (
    get_current_user,
)  # 导入当前登录用户依赖；如果你的项目路径不同，要按实际路径调整
from schemas import (  # 从 schemas.py 导入项目成员相关请求和响应模型
    ProjectMemberAddRequest,  # 添加项目成员请求模型
    ProjectMemberListResponse,  # 项目成员列表响应模型
    ProjectMemberResponse,  # 项目成员响应模型
    ProjectMemberUpdateRoleRequest,  # 修改项目成员角色请求模型
)  # schemas 导入结束
from services.project_member_service import (  # 从项目成员服务层导入业务函数
    add_project_member,  # 添加项目成员函数
    list_project_members,  # 查询项目成员列表函数
    remove_project_member,  # 移除项目成员函数
    update_project_member_role,  # 修改项目成员角色函数
)  # services 导入结束

router = APIRouter(  # 创建项目成员路由对象
    prefix="/project-spaces/{project_id}/members",  # 这一组接口都挂在某个项目空间下面
    tags=["project-members"],  # Swagger 中显示为 project-members 分组
)  # 路由对象创建结束


@router.get("", response_model=ProjectMemberListResponse)  # 注册查询项目成员列表接口
def list_project_members_api(  # 定义查询项目成员列表接口处理函数
    project_id: int,  # 从路径中获取项目空间 ID
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user: User = Depends(get_current_user),  # 注入当前登录用户
):  # 函数参数定义结束
    result = list_project_members(  # 调用服务层函数查询项目成员列表
        session=session,  # 传入数据库会话
        project_id=project_id,  # 传入项目空间 ID
        current_user=current_user,  # 传入当前登录用户
    )  # 成员列表查询结束

    if result is None:  # 如果返回 None，说明项目不存在，或者当前用户无权查看
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=404,  # 返回 404，避免泄露项目空间是否真实存在
            detail="项目空间不存在或无权访问成员列表",  # 返回错误信息
        )  # HTTPException 定义结束

    return result  # 返回项目成员列表


@router.post("", response_model=ProjectMemberResponse)  # 注册添加项目成员接口
def add_project_member_api(  # 定义添加项目成员接口处理函数
    project_id: int,  # 从路径中获取项目空间 ID
    request_data: ProjectMemberAddRequest,  # 接收前端传入的 user_id 和 role
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user: User = Depends(get_current_user),  # 注入当前登录用户
):  # 函数参数定义结束
    try:  # 捕获服务层可能抛出的业务错误或权限错误
        return add_project_member(  # 调用服务层函数添加项目成员
            session=session,  # 传入数据库会话
            project_id=project_id,  # 传入项目空间 ID
            request_data=request_data,  # 传入添加成员请求数据
            current_user=current_user,  # 传入当前登录用户
        )  # 返回新添加的项目成员信息
    except PermissionError as exc:  # 捕获权限错误，例如当前用户不是 admin
        raise HTTPException(  # 抛出 HTTP 权限错误
            status_code=403,  # 403 表示没有权限
            detail=str(exc),  # 返回服务层给出的权限错误信息
        )  # HTTPException 定义结束
    except ValueError as exc:  # 捕获业务错误，例如项目不存在、用户不存在、成员已存在
        raise HTTPException(  # 抛出 HTTP 业务错误
            status_code=400,  # 400 表示请求数据或业务规则不合法
            detail=str(exc),  # 返回服务层给出的业务错误信息
        )  # HTTPException 定义结束


@router.patch(
    "/{member_id}/role", response_model=ProjectMemberResponse
)  # 注册修改成员角色接口
def update_project_member_role_api(  # 定义修改成员角色接口处理函数
    project_id: int,  # 从路径中获取项目空间 ID
    member_id: int,  # 从路径中获取项目成员记录 ID
    request_data: ProjectMemberUpdateRoleRequest,  # 接收前端传入的新角色
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user: User = Depends(get_current_user),  # 注入当前登录用户
):  # 函数参数定义结束
    try:  # 捕获服务层可能抛出的错误
        return update_project_member_role(  # 调用服务层函数修改成员角色
            session=session,  # 传入数据库会话
            project_id=project_id,  # 传入项目空间 ID
            member_id=member_id,  # 传入成员记录 ID
            request_data=request_data,  # 传入修改角色请求数据
            current_user=current_user,  # 传入当前登录用户
        )  # 返回修改后的成员信息
    except PermissionError as exc:  # 捕获权限错误
        raise HTTPException(  # 抛出 HTTP 权限错误
            status_code=403,  # 403 表示没有权限
            detail=str(exc),  # 返回权限错误信息
        )  # HTTPException 定义结束
    except ValueError as exc:  # 捕获业务错误
        raise HTTPException(  # 抛出 HTTP 业务错误
            status_code=400,  # 400 表示请求数据或业务规则不合法
            detail=str(exc),  # 返回业务错误信息
        )  # HTTPException 定义结束


@router.delete("/{member_id}")  # 注册移除项目成员接口
def remove_project_member_api(  # 定义移除项目成员接口处理函数
    project_id: int,  # 从路径中获取项目空间 ID
    member_id: int,  # 从路径中获取项目成员记录 ID
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user: User = Depends(get_current_user),  # 注入当前登录用户
):  # 函数参数定义结束
    try:  # 捕获服务层可能抛出的错误
        remove_project_member(  # 调用服务层函数移除项目成员
            session=session,  # 传入数据库会话
            project_id=project_id,  # 传入项目空间 ID
            member_id=member_id,  # 传入成员记录 ID
            current_user=current_user,  # 传入当前登录用户
        )  # 成员移除结束

        return {  # 返回删除成功结果
            "success": True,  # 表示删除成功
            "message": "项目成员已移除",  # 返回成功提示
        }  # 返回结果结束
    except PermissionError as exc:  # 捕获权限错误
        raise HTTPException(  # 抛出 HTTP 权限错误
            status_code=403,  # 403 表示没有权限
            detail=str(exc),  # 返回权限错误信息
        )  # HTTPException 定义结束
    except ValueError as exc:  # 捕获业务错误
        raise HTTPException(  # 抛出 HTTP 业务错误
            status_code=400,  # 400 表示请求数据或业务规则不合法
            detail=str(exc),  # 返回业务错误信息
        )  # HTTPException 定义结束
