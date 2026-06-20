#注册成功
#重复注册失败
#登录成功
#错误密码登录失败
#未登录不能访问 /users/me
#无效 token 不能访问 /users/me
#合法 token 可以访问 /users/me
#响应里不会泄露 password / hashed_password

import uuid  # 导入 uuid，用来生成随机用户名，避免重复注册导致测试失败

from fastapi.testclient import TestClient  # 导入 FastAPI 测试客户端，用来模拟接口请求

from main import app  # 导入 FastAPI 应用实例，TestClient 会直接请求这个 app

client = TestClient(app)  # 创建测试客户端，不需要启动 uvicorn 也能请求接口


def make_unique_username() -> str:  # 定义生成唯一用户名的辅助函数
    return f"test_user_{uuid.uuid4().hex[:8]}"  # 返回带随机后缀的用户名，避免和数据库已有用户冲突


def register_and_login_test_user() -> (
    tuple[str, str]
):  # 定义注册并登录测试用户的辅助函数，返回用户名和 access_token
    username = make_unique_username()  # 生成唯一用户名，避免重复注册冲突

    register_response = client.post(  # 请求注册接口
        "/users/register",  # 注册接口路径
        json={  # 设置注册请求体
            "username": username,  # 使用随机用户名
            "password": "123456",  # 使用固定测试密码
        },  # 结束注册请求体
    )  # 得到注册响应

    assert register_response.status_code == 200  # 断言注册成功

    login_response = client.post(  # 请求登录接口
        "/users/login",  # 登录接口路径
        json={  # 设置登录请求体
            "username": username,  # 使用刚注册的用户名
            "password": "123456",  # 使用正确密码
        },  # 结束登录请求体
    )  # 得到登录响应

    assert login_response.status_code == 200  # 断言登录成功

    token = login_response.json()["access_token"]  # 从登录响应里取出 access_token

    return username, token  # 返回用户名和 token，方便后续测试接口鉴权


def test_register_user_should_create_user_successfully():  # 测试注册接口是否能成功创建用户
    username = make_unique_username()  # 生成一个唯一用户名，避免重复注册

    response = client.post(  # 使用 TestClient 发送 POST 请求
        "/users/register",  # 请求用户注册接口
        json={  # 设置请求体 JSON
            "username": username,  # 传入用户名
            "password": "123456",  # 传入测试密码
        },  # 请求体结束
    )  # 请求结束，得到响应对象

    assert response.status_code == 200  # 断言注册成功时 HTTP 状态码为 200

    data = response.json()  # 把响应 JSON 转成 Python 字典

    assert data["username"] == username  # 断言返回的用户名等于刚才注册的用户名
    assert "id" in data  # 断言返回结果里包含用户 ID
    assert "created_at" in data  # 断言返回结果里包含创建时间
    assert "updated_at" in data  # 断言返回结果里包含更新时间
    assert "password" not in data  # 断言响应里不能返回明文密码
    assert "hashed_password" not in data  # 断言响应里不能返回密码哈希


def test_login_user_should_return_access_token():  # 测试登录接口是否能返回 access_token
    username = make_unique_username()  # 生成唯一用户名，避免和已有用户冲突

    register_response = client.post(  # 先调用注册接口创建测试用户
        "/users/register",  # 请求注册接口
        json={  # 设置注册请求体
            "username": username,  # 使用随机用户名
            "password": "123456",  # 设置测试密码
        },  # 结束注册请求体
    )  # 得到注册响应

    assert register_response.status_code == 200  # 断言注册成功

    login_response = client.post(  # 调用登录接口
        "/users/login",  # 请求登录接口
        json={  # 设置登录请求体
            "username": username,  # 传入刚刚注册的用户名
            "password": "123456",  # 传入正确密码
        },  # 结束登录请求体
    )  # 得到登录响应

    assert login_response.status_code == 200  # 断言登录成功

    data = login_response.json()  # 把登录响应 JSON 转成字典

    assert "access_token" in data  # 断言返回结果里包含 access_token
    assert data["access_token"]  # 断言 access_token 不是空字符串
    assert data["token_type"] == "bearer"  # 断言 token 类型是 bearer


def test_get_current_user_should_return_user_when_token_is_valid():  # 测试携带合法 token 访问 /users/me 是否返回当前用户
    username, token = (
        register_and_login_test_user()
    )  # 先注册并登录一个测试用户，拿到用户名和 token

    response = client.get(  # 请求当前用户信息接口
        "/users/me",  # 当前用户接口路径
        headers={  # 设置请求头
            "Authorization": f"Bearer {token}",  # 按 Bearer Token 格式携带 access_token
        },  # 结束请求头
    )  # 得到接口响应

    assert response.status_code == 200  # 断言携带合法 token 时访问成功

    data = response.json()  # 把响应 JSON 转成字典

    assert data["username"] == username  # 断言返回的用户名就是当前登录用户
    assert "id" in data  # 断言返回用户 ID
    assert "created_at" in data  # 断言返回创建时间
    assert "updated_at" in data  # 断言返回更新时间
    assert "password" not in data  # 断言不会返回明文密码
    assert "hashed_password" not in data  # 断言不会返回密码哈希


def test_register_user_should_fail_when_username_exists():  # 测试重复注册是否返回错误
    username = make_unique_username()  # 生成唯一用户名，避免和旧数据冲突

    first_response = client.post(  # 第一次注册
        "/users/register",  # 注册接口路径
        json={  # 注册请求体
            "username": username,  # 使用唯一用户名
            "password": "123456",  # 设置测试密码
        },  # 结束请求体
    )  # 得到第一次注册响应

    assert first_response.status_code == 200  # 断言第一次注册成功

    second_response = client.post(  # 第二次使用同一个用户名注册
        "/users/register",  # 注册接口路径
        json={  # 注册请求体
            "username": username,  # 使用相同用户名
            "password": "123456",  # 设置测试密码
        },  # 结束请求体
    )  # 得到第二次注册响应

    assert second_response.status_code == 400  # 断言重复注册返回 400
    assert second_response.json()["detail"] == "用户名已存在"  # 断言错误信息正确


def test_login_user_should_fail_when_password_is_wrong():  # 测试密码错误时登录是否失败
    username = make_unique_username()  # 生成唯一用户名

    register_response = client.post(  # 先注册用户
        "/users/register",  # 注册接口路径
        json={  # 注册请求体
            "username": username,  # 使用唯一用户名
            "password": "123456",  # 正确密码
        },  # 结束请求体
    )  # 得到注册响应

    assert register_response.status_code == 200  # 断言注册成功

    login_response = client.post(  # 使用错误密码登录
        "/users/login",  # 登录接口路径
        json={  # 登录请求体
            "username": username,  # 使用刚注册的用户名
            "password": "wrong-password",  # 故意传入错误密码
        },  # 结束请求体
    )  # 得到登录响应

    assert login_response.status_code == 401  # 断言密码错误返回 401
    assert login_response.json()["detail"] == "用户名或密码错误"  # 断言错误信息正确


def test_get_current_user_should_fail_when_no_token():  # 测试没有携带 token 访问 /users/me 是否失败
    response = client.get(
        "/users/me"
    )  # 不带 Authorization 请求头，直接访问当前用户接口

    assert response.status_code in [
        401,
        403,
    ]  # 断言未登录访问会失败，HTTPBearer 常见返回 403


def test_get_current_user_should_fail_when_token_is_invalid():  # 测试携带无效 token 访问 /users/me 是否失败
    response = client.get(  # 请求当前用户接口
        "/users/me",  # 当前用户接口路径
        headers={  # 设置请求头
            "Authorization": "Bearer invalid-token",  # 故意传入无效 token
        },  # 结束请求头
    )  # 得到接口响应

    assert response.status_code == 401  # 断言无效 token 返回 401
    assert response.json()["detail"] == "无效或已过期的 Token"  # 断言错误信息正确
