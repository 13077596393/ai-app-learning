from fastapi import (  # 从 FastAPI 导入常用组件
    APIRouter,  # APIRouter 用来创建路由分组
    Depends,  # Depends 用来注入依赖
    HTTPException,  # HTTPException 用来返回 HTTP 错误
)  # FastAPI 组件导入结束

from fastapi.responses import StreamingResponse  # 导入流式响应类型

from sqlmodel import Session  # 导入数据库会话类型，用来做项目权限校验

from database import get_session  # 导入数据库会话依赖

from models import ProjectSpace  # 导入 ProjectSpace，用来判断项目空间是否存在

from services.ai_service import (  # 导入 AI 回复相关服务函数
    generate_ai_reply,  # 导入非流式 AI 回复函数
    build_ai_messages,  # 导入把数据库历史消息转换成 LLM messages 的函数
    stream_llm_api,  # 导入流式调用 LLM 的函数
)  # AI 服务函数导入结束

from routers.users import get_current_user  # 导入当前用户鉴权依赖

from schemas import (  # 导入聊天相关请求和响应模型
    ChatMessageCreate,  # 导入创建聊天消息请求模型
    ChatMessageResponse,  # 导入聊天消息响应模型
    ChatResponse,  # 导入发送消息完整响应模型
    ChatSessionCreate,  # 导入创建聊天会话请求模型，里面现在需要有 project_id
    ChatSessionResponse,  # 导入聊天会话响应模型，里面现在需要有 project_id
)  # schemas 导入结束

from services.user_service import (  # 导入聊天数据访问服务函数
    create_chat_message,  # 导入创建聊天消息函数
    create_chat_session,  # 导入创建聊天会话函数
    find_chat_session_by_id,  # 导入按 ID 查询聊天会话函数
    find_chat_sessions_by_project_id,  # 导入按项目空间 ID 查询会话列表函数，后面需要在 user_service.py 里新增
    find_messages_by_session_id,  # 导入按会话 ID 查询消息列表函数
)  # user_service 导入结束

from services.project_permission_service import (
    can_view_project,
)  # 导入项目查看权限判断函数

from tools import execute_tool_call, llm_tool_decision  # 导入工具调用决策和执行函数
from services.rate_limit_service import (
    check_rate_limit,
)  # 导入限流检查函数，用来限制用户频繁调用 AI 接口
from services.prompt_security_service import (  # 导入提示词安全检查函数
    validate_prompt_security,  # 用来检查普通聊天输入是否包含 Prompt Injection 内容
)  # 提示词安全服务导入结束

router = APIRouter(  # 创建聊天模块路由对象
    prefix="/chat",  # 设置统一路径前缀
    tags=["chat"],  # 设置 Swagger 分组名称
)  # 路由对象创建结束


def get_chat_session_for_current_user(  # 定义工具函数：查询会话并校验当前用户是否有查看权限
    session_id: int,  # 会话 ID
    db_session: Session,  # 数据库会话对象
    current_user,  # 当前登录用户
):  # 函数参数定义结束
    chat_session = find_chat_session_by_id(session_id)  # 根据会话 ID 查询聊天会话

    if chat_session is None:  # 如果会话不存在
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=404,  # 404 表示资源不存在
            detail="聊天会话不存在",  # 返回错误提示
        )  # HTTPException 结束

    if not can_view_project(  # 判断当前用户是否可以查看该会话所属项目空间
        session=db_session,  # 传入数据库会话
        project_id=chat_session.project_id,  # 使用会话所属项目空间 ID 做权限判断
        user=current_user,  # 传入当前登录用户
    ):  # 权限判断结束
        raise HTTPException(  # 如果无权访问
            status_code=404,  # 返回 404，避免泄露会话是否存在
            detail="聊天会话不存在或无权访问",  # 返回错误提示
        )  # HTTPException 结束

    return chat_session  # 返回已通过权限校验的会话对象


@router.post("/sessions", response_model=ChatSessionResponse)  # 注册创建聊天会话接口
def create_session(  # 定义创建聊天会话处理函数
    session_data: ChatSessionCreate,  # 接收创建会话请求数据，里面包含 project_id 和 title
    db_session: Session = Depends(
        get_session
    ),  # 注入数据库会话，用来查询项目空间和做权限判断
    current_user=Depends(get_current_user),  # 注入当前登录用户
):  # 函数参数定义结束
    if current_user.id is None:  # 判断当前用户是否没有有效 ID
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=400,  # 400 表示当前用户状态不合法
            detail="当前用户没有有效 ID，无法创建会话",  # 返回错误提示
        )  # HTTPException 结束

    project_space = db_session.get(  # 根据 project_id 查询项目空间
        ProjectSpace,  # 要查询的模型是 ProjectSpace
        session_data.project_id,  # 使用请求体里的 project_id 查询
    )  # 项目空间查询结束

    if project_space is None:  # 如果项目空间不存在
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=404,  # 404 表示项目空间不存在
            detail="项目空间不存在",  # 返回错误提示
        )  # HTTPException 结束

    if not can_view_project(  # 判断当前用户是否可以查看该项目空间
        session=db_session,  # 传入数据库会话
        project_id=session_data.project_id,  # 传入项目空间 ID
        user=current_user,  # 传入当前登录用户
    ):  # 权限判断结束
        raise HTTPException(  # 如果当前用户不是项目成员
            status_code=404,  # 返回 404，避免泄露项目空间是否存在
            detail="项目空间不存在或无权访问",  # 返回错误提示
        )  # HTTPException 结束

    chat_session = create_chat_session(  # 调用服务层创建聊天会话
        user_id=current_user.id,  # 设置创建者为当前登录用户
        title=session_data.title,  # 设置会话标题
        project_id=session_data.project_id,  # 设置会话所属项目空间
    )  # 会话创建调用结束

    return chat_session  # 返回创建完成的聊天会话


@router.get(
    "/sessions", response_model=list[ChatSessionResponse]
)  # 注册获取项目空间会话列表接口
def get_project_sessions(  # 定义查询项目空间会话列表处理函数
    project_id: int,  # 从 query 参数接收项目空间 ID，例如 /chat/sessions?project_id=1
    db_session: Session = Depends(get_session),  # 注入数据库会话
    current_user=Depends(get_current_user),  # 注入当前登录用户
):  # 函数参数定义结束
    project_space = db_session.get(  # 根据 project_id 查询项目空间
        ProjectSpace,  # 要查询的模型是 ProjectSpace
        project_id,  # 查询传入的项目空间 ID
    )  # 项目空间查询结束

    if project_space is None:  # 如果项目空间不存在
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=404,  # 404 表示项目空间不存在
            detail="项目空间不存在",  # 返回错误提示
        )  # HTTPException 结束

    if not can_view_project(  # 判断当前用户是否可以查看该项目空间
        session=db_session,  # 传入数据库会话
        project_id=project_id,  # 传入项目空间 ID
        user=current_user,  # 传入当前登录用户
    ):  # 权限判断结束
        raise HTTPException(  # 如果无权查看
            status_code=404,  # 返回 404，避免泄露项目空间是否存在
            detail="项目空间不存在或无权访问",  # 返回错误提示
        )  # HTTPException 结束

    chat_sessions = find_chat_sessions_by_project_id(  # 查询该项目空间下的所有会话
        project_id=project_id,  # 传入项目空间 ID
    )  # 会话列表查询结束

    return chat_sessions  # 返回项目空间下的聊天会话列表


@router.post("/messages", response_model=ChatResponse)  # 注册发送普通聊天消息接口
def send_message(  # 定义发送消息处理函数
    message_data: ChatMessageCreate,  # 接收创建消息请求数据
    db_session: Session = Depends(get_session),  # 注入数据库会话，用来做会话权限校验
    current_user=Depends(get_current_user),  # 注入当前登录用户
):  # 函数参数定义结束
    chat_session = (
        get_chat_session_for_current_user(  # 查询会话并校验当前用户是否有权限访问
            session_id=message_data.session_id,  # 传入请求中的会话 ID
            db_session=db_session,  # 传入数据库会话
            current_user=current_user,  # 传入当前登录用户
        )
    )  # 会话查询和权限校验结束
    user_content = message_data.content.strip()  # 去掉用户消息前后的空白字符

    if not user_content:  # 判断用户消息是否为空
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=400,  # 400 表示参数不合法
            detail="消息内容不能为空",  # 返回错误提示
        )  # HTTPException 结束

    validate_prompt_security(  # 检查用户消息是否包含 Prompt Injection 内容
        user_content  # 传入用户原始消息
    )  # 安全检查结束
    check_rate_limit(  # 检查当前用户调用普通聊天接口是否过于频繁
        user_id=current_user.id,  # 使用当前登录用户 ID 做限流维度
        action="chat_message",  # 普通聊天接口使用 chat_message 限流规则
    )  # 限流检查结束，超过限制会直接返回 429
    if message_data.role != "user":  # 判断请求角色是否为用户消息
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=400,  # 400 表示请求数据不合法
            detail="当前阶段只能发送 user 消息",  # 返回错误提示
        )  # HTTPException 结束

    user_message = create_chat_message(  # 保存用户发送的消息
        session_id=chat_session.id,  # 设置消息所属会话 ID
        role="user",  # 固定保存为用户角色
        content=message_data.content,  # 保存用户输入内容
    )  # 用户消息创建结束

    tool_call = llm_tool_decision(
        message_data.content
    )  # 让大模型判断本条消息是否需要调用工具

    tool_result = execute_tool_call(tool_call)  # 根据工具调用决策执行对应工具

    if tool_result["type"] == "tool_result":  # 判断工具是否执行成功并返回结果
        assistant_content = f"工具 {tool_result['tool_name']} 执行结果：{tool_result['result']}"  # 构造工具结果回复内容

        assistant_message = create_chat_message(  # 保存工具结果对应的助手消息
            session_id=chat_session.id,  # 设置消息所属会话 ID
            role="assistant",  # 设置消息角色为助手
            content=assistant_content,  # 保存助手回复内容
        )  # 助手消息创建结束

        return {  # 返回用户消息、助手消息和工具结果
            "user_message": user_message,  # 返回保存后的用户消息
            "assistant_message": assistant_message,  # 返回保存后的助手消息
            "tool_result": tool_result,  # 返回工具执行结果
        }  # 响应返回结束

    if tool_result["type"] == "tool_error":  # 判断工具调用是否失败
        assistant_content = (
            f"工具调用失败：{tool_result['message']}"  # 构造工具失败回复内容
        )

        assistant_message = create_chat_message(  # 保存工具失败对应的助手消息
            session_id=chat_session.id,  # 设置消息所属会话 ID
            role="assistant",  # 设置消息角色为助手
            content=assistant_content,  # 保存助手回复内容
        )  # 助手消息创建结束

        return {  # 返回用户消息、助手消息和工具错误结果
            "user_message": user_message,  # 返回保存后的用户消息
            "assistant_message": assistant_message,  # 返回保存后的助手消息
            "tool_result": tool_result,  # 返回工具错误结果
        }  # 响应返回结束

    history_messages = find_messages_by_session_id(
        chat_session.id
    )  # 查询当前会话的完整历史消息

    ai_messages = build_ai_messages(
        history_messages
    )  # 将数据库消息转换为大模型消息格式

    ai_reply_content = generate_ai_reply(ai_messages)  # 调用大模型生成助手回复

    assistant_message = create_chat_message(  # 保存大模型生成的助手消息
        session_id=chat_session.id,  # 设置消息所属会话 ID
        role="assistant",  # 设置消息角色为助手
        content=ai_reply_content,  # 保存大模型回复内容
    )  # 助手消息创建结束

    return {  # 返回普通聊天响应
        "user_message": user_message,  # 返回保存后的用户消息
        "assistant_message": assistant_message,  # 返回保存后的助手消息
        "tool_result": None,  # 表示本次没有工具调用结果
    }  # 响应返回结束


@router.post("/messages/stream")  # 注册发送流式聊天消息接口
def send_message_stream(  # 定义发送流式消息处理函数
    message_data: ChatMessageCreate,  # 接收创建消息请求数据
    db_session: Session = Depends(get_session),  # 注入数据库会话，用来做会话权限校验
    current_user=Depends(get_current_user),  # 注入当前登录用户
):  # 函数参数定义结束
    chat_session = get_chat_session_for_current_user(  # 查询会话并校验权限
        session_id=message_data.session_id,  # 传入会话 ID
        db_session=db_session,  # 传入数据库会话
        current_user=current_user,  # 传入当前登录用户
    )  # 会话查询和权限校验结束
    user_content = message_data.content.strip()  # 去掉用户消息前后的空白字符

    if not user_content:  # 判断用户消息是否为空
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=400,  # 400 表示参数不合法
            detail="消息内容不能为空",  # 返回错误提示
        )  # HTTPException 结束

    validate_prompt_security(  # 检查用户消息是否包含 Prompt Injection 内容
        user_content  # 传入用户原始消息
    )  # 安全检查结束
    check_rate_limit(  # 检查当前用户调用流式聊天接口是否过于频繁
        user_id=current_user.id,  # 使用当前登录用户 ID 做限流维度
        action="chat_message",  # 流式聊天也归类为 chat_message，和普通聊天共享额度
    )  # 限流检查结束，超过限制会直接返回 429
    if message_data.role != "user":  # 判断请求角色是否为用户消息
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=400,  # 400 表示请求数据不合法
            detail="当前阶段只能发送 user 消息",  # 返回错误提示
        )  # HTTPException 结束

    create_chat_message(  # 保存用户发送的消息
        session_id=chat_session.id,  # 设置消息所属会话 ID
        role="user",  # 固定保存为用户角色
        content=message_data.content,  # 保存用户输入内容
    )  # 用户消息创建结束

    history_messages = find_messages_by_session_id(
        chat_session.id
    )  # 查询当前会话的完整历史消息

    ai_messages = build_ai_messages(
        history_messages
    )  # 将数据库消息转换为大模型消息格式

    def generate_stream():  # 定义内部生成器，用于持续产出模型文本
        full_reply = ""  # 初始化完整回复文本，便于流式结束后保存

        for content in stream_llm_api(ai_messages):  # 逐段读取大模型流式输出
            full_reply += content  # 累加当前片段到完整回复中
            yield content  # 立即把当前片段返回给客户端

        create_chat_message(  # 流式输出结束后保存完整助手回复
            session_id=chat_session.id,  # 设置消息所属会话 ID
            role="assistant",  # 设置消息角色为助手
            content=full_reply,  # 保存拼接后的完整回复
        )  # 助手消息创建结束

    return StreamingResponse(  # 返回 FastAPI 流式响应
        generate_stream(),  # 使用内部生成器作为响应体
        media_type="text/plain; charset=utf-8",  # 设置返回内容类型和编码
    )  # 流式响应构造结束


@router.get(  # 注册查询指定会话消息列表接口
    "/sessions/{session_id}/messages",  # 注册查询指定会话消息列表的路径
    response_model=list[ChatMessageResponse],  # 设置响应模型为聊天消息列表
)  # 路由装饰器结束
def get_session_messages(  # 定义查询会话消息列表处理函数
    session_id: int,  # 接收路径参数中的会话 ID
    db_session: Session = Depends(get_session),  # 注入数据库会话，用来做权限校验
    current_user=Depends(get_current_user),  # 注入当前登录用户
):  # 函数参数定义结束
    chat_session = (
        get_chat_session_for_current_user(  # 查询会话并校验当前用户是否有权限访问
            session_id=session_id,  # 传入会话 ID
            db_session=db_session,  # 传入数据库会话
            current_user=current_user,  # 传入当前登录用户
        )
    )  # 会话查询和权限校验结束

    messages = find_messages_by_session_id(chat_session.id)  # 查询该会话下的所有消息

    return messages  # 返回聊天消息列表
