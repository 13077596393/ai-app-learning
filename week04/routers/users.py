from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)  # 导入路由、依赖注入、异常和状态码工具
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)  # 导入 Bearer Token 鉴权工具

from schemas import (
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)  # 导入用户相关请求和响应模型
from security import (  # 导入安全相关工具函数
    create_access_token,  # 导入访问令牌创建函数
    decode_access_token,  # 导入访问令牌解析函数
    hash_password,  # 导入密码哈希函数
    verify_password,  # 导入密码校验函数
)  # 结束安全工具函数导入
from services.user_service import (
    create_user,
    find_user_by_id,
    find_user_by_username,
)  # 导入用户数据访问服务函数

router = APIRouter(
    prefix="/users", tags=["users"]
)  # 创建用户模块路由并设置统一路径前缀和标签

bearer_scheme = HTTPBearer()  # 创建 HTTP Bearer 认证依赖对象


def get_current_user(  # 定义获取当前登录用户的依赖函数
    credentials: HTTPAuthorizationCredentials = Depends(
        bearer_scheme
    ),  # 从请求头中读取 Bearer Token
):  # 结束当前用户依赖函数参数声明
    token = credentials.credentials  # 提取真正的 JWT 字符串

    payload = decode_access_token(token)  # 解析并校验访问令牌

    if payload is None:  # 判断令牌是否解析失败
        raise HTTPException(  # 抛出未认证异常
            status_code=status.HTTP_401_UNAUTHORIZED,  # 设置 HTTP 状态码为 401
            detail="无效或已过期的 Token",  # 返回令牌无效或过期的错误信息
        )  # 结束异常构造

    user_id = payload.get("sub")  # 从令牌载荷中读取用户 ID

    if user_id is None:  # 判断令牌中是否缺少用户 ID
        raise HTTPException(  # 抛出未认证异常
            status_code=status.HTTP_401_UNAUTHORIZED,  # 设置 HTTP 状态码为 401
            detail="Token 中缺少用户信息",  # 返回令牌缺少用户信息的错误提示
        )  # 结束异常构造

    db_user = find_user_by_id(int(user_id))  # 根据令牌中的用户 ID 查询数据库用户

    if db_user is None:  # 判断数据库中是否找不到对应用户
        raise HTTPException(  # 抛出未认证异常
            status_code=status.HTTP_401_UNAUTHORIZED,  # 设置 HTTP 状态码为 401
            detail="用户不存在",  # 返回用户不存在的错误提示
        )  # 结束异常构造

    return db_user  # 返回当前登录用户对象


@router.post("/register", response_model=UserResponse)  # 注册用户创建接口
def register_user(user: UserRegister):  # 定义用户注册处理函数
    existing_user = find_user_by_username(user.username)  # 根据用户名检查用户是否已存在

    if existing_user is not None:  # 如果用户名已被占用
        raise HTTPException(
            status_code=400, detail="用户名已存在"
        )  # 返回用户名重复的请求错误

    hashed_password = hash_password(user.password)  # 对注册密码进行哈希处理

    new_user = create_user(user.username, hashed_password)  # 创建新用户并写入数据库

    return new_user  # 返回创建完成的用户信息


@router.post("/login", response_model=TokenResponse)  # 注册用户登录接口
def login_user(user: UserLogin):  # 定义用户登录处理函数
    db_user = find_user_by_username(user.username)  # 根据用户名查询数据库用户

    if db_user is None:  # 判断用户是否不存在
        raise HTTPException(
            status_code=401, detail="用户名或密码错误"
        )  # 返回统一的账号或密码错误提示

    is_valid_password = verify_password(
        user.password, db_user.hashed_password
    )  # 校验输入密码和数据库哈希密码是否匹配

    if is_valid_password is False:  # 判断密码是否校验失败
        raise HTTPException(
            status_code=401, detail="用户名或密码错误"
        )  # 返回统一的账号或密码错误提示

    access_token = create_access_token(  # 创建登录成功后的访问令牌
        data={  # 设置写入 JWT 的业务载荷
            "sub": str(db_user.id),  # 使用用户 ID 作为令牌主体
            "username": db_user.username,  # 将用户名写入令牌载荷
        }  # 结束 JWT 业务载荷
    )  # 结束访问令牌创建

    return {  # 返回登录令牌响应
        "access_token": access_token,  # 返回生成好的 JWT
        "token_type": "bearer",  # 告诉客户端令牌类型为 bearer
    }  # 结束响应字典


@router.get("/me", response_model=UserResponse)  # 注册获取当前用户信息接口
def read_current_user(
    current_user=Depends(get_current_user),
):  # 通过依赖注入获取当前登录用户
    return current_user  # 返回当前登录用户信息
