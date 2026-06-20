from sqlmodel import (
    Session,
    select,
)  # 导入 Session 用来操作数据库，导入 select 用来查询数据

from models import (
    ProjectMember,
    ProjectRole,
    User,
)  # 导入项目成员表、项目角色枚举、用户表


def get_project_member(  # 定义函数：查询某个用户在某个项目空间里的成员记录
    session: Session,  # 数据库会话对象，用来执行 SQL 查询
    project_id: int,  # 项目空间 ID，用来指定要检查哪个项目
    user: User,  # 当前登录用户对象，用来获取用户 ID
) -> ProjectMember | None:  # 返回 ProjectMember 对象；如果用户不属于该项目，则返回 None
    if user.id is None:  # 如果当前用户没有 ID，说明用户数据异常或还没有正确入库
        return None  # 直接返回 None，表示没有任何项目权限

    statement = (  # 构造 SQL 查询语句
        select(ProjectMember)  # 查询 ProjectMember 表
        .where(
            ProjectMember.project_id == project_id
        )  # 条件 1：项目 ID 必须等于传入的 project_id
        .where(
            ProjectMember.user_id == user.id
        )  # 条件 2：用户 ID 必须等于当前登录用户的 ID
    )  # 查询语句构造结束

    return session.exec(
        statement
    ).first()  # 执行查询，并返回第一条成员记录；如果没有查到则返回 None


def get_project_role(  # 定义函数：获取某个用户在某个项目空间里的角色
    session: Session,  # 数据库会话对象
    project_id: int,  # 项目空间 ID
    user: User,  # 当前登录用户对象
) -> (
    str | None
):  # 返回角色字符串，例如 admin/member/viewer；如果不是项目成员则返回 None
    member = get_project_member(  # 调用上面的函数，先查询项目成员记录
        session=session,  # 传入数据库会话
        project_id=project_id,  # 传入项目空间 ID
        user=user,  # 传入当前登录用户
    )  # 成员记录查询结束

    if member is None:  # 如果没有查到成员记录，说明当前用户不属于这个项目
        return None  # 返回 None，表示没有角色

    return member.role  # 返回当前用户在该项目里的角色


def can_view_project(  # 定义函数：判断当前用户是否可以查看项目空间
    session: Session,  # 数据库会话对象
    project_id: int,  # 项目空间 ID
    user: User,  # 当前登录用户对象
) -> bool:  # 返回布尔值：True 表示可以查看，False 表示不可以查看
    role = get_project_role(  # 获取当前用户在这个项目里的角色
        session=session,  # 传入数据库会话
        project_id=project_id,  # 传入项目空间 ID
        user=user,  # 传入当前登录用户
    )  # 角色获取结束

    return role in [  # 判断角色是否在允许查看的角色列表中
        ProjectRole.ADMIN.value,  # admin 可以查看项目
        ProjectRole.MEMBER.value,  # member 可以查看项目
        ProjectRole.VIEWER.value,  # viewer 可以查看项目
    ]  # 允许查看的角色列表结束


def can_write_project(  # 定义函数：判断当前用户是否可以写入项目内容
    session: Session,  # 数据库会话对象
    project_id: int,  # 项目空间 ID
    user: User,  # 当前登录用户对象
) -> bool:  # 返回布尔值：True 表示可以写入，False 表示不可以写入
    role = get_project_role(  # 获取当前用户在这个项目里的角色
        session=session,  # 传入数据库会话
        project_id=project_id,  # 传入项目空间 ID
        user=user,  # 传入当前登录用户
    )  # 角色获取结束

    return role in [  # 判断角色是否在允许写入的角色列表中
        ProjectRole.ADMIN.value,  # admin 可以写入项目内容
        ProjectRole.MEMBER.value,  # member 可以写入项目内容
    ]  # 允许写入的角色列表结束


def can_manage_project(  # 定义函数：判断当前用户是否可以管理项目
    session: Session,  # 数据库会话对象
    project_id: int,  # 项目空间 ID
    user: User,  # 当前登录用户对象
) -> bool:  # 返回布尔值：True 表示可以管理，False 表示不可以管理
    role = get_project_role(  # 获取当前用户在这个项目里的角色
        session=session,  # 传入数据库会话
        project_id=project_id,  # 传入项目空间 ID
        user=user,  # 传入当前登录用户
    )  # 角色获取结束

    return role == ProjectRole.ADMIN.value  # 只有 admin 角色才可以管理项目
