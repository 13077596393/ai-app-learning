from datetime import datetime, timedelta  # 导入时间工具，用来生成 JWT 过期时间

from jose import JWTError, jwt  # 导入 JWT 编解码工具和 JWT 异常类型
from passlib.context import CryptContext  # 导入密码哈希上下文工具

from settings import settings  # 导入项目统一配置对象，用来读取 JWT 配置

pwd_context = CryptContext(  # 创建密码哈希上下文
    schemes=["bcrypt"],  # 指定使用 bcrypt 算法保存密码哈希
    deprecated="auto",  # 自动处理旧算法废弃策略
)  # 密码哈希上下文创建结束


def hash_password(password: str) -> str:  # 定义密码哈希函数，接收用户明文密码
    hashed_password = pwd_context.hash(password)  # 使用 bcrypt 对明文密码进行哈希

    return hashed_password  # 返回哈希后的密码字符串


def verify_password(  # 定义密码校验函数
    plain_password: str,  # 用户登录时输入的明文密码
    hashed_password: str,  # 数据库里保存的哈希密码
) -> bool:  # 返回密码是否匹配
    is_valid = pwd_context.verify(  # 使用 passlib 校验明文密码和哈希密码是否匹配
        plain_password,  # 传入用户输入的明文密码
        hashed_password,  # 传入数据库中的哈希密码
    )  # 密码校验结束

    return is_valid  # 返回校验结果，True 表示密码正确，False 表示密码错误


def create_access_token(data: dict) -> str:  # 定义访问令牌创建函数
    to_encode = data.copy()  # 复制原始载荷，避免直接修改调用方传入的数据

    expire = datetime.utcnow() + timedelta(  # 计算 JWT 过期时间
        minutes=settings.jwt_expire_minutes  # 从 settings 读取过期分钟数
    )  # 过期时间计算结束

    to_encode.update(  # 给 JWT 载荷追加过期时间
        {"exp": expire}  # exp 是 JWT 标准过期时间字段
    )  # 载荷更新结束

    encoded_jwt = jwt.encode(  # 编码生成 JWT 字符串
        to_encode,  # 传入要写入 JWT 的载荷
        settings.jwt_secret_key,  # 从 settings 读取 JWT 签名密钥
        algorithm=settings.jwt_algorithm,  # 从 settings 读取 JWT 签名算法
    )  # JWT 编码结束

    return encoded_jwt  # 返回生成好的访问令牌


def decode_access_token(token: str) -> dict | None:  # 定义访问令牌解析函数
    try:  # 尝试解析并校验 JWT
        payload = jwt.decode(  # 解码 JWT 并校验签名、算法和过期时间
            token,  # 传入客户端提交的 JWT 字符串
            settings.jwt_secret_key,  # 从 settings 读取 JWT 签名密钥
            algorithms=[settings.jwt_algorithm],  # 从 settings 读取允许的 JWT 算法
        )  # JWT 解码结束

        return payload  # 解析成功时返回载荷字典

    except JWTError:  # 捕获令牌无效、过期、签名错误等 JWT 异常
        return None  # 解析失败时返回 None
