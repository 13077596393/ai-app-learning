from datetime import datetime  # 导入 datetime，用来更新成员记录的时间

from sqlmodel import (
    Session,
    select,
)  # 导入 Session 操作数据库，导入 select 构造查询语句

from models import (
    ProjectMember,
    ProjectSpace,
    User,
)  # 导入项目成员表、项目空间表、用户表
from schemas import (  # 导入项目成员相关请求和响应模型
    ProjectMemberAddRequest,  # 添加项目成员请求模型
    ProjectMemberListResponse,  # 项目成员列表响应模型
    ProjectMemberResponse,  # 项目成员响应模型
    ProjectMemberUpdateRoleRequest,  # 修改项目成员角色请求模型
)  # schemas 导入结束
from services.project_permission_service import (  # 导入项目权限判断函数
    can_manage_project,  # 判断当前用户是否能管理项目
    can_view_project,  # 判断当前用户是否能查看项目
)  # 权限函数导入结束


def build_project_member_response(  # 定义函数：把数据库中的 ProjectMember 转成接口响应模型
    member: ProjectMember,  # 数据库中的项目成员对象
) -> ProjectMemberResponse:  # 返回 ProjectMemberResponse 响应对象
    return ProjectMemberResponse(  # 创建项目成员响应对象
        id=member.id or 0,  # 返回成员记录 ID，如果 id 是 None 就兜底返回 0
        project_id=member.project_id,  # 返回项目空间 ID
        user_id=member.user_id,  # 返回成员用户 ID
        role=member.role,  # 返回成员角色：admin / member / viewer
        created_at=member.created_at,  # 返回成员加入项目的时间
        updated_at=member.updated_at,  # 返回成员记录最后更新时间
    )  # 项目成员响应对象创建结束


def list_project_members(  # 定义函数：查询某个项目空间的成员列表
    session: Session,  # 数据库会话对象
    project_id: int,  # 项目空间 ID
    current_user: User,  # 当前登录用户
) -> (
    ProjectMemberListResponse | None
):  # 有权限则返回成员列表；无权限或项目不存在则返回 None
    project_space = session.get(
        ProjectSpace, project_id
    )  # 根据项目 ID 查询项目空间是否存在

    if project_space is None:  # 如果项目空间不存在
        return None  # 返回 None，后面路由层会转成 404

    if not can_view_project(  # 判断当前用户是否有查看该项目空间的权限
        session=session,  # 传入数据库会话
        project_id=project_id,  # 传入项目空间 ID
        user=current_user,  # 传入当前登录用户
    ):  # 权限判断结束
        return None  # 如果无权查看，也返回 None，避免泄露项目是否存在

    statement = select(  # 构造查询项目成员的 SQL 语句
        ProjectMember
    ).where(  # 查询 ProjectMember 表
        ProjectMember.project_id == project_id
    )  # 只查询当前项目空间的成员  # 查询语句构造结束

    members = session.exec(statement).all()  # 执行查询，得到项目成员列表

    items = [  # 构造成员响应列表
        build_project_member_response(member)  # 把每个数据库成员对象转成响应模型
        for member in members  # 遍历查询出来的每一个成员
    ]  # 列表构造结束

    return ProjectMemberListResponse(  # 返回项目成员列表响应
        total=len(items),  # 返回成员总数
        items=items,  # 返回成员列表
    )  # 成员列表响应返回结束


def add_project_member(  # 定义函数：添加项目成员
    session: Session,  # 数据库会话对象
    project_id: int,  # 项目空间 ID
    request_data: ProjectMemberAddRequest,  # 添加成员请求数据
    current_user: User,  # 当前登录用户
) -> ProjectMemberResponse:  # 返回新添加的成员信息
    project_space = session.get(
        ProjectSpace, project_id
    )  # 根据项目 ID 查询项目空间是否存在

    if project_space is None:  # 如果项目空间不存在
        raise ValueError("项目空间不存在")  # 抛出业务错误

    if not can_manage_project(  # 判断当前用户是否有管理项目成员的权限
        session=session,  # 传入数据库会话
        project_id=project_id,  # 传入项目空间 ID
        user=current_user,  # 传入当前登录用户
    ):  # 权限判断结束
        raise PermissionError("没有权限添加项目成员")  # 抛出权限错误

    target_user = session.get(
        User, request_data.user_id
    )  # 查询要添加的目标用户是否存在

    if target_user is None:  # 如果目标用户不存在
        raise ValueError("要添加的用户不存在")  # 抛出业务错误

    existing_statement = (  # 构造查询已有成员记录的语句
        select(ProjectMember)  # 查询 ProjectMember 表
        .where(ProjectMember.project_id == project_id)  # 条件 1：项目 ID 相同
        .where(ProjectMember.user_id == request_data.user_id)  # 条件 2：用户 ID 相同
    )  # 查询语句构造结束

    existing_member = session.exec(
        existing_statement
    ).first()  # 执行查询，检查用户是否已经是项目成员

    if existing_member is not None:  # 如果已经存在成员记录
        raise ValueError("该用户已经是项目成员")  # 抛出业务错误，避免重复添加

    now = datetime.utcnow()  # 获取当前 UTC 时间

    member = ProjectMember(  # 创建项目成员数据库对象
        project_id=project_id,  # 设置成员所属项目空间 ID
        user_id=request_data.user_id,  # 设置成员对应的用户 ID
        role=request_data.role,  # 设置成员角色：admin / member / viewer
        created_at=now,  # 设置创建时间
        updated_at=now,  # 设置更新时间
    )  # 项目成员对象创建结束

    session.add(member)  # 把项目成员对象加入数据库会话
    session.commit()  # 提交事务，把成员保存到数据库
    session.refresh(member)  # 刷新成员对象，拿到数据库生成的 ID

    return build_project_member_response(member)  # 返回新成员响应对象


def update_project_member_role(  # 定义函数：修改项目成员角色
    session: Session,  # 数据库会话对象
    project_id: int,  # 项目空间 ID
    member_id: int,  # 要修改的成员记录 ID
    request_data: ProjectMemberUpdateRoleRequest,  # 修改角色请求数据
    current_user: User,  # 当前登录用户
) -> ProjectMemberResponse:  # 返回修改后的成员信息
    project_space = session.get(ProjectSpace, project_id)  # 查询项目空间是否存在

    if project_space is None:  # 如果项目空间不存在
        raise ValueError("项目空间不存在")  # 抛出业务错误

    if not can_manage_project(  # 判断当前用户是否有管理项目的权限
        session=session,  # 传入数据库会话
        project_id=project_id,  # 传入项目空间 ID
        user=current_user,  # 传入当前登录用户
    ):  # 权限判断结束
        raise PermissionError("没有权限修改项目成员角色")  # 抛出权限错误

    member = session.get(ProjectMember, member_id)  # 根据成员记录 ID 查询成员

    if member is None:  # 如果成员记录不存在
        raise ValueError("项目成员不存在")  # 抛出业务错误

    if member.project_id != project_id:  # 如果成员记录不属于当前项目空间
        raise ValueError("项目成员不属于当前项目空间")  # 抛出业务错误，避免跨项目误操作

    member.role = request_data.role  # 更新成员角色
    member.updated_at = datetime.utcnow()  # 更新成员记录的更新时间

    session.add(member)  # 把修改后的成员对象加入数据库会话
    session.commit()  # 提交事务，保存修改
    session.refresh(member)  # 刷新成员对象，拿到数据库最新数据

    return build_project_member_response(member)  # 返回修改后的成员响应对象


def remove_project_member(  # 定义函数：移除项目成员
    session: Session,  # 数据库会话对象
    project_id: int,  # 项目空间 ID
    member_id: int,  # 要移除的成员记录 ID
    current_user: User,  # 当前登录用户
) -> bool:  # 返回 True 表示删除成功
    project_space = session.get(ProjectSpace, project_id)  # 查询项目空间是否存在

    if project_space is None:  # 如果项目空间不存在
        raise ValueError("项目空间不存在")  # 抛出业务错误

    if not can_manage_project(  # 判断当前用户是否有管理项目成员的权限
        session=session,  # 传入数据库会话
        project_id=project_id,  # 传入项目空间 ID
        user=current_user,  # 传入当前登录用户
    ):  # 权限判断结束
        raise PermissionError("没有权限移除项目成员")  # 抛出权限错误

    member = session.get(ProjectMember, member_id)  # 根据成员记录 ID 查询成员

    if member is None:  # 如果成员记录不存在
        raise ValueError("项目成员不存在")  # 抛出业务错误

    if member.project_id != project_id:  # 如果成员记录不属于当前项目空间
        raise ValueError("项目成员不属于当前项目空间")  # 抛出业务错误，避免跨项目误删

    if current_user.id == member.user_id:  # 如果当前 admin 正在尝试移除自己
        raise ValueError(
            "不能移除自己，如需退出项目请先转交管理员权限"
        )  # 阻止管理员把自己移出项目

    session.delete(member)  # 从数据库会话中删除成员对象
    session.commit()  # 提交事务，正式删除成员记录

    return True  # 返回 True，表示移除成功



