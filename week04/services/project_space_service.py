from datetime import datetime  # 导入 datetime，用来生成创建时间和更新时间

from sqlmodel import (
    Session,
    select,
)  # 导入 Session 用来操作数据库，导入 select 用来构造查询语句

from models import (
    ProjectMember,
    ProjectRole,
    ProjectSpace,
    User,
)  # 导入项目空间表、项目成员表、角色枚举和用户表
from schemas import (  # 从 schemas.py 导入项目空间相关的请求和响应模型
    ProjectSpaceCreateRequest,  # 创建项目空间请求模型
    ProjectSpaceListResponse,  # 项目空间列表响应模型
    ProjectSpaceResponse,  # 项目空间详情响应模型
)  # schemas 导入结束
from services.project_permission_service import (
    get_project_member,
)  # 导入查询项目成员记录的函数


def build_project_space_response(  # 定义函数：把数据库里的 ProjectSpace 转成接口响应模型
    project_space: ProjectSpace,  # 数据库中的项目空间对象
    current_user_role: str | None,  # 当前登录用户在这个项目空间里的角色
) -> ProjectSpaceResponse:  # 返回 ProjectSpaceResponse 响应对象
    return ProjectSpaceResponse(  # 创建并返回项目空间响应模型
        id=project_space.id or 0,  # 返回项目空间 ID；如果 id 是 None，就兜底返回 0
        name=project_space.name,  # 返回项目空间名称
        description=project_space.description,  # 返回项目空间描述
        owner_id=project_space.owner_id,  # 返回项目空间创建者 ID
        current_user_role=current_user_role,  # 返回当前用户在该项目空间里的角色
        created_at=project_space.created_at,  # 返回创建时间
        updated_at=project_space.updated_at,  # 返回更新时间
    )  # 响应模型创建结束


def create_project_space(  # 定义函数：创建项目空间
    session: Session,  # 数据库会话对象
    request_data: ProjectSpaceCreateRequest,  # 前端传入的创建项目空间请求数据
    user: User,  # 当前登录用户
) -> ProjectSpaceResponse:  # 返回创建后的项目空间响应
    if user.id is None:  # 如果当前用户没有 ID，说明用户数据异常
        raise ValueError(
            "当前用户没有有效 ID，无法创建项目空间"
        )  # 抛出错误，避免创建无 owner 的项目空间

    now = datetime.utcnow()  # 获取当前 UTC 时间，后面用于 created_at 和 updated_at

    project_space = ProjectSpace(  # 创建项目空间数据库对象
        name=request_data.name,  # 设置项目空间名称
        description=request_data.description,  # 设置项目空间描述
        owner_id=user.id,  # 设置项目空间创建者为当前登录用户
        created_at=now,  # 设置创建时间
        updated_at=now,  # 设置更新时间
    )  # 项目空间对象创建结束

    try:  # 开始数据库事务保护
        session.add(project_space)  # 把项目空间对象加入数据库会话
        session.flush()  # 先把数据发送到数据库，让数据库生成 project_space.id，但暂时不提交事务

        if (
            project_space.id is None
        ):  # 如果 flush 后仍然没有生成 ID，说明创建项目空间失败
            raise ValueError(
                "项目空间 ID 生成失败"
            )  # 抛出错误，避免后面创建成员关系失败

        project_member = ProjectMember(  # 创建项目成员数据库对象
            project_id=project_space.id,  # 成员所属项目空间 ID
            user_id=user.id,  # 成员对应的用户 ID，也就是当前创建项目的人
            role=ProjectRole.ADMIN.value,  # 创建者自动成为 admin 管理员
            created_at=now,  # 设置成员记录创建时间
            updated_at=now,  # 设置成员记录更新时间
        )  # 项目成员对象创建结束

        session.add(project_member)  # 把项目成员对象加入数据库会话
        session.commit()  # 提交事务，把 ProjectSpace 和 ProjectMember 一起保存到数据库
        session.refresh(project_space)  # 刷新项目空间对象，确保拿到数据库里的最新数据

    except Exception:  # 如果创建项目空间或创建成员关系过程中出现任何错误
        session.rollback()  # 回滚事务，避免只创建了项目空间但没有创建管理员成员
        raise  # 继续抛出原始错误，交给路由层返回给前端

    return build_project_space_response(  # 返回项目空间响应对象
        project_space=project_space,  # 传入刚创建好的项目空间
        current_user_role=ProjectRole.ADMIN.value,  # 当前用户就是创建者，所以角色是 admin
    )  # 响应对象返回结束


def list_my_project_spaces(  # 定义函数：查询当前用户加入的所有项目空间
    session: Session,  # 数据库会话对象
    user: User,  # 当前登录用户
) -> ProjectSpaceListResponse:  # 返回项目空间列表响应
    if user.id is None:  # 如果当前用户没有 ID，说明用户数据异常
        return ProjectSpaceListResponse(total=0, items=[])  # 直接返回空列表

    statement = select(ProjectMember).where(  # 构造查询语句  # 查询 ProjectMember 表
        ProjectMember.user_id == user.id
    )  # 只查当前用户加入的项目成员记录  # 查询语句构造结束

    members = session.exec(statement).all()  # 执行查询，得到当前用户的所有项目成员记录

    items: list[ProjectSpaceResponse] = (
        []
    )  # 创建响应列表，用来存放当前用户可见的项目空间

    for member in members:  # 遍历当前用户加入的每一个项目成员记录
        project_space = session.get(
            ProjectSpace, member.project_id
        )  # 根据 project_id 查询对应的项目空间

        if project_space is None:  # 如果项目空间不存在，说明数据可能已经被删除或异常
            continue  # 跳过这条异常成员记录

        items.append(  # 把项目空间响应对象加入列表
            build_project_space_response(  # 构造项目空间响应对象
                project_space=project_space,  # 传入项目空间对象
                current_user_role=member.role,  # 传入当前用户在该项目里的角色
            )  # 响应对象构造结束
        )  # 加入列表结束

    return ProjectSpaceListResponse(  # 返回项目空间列表响应
        total=len(items),  # 返回项目空间总数
        items=items,  # 返回项目空间列表
    )  # 列表响应返回结束


def get_my_project_space_detail(  # 定义函数：查询当前用户有权限查看的项目空间详情
    session: Session,  # 数据库会话对象
    project_id: int,  # 要查询的项目空间 ID
    user: User,  # 当前登录用户
) -> ProjectSpaceResponse | None:  # 如果有权限就返回项目空间详情，否则返回 None
    member = get_project_member(  # 查询当前用户在该项目空间里的成员记录
        session=session,  # 传入数据库会话
        project_id=project_id,  # 传入项目空间 ID
        user=user,  # 传入当前登录用户
    )  # 成员记录查询结束

    if member is None:  # 如果没有成员记录，说明当前用户不属于这个项目空间
        return None  # 返回 None，表示无权查看

    project_space = session.get(
        ProjectSpace, project_id
    )  # 根据项目空间 ID 查询项目空间对象

    if project_space is None:  # 如果项目空间不存在
        return None  # 返回 None，表示没有找到项目空间

    return build_project_space_response(  # 返回项目空间详情响应
        project_space=project_space,  # 传入项目空间对象
        current_user_role=member.role,  # 传入当前用户在该项目空间里的角色
    )  # 响应对象返回结束


