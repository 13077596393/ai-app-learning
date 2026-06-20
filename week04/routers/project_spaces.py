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
from schemas import (  # 从 schemas.py 导入项目空间相关请求和响应模型
    ProjectSpaceCreateRequest,  # 创建项目空间请求模型
    ProjectSpaceListResponse,  # 项目空间列表响应模型
    ProjectSpaceResponse,  # 项目空间详情响应模型
)  # schemas 导入结束
from services.project_space_service import (  # 导入项目空间业务函数
    create_project_space,  # 创建项目空间函数
    get_my_project_space_detail,  # 查询当前用户有权限查看的项目空间详情函数
    list_my_project_spaces,  # 查询当前用户加入的项目空间列表函数
)  # services 导入结束

router = APIRouter(  # 创建项目空间路由对象
    prefix="/project-spaces",  # 这一组接口统一以 /project-spaces 开头
    tags=["project-spaces"],  # Swagger 中显示为 project-spaces 分组
)  # 路由对象创建结束


@router.post("", response_model=ProjectSpaceResponse)  # 注册创建项目空间接口
def create_project_space_api(  # 定义创建项目空间接口处理函数
    request_data: ProjectSpaceCreateRequest,  # 接收前端传来的项目空间名称和描述
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user: User = Depends(get_current_user),  # 注入当前登录用户
):  # 函数参数定义结束
    try:  # 开始捕获业务层可能抛出的异常
        return create_project_space(  # 调用业务函数创建项目空间
            session=session,  # 传入数据库会话
            request_data=request_data,  # 传入创建项目空间请求数据
            user=current_user,  # 传入当前登录用户
        )  # 返回创建后的项目空间响应
    except ValueError as exc:  # 捕获业务层主动抛出的参数类错误
        raise HTTPException(  # 抛出 HTTP 错误给前端
            status_code=400,  # 400 表示请求参数或业务数据不合法
            detail=str(exc),  # 把业务错误信息返回给前端
        )  # HTTPException 定义结束


@router.get(
    "/my", response_model=ProjectSpaceListResponse
)  # 注册查询我的项目空间列表接口
def list_my_project_spaces_api(  # 定义查询我的项目空间接口处理函数
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user: User = Depends(get_current_user),  # 注入当前登录用户
):  # 函数参数定义结束
    return list_my_project_spaces(  # 调用业务函数查询当前用户加入的项目空间
        session=session,  # 传入数据库会话
        user=current_user,  # 传入当前登录用户
    )  # 返回项目空间列表响应


@router.get(
    "/{project_id}", response_model=ProjectSpaceResponse
)  # 注册查询项目空间详情接口
def get_project_space_detail_api(  # 定义项目空间详情接口处理函数
    project_id: int,  # 从路径中接收项目空间 ID
    session: Session = Depends(get_session),  # 注入数据库会话
    current_user: User = Depends(get_current_user),  # 注入当前登录用户
):  # 函数参数定义结束
    project_space = (
        get_my_project_space_detail(  # 调用业务函数查询当前用户有权限访问的项目空间详情
            session=session,  # 传入数据库会话
            project_id=project_id,  # 传入项目空间 ID
            user=current_user,  # 传入当前登录用户
        )
    )  # 查询项目空间详情结束

    if project_space is None:  # 如果返回 None，说明项目不存在，或者当前用户没有权限查看
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=404,  # 这里用 404，避免泄露项目是否真实存在
            detail="项目空间不存在或无权访问",  # 返回给前端的错误信息
        )  # HTTPException 定义结束

    return project_space  # 返回项目空间详情

