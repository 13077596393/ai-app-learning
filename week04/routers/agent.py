from fastapi import (  # 从 FastAPI 导入常用工具
    APIRouter,  # APIRouter 用来创建路由模块
    Depends,  # Depends 用来注入当前用户和数据库会话
    HTTPException,  # HTTPException 用来返回 HTTP 错误
)  # FastAPI 导入结束
from typing import Any  # 导入 Any 类型，用来给字典响应做类型标注
from sqlmodel import Session  # 导入数据库会话类型，用来做项目权限校验

from database import get_session  # 导入数据库会话依赖

from routers.users import get_current_user  # 导入当前登录用户依赖

from services.project_permission_service import (
    can_view_project,
)  # 导入项目查看权限判断函数
from schemas import (
    AgentState,
    AgentChatRequest,
    AgentChatResponse,
    AgentTaskActionResponse,
    AgentTaskCreateRequest,
    AgentTaskCreateResponse,
    AgentTaskSummaryResponse,
    AgentTaskDetailResponse,
    AgentTaskEventItem,
    AgentTaskEventsResponse,
    AgentTaskCancelResponse,
    BadCaseCreateRequest,
)  # 导入 Agent 相关请求体和响应体模型
from models import (  # 导入数据库模型
    AgentTask,  # 导入 AgentTask 数据库模型
    AgentStep,  # 导入 AgentStep 数据库模型
    ChatSession,  # 导入 ChatSession，用来校验 Agent 请求里的 session_id 权限
    KnowledgeBase,  # 导入 KnowledgeBase，用来校验 Agent 请求里的 knowledge_base_id 权限
)  # models 导入结束

# 导入 AgentStep 数据库模型，用来作为事件响应构造函数的参数类型
from services.agent_graph import (
    agent_graph,
)  # 从 agent_graph 导入已经编译好的 LangGraph 工作流对象
from services.agent_nodes import (
    generate_report_node,
)  # 导入报告生成节点，用户确认后继续复用这个节点生成报告

from services.agent_task_service import (
    create_agent_step,
)  # 导入创建任务步骤记录的服务函数

from services.agent_task_service import (
    get_agent_task,
)  # 导入根据任务 ID 查询 AgentTask 的服务函数

from services.agent_task_service import (
    update_agent_task_status,
)  # 导入更新 AgentTask 状态的服务函数
from services.agent_task_service import (
    can_retry_agent_task,
)  # 导入判断任务是否允许重试的服务函数

from services.agent_task_service import (
    increase_agent_task_retry_count,
)  # 导入增加任务重试次数的服务函数

from services.agent_task_service import (
    list_failed_agent_tasks,
)  # 导入查询失败任务列表的服务函数
from services.agent_task_service import (
    create_agent_step,
)  # 导入创建 AgentStep 步骤记录的服务函数

from services.agent_task_service import (
    create_agent_task,
)  # 导入创建 AgentTask 任务的服务函数

from services.agent_task_service import (
    update_agent_task_job_id,
)  # 导入更新 AgentTask 对应 RQ Job ID 的服务函数

from services.agent_task_service import (
    update_agent_task_progress,
)  # 导入更新 AgentTask 任务进度的服务函数
from services.agent_task_service import (
    list_agent_steps,
)  # 导入根据任务 ID 查询 AgentStep 列表的服务函数
from services.agent_task_service import (
    cancel_agent_task,
)  # 导入取消 Agent 后台任务的服务函数

from services.agent_worker_tasks import (
    run_agent_task,
)  # 导入后台 Worker 真正执行的任务函数

from services.rq_queue import (
    agent_task_queue,
)  # 导入 RQ 队列对象，用来把任务放入 Redis 队列

from services.agent_trace_service import (  # 从任务调用链服务中导入组装完整调用链的函数
    build_agent_task_trace,  # 导入 build_agent_task_trace，用来根据 task_id 生成完整 trace 结果
)  # 调用链服务导入结束
from services.bad_case_service import create_bad_case  # 导入创建 bad case 的服务函数
from services.report_approval_service import (  # 导入报告确认服务
    approve_report_task_save_and_export,  # 导入确认、保存并导出 Markdown 的函数
)  # 导入结束
from services.agent_task_service import (
    update_agent_task_final_result,
)  # 导入更新任务最终结果的函数
from services.rate_limit_service import (
    check_rate_limit,
)  # 导入限流检查函数，用来限制 Agent 任务创建频率
from services.prompt_security_service import (  # 导入提示词安全检查函数
    validate_prompt_security,  # 用来检查普通聊天输入是否包含 Prompt Injection 内容
)  # 提示词安全服务导入结束

router = APIRouter(
    prefix="/agent", tags=["Agent"]
)  # 创建 Agent 路由对象，统一前缀是 /agent，Swagger 分组名是 Agent

def validate_agent_request_project_permission(  # 定义 Agent 请求的项目空间权限校验函数
    session: Session,  # 数据库会话对象
    knowledge_base_id: int | None,  # 知识库 ID，可以为空
    chat_session_id: int | None,  # 聊天会话 ID，可以为空
    current_user,  # 当前登录用户
) -> int | None:  # 返回本次 Agent 请求所属项目空间 ID，如果没有传知识库和会话则返回 None
    project_id: int | None = None  # 初始化项目空间 ID，后面从知识库或会话中推导出来

    if knowledge_base_id is not None:  # 如果本次 Agent 请求传了知识库 ID
        knowledge_base = session.get(  # 根据知识库 ID 查询知识库
            KnowledgeBase,  # 要查询的模型是 KnowledgeBase
            knowledge_base_id,  # 查询传入的知识库 ID
        )  # 知识库查询结束

        if knowledge_base is None:  # 如果知识库不存在
            raise HTTPException(  # 抛出 HTTP 错误
                status_code=404,  # 404 表示资源不存在
                detail="知识库不存在",  # 返回错误提示
            )  # HTTPException 结束

        if not can_view_project(  # 判断当前用户是否可以查看知识库所属项目空间
            session=session,  # 传入数据库会话
            project_id=knowledge_base.project_id,  # 使用知识库所属项目空间 ID 做权限判断
            user=current_user,  # 传入当前登录用户
        ):  # 权限判断结束
            raise HTTPException(  # 如果没有权限访问该知识库
                status_code=404,  # 返回 404，避免泄露知识库是否存在
                detail="知识库不存在或无权访问",  # 返回错误提示
            )  # HTTPException 结束

        project_id = knowledge_base.project_id  # 把本次请求所属项目空间设置为知识库所属项目空间

    if chat_session_id is not None:  # 如果本次 Agent 请求传了会话 ID
        chat_session = session.get(  # 根据会话 ID 查询聊天会话
            ChatSession,  # 要查询的模型是 ChatSession
            chat_session_id,  # 查询传入的会话 ID
        )  # 聊天会话查询结束

        if chat_session is None:  # 如果聊天会话不存在
            raise HTTPException(  # 抛出 HTTP 错误
                status_code=404,  # 404 表示资源不存在
                detail="聊天会话不存在",  # 返回错误提示
            )  # HTTPException 结束

        if not can_view_project(  # 判断当前用户是否可以查看会话所属项目空间
            session=session,  # 传入数据库会话
            project_id=chat_session.project_id,  # 使用会话所属项目空间 ID 做权限判断
            user=current_user,  # 传入当前登录用户
        ):  # 权限判断结束
            raise HTTPException(  # 如果没有权限访问该会话
                status_code=404,  # 返回 404，避免泄露会话是否存在
                detail="聊天会话不存在或无权访问",  # 返回错误提示
            )  # HTTPException 结束

        if project_id is not None and chat_session.project_id != project_id:  # 如果知识库和会话都传了，但不属于同一个项目空间
            raise HTTPException(  # 抛出 HTTP 错误
                status_code=400,  # 400 表示请求参数组合不合法
                detail="当前聊天会话和知识库不属于同一个项目空间",  # 返回错误提示
            )  # HTTPException 结束

        project_id = chat_session.project_id  # 把本次请求所属项目空间设置为会话所属项目空间

    return project_id  # 返回本次 Agent 请求所属项目空间 ID

def build_task_message(status: str) -> str:  # 根据任务状态生成给前端或用户看的提示信息
    if status == "created":  # 判断任务是否刚创建
        return "任务已创建。"  # 返回 created 状态提示

    if status == "queued":  # 判断任务是否正在队列中等待执行
        return "任务正在排队执行。"  # 返回 queued 状态提示

    if status == "running":  # 判断任务是否正在执行
        return "任务正在执行中。"  # 返回 running 状态提示

    if status in ["success", "completed"]:  # 判断任务是否已经成功完成
        return "任务已完成。"  # 返回完成状态提示

    if status == "failed":  # 判断任务是否执行失败
        return "任务执行失败。"  # 返回 failed 状态提示

    if status == "cancelled":  # 判断任务是否已经取消
        return "任务已取消。"  # 返回 cancelled 状态提示

    return "任务状态未知。"  # 如果状态不在预设范围内，就返回未知状态提示


def build_agent_task_detail_response(
    task: AgentTask,
) -> AgentTaskDetailResponse:  # 把 AgentTask 数据库对象转换成任务详情响应体
    return AgentTaskDetailResponse(  # 返回 AgentTaskDetailResponse 响应对象
        success=True,  # 查询到任务时，success 返回 True
        task_id=task.id,  # 把数据库里的 id 转成接口里的 task_id
        task_type=task.task_type,  # 返回任务类型，例如 report
        task_status=task.status,  # 把数据库里的 status 转成接口里的 task_status
        progress=task.progress,  # 返回任务进度，范围是 0 到 100
        current_step=task.current_step,  # 返回当前任务执行步骤说明
        user_input=task.user_input,  # 返回用户创建任务时输入的原始内容
        answer=task.answer,  # 返回任务最终答案，任务未完成时通常是空字符串
        report_id=task.report_id,  # 返回报告 ID，任务未生成报告时为空
        markdown_file_path=task.markdown_file_path,  # 返回 Markdown 文件路径，任务未导出时为空
        job_id=task.job_id,  # 返回 RQ Job ID，任务未入队或入队失败时可以为空
        error=task.error,  # 返回任务错误信息，成功时为空
        queued_at=task.queued_at,  # 返回任务入队时间
        started_at=task.started_at,  # 返回 Worker 开始执行任务的时间
        finished_at=task.finished_at,  # 返回任务成功、失败或取消的结束时间
        created_at=task.created_at,  # 返回任务创建时间
        updated_at=task.updated_at,  # 返回任务最后更新时间
        message=build_task_message(task.status),  # 根据任务状态生成提示信息
    )  # 任务详情响应对象创建结束


def build_agent_task_event_item(
    step: AgentStep,
) -> AgentTaskEventItem:  # 把 AgentStep 数据库对象转换成接口返回的单个事件对象
    return AgentTaskEventItem(  # 返回 AgentTaskEventItem 响应对象
        step_id=step.id,  # 把数据库里的步骤 id 转成接口里的 step_id
        task_id=step.task_id,  # 返回这个步骤所属的任务 ID
        step_name=step.step_name,  # 返回步骤名称，例如 queue_task、retrieve_knowledge
        step_type=step.step_type,  # 返回步骤类型，例如 queue、worker、tool、system
        status=step.status,  # 返回步骤状态，例如 success、failed、running
        input_data=step.input_data or {},  # 返回步骤输入数据，如果为空就返回空字典
        output_data=step.output_data or {},  # 返回步骤输出数据，如果为空就返回空字典
        error=step.error,  # 返回步骤错误信息，成功时通常为空
        retry_count=step.retry_count,  # 返回当前步骤对应的重试次数
        is_retry=step.is_retry,  # 返回这个步骤是否属于重试过程
        started_at=step.started_at,  # 返回步骤开始时间
        finished_at=step.finished_at,  # 返回步骤结束时间
        created_at=step.created_at,  # 返回步骤记录创建时间
    )  # 单个事件响应对象创建结束


def build_agent_task_event_items(
    steps: list[AgentStep],
) -> list[AgentTaskEventItem]:  # 把多个 AgentStep 转换成多个事件响应对象
    return [  # 返回事件响应对象列表
        build_agent_task_event_item(step)  # 把当前 AgentStep 转换成 AgentTaskEventItem
        for step in steps  # 遍历所有 AgentStep 步骤记录
    ]  # 事件响应对象列表创建结束


@router.post(  # 注册 POST 接口
    "/chat",  # 设置接口路径为 /agent/chat
    response_model=AgentChatResponse,  # 指定响应模型为 AgentChatResponse
)  # 路由装饰器结束
def agent_chat(  # 定义 Agent 聊天接口处理函数
    request_data: AgentChatRequest,  # 接收请求体数据
    session: Session = Depends(get_session),  # 注入数据库会话，用来做权限校验
    current_user=Depends(get_current_user),  # 注入当前登录用户，用来做限流和权限校验
) -> AgentChatResponse:  # 返回 AgentChatResponse 响应对象
    message = request_data.message.strip()  # 去掉用户输入前后的空白字符

    if not message:  # 判断用户输入是否为空
        raise HTTPException(  # 抛出 HTTP 错误
            status_code=400,  # 400 表示请求参数不合法
            detail="消息内容不能为空",  # 返回错误提示
        )  # HTTPException 结束
    validate_prompt_security(  # 检查 Agent 聊天输入是否包含 Prompt Injection 内容
        message  # 传入用户原始输入
    )  # 提示词安全检查结束
    validate_agent_request_project_permission(  # 校验本次 Agent 请求是否有项目空间访问权限
        session=session,  # 传入数据库会话
        knowledge_base_id=request_data.knowledge_base_id,  # 传入请求里的知识库 ID
        chat_session_id=request_data.session_id,  # 传入请求里的会话 ID
        current_user=current_user,  # 传入当前登录用户
    )  # 权限校验结束

    check_rate_limit(  # 检查当前用户调用 Agent 接口是否过于频繁
        user_id=current_user.id,  # 使用当前登录用户 ID 做限流维度
        action="agent_task",  # Agent 接口使用 agent_task 限流规则
    )  # 限流检查结束，超过限制会直接返回 429
    task = create_agent_task(  # 创建一条 AgentTask 任务记录，用来作为本次 Agent 调用链的 trace
        user_input=message,  # 保存用户原始输入
        task_type="normal_chat",  # 初始任务类型先设置为普通聊天，后面 classify_task_node 可以覆盖
        session_id=request_data.session_id,  # 保存会话 ID，如果 create_agent_task 不支持这个参数，就删掉这一行
        knowledge_base_id=request_data.knowledge_base_id,  # 保存知识库 ID，如果 create_agent_task 不支持这个参数，就删掉这一行
    )  # AgentTask 创建结束

    input_state: AgentState = {  # 构造 Agent 初始状态
        "user_input": message,  # 用户输入
        "task_type": "normal_chat",  # 默认普通聊天
        "knowledge_base_id": request_data.knowledge_base_id,  # 知识库 ID
        "session_id": request_data.session_id,  # 会话 ID
        "top_k": request_data.top_k,  # 检索数量
        "context": "",  # 初始化上下文
        "citations": [],  # 初始化引用来源
        "answer": "",  # 初始化回答
        "task_id": task.id,  # 当前 AgentTask ID
        "step_id": None,  # 初始化步骤 ID
        "task_status": None,  # 初始化任务状态
        "steps": [],  # 初始化步骤列表
        "report_id": None,  # 初始化报告 ID
        "report_title": "",  # 初始化报告标题
        "report_content": "",  # 初始化报告正文
        "markdown_file_path": None,  # 初始化 Markdown 路径
        "error": None,  # 初始化错误
    }

    result = agent_graph.invoke(  # 执行 LangGraph 工作流
        input_state  # 把完整初始 State 传给 AgentGraph
    )  # LangGraph 执行结束，得到最终 State
    result_error = result.get("error")  # 从 Agent 执行结果中读取错误信息

    result_status = result.get("task_status") or (
        "failed" if result_error else "completed"
    )  # 从 Agent 执行结果中读取最终状态；没有显式状态时根据 error 判断

    result_answer = result.get("answer", "")  # 从 Agent 执行结果中读取回答内容

    if result_status == "failed":  # 判断任务最终状态是否失败
        update_agent_task_final_result(  # 把失败状态写回 agent_tasks 表
            task_id=task.id,  # 传入当前任务 ID
            status="failed",  # 更新任务状态为 failed
            current_step=result_answer or "Agent 执行失败",  # 把失败说明写入当前步骤
            error=result_error
            or result_answer
            or "Agent 执行失败",  # 把失败原因写入 error
            progress=100,  # 失败也表示流程已经结束
        )  # 更新失败任务结束

    elif result_status == "waiting_approval":  # 判断任务是否等待人工确认
        update_agent_task_final_result(  # 把等待确认状态写回 agent_tasks 表
            task_id=task.id,  # 传入当前任务 ID
            status="waiting_approval",  # 更新任务状态为 waiting_approval
            current_step="报告草稿已生成，等待人工确认",  # 更新当前步骤说明
            error=None,  # 清空错误
            progress=80,  # 设置进度为 80
        )  # 更新等待确认任务结束

    elif result_status == "completed":  # 判断任务是否已完成
        update_agent_task_final_result(  # 把完成状态写回 agent_tasks 表
            task_id=task.id,  # 传入当前任务 ID
            status="completed",  # 更新任务状态为 completed
            current_step="Agent 执行完成",  # 更新当前步骤说明
            error=None,  # 清空错误
            report_id=result.get("report_id"),  # 写入报告 ID
            markdown_file_path=result.get("markdown_file_path"),  # 写入 Markdown 路径
            progress=100,  # 设置进度为 100
        )  # 更新完成任务结束
    return AgentChatResponse(  # 返回符合 AgentChatResponse 响应模型的数据
        answer=result.get(  # 从最终 State 中读取回答
            "answer",  # 读取 answer 字段
            "",  # 如果没有 answer，就返回空字符串
        ),  # answer 字段设置结束
        task_type=result.get(  # 从最终 State 中读取任务类型
            "task_type",  # 读取 task_type 字段
            "unknown",  # 如果没有 task_type，就返回 unknown
        ),  # task_type 字段设置结束
        context=result.get(  # 从最终 State 中读取 RAG 上下文
            "context",  # 读取 context 字段
            "",  # 如果没有 context，就返回空字符串
        ),  # context 字段设置结束
        citations=result.get(  # 从最终 State 中读取引用来源
            "citations",  # 读取 citations 字段
            [],  # 如果没有 citations，就返回空列表
        ),  # citations 字段设置结束
        steps=result.get(  # 从最终 State 中读取执行步骤列表
            "steps",  # 读取 steps 字段
            [],  # 如果没有 steps，就返回空列表
        ),  # steps 字段设置结束
        saved_result_id=result.get(  # 从最终 State 中读取保存结果 ID
            "saved_result_id"  # 读取 saved_result_id 字段
        ),  # saved_result_id 字段设置结束
        task_id=result.get(  # 优先从最终 State 中读取 task_id
            "task_id",  # 读取 task_id 字段
            task.id,  # 如果最终 State 没有 task_id，就返回一开始创建的 AgentTask ID
        ),  # task_id 字段设置结束
        task_status=result_status,  # 返回接口层判断后的最终任务状态
        report_title=result.get(  # 从最终 State 中读取报告标题
            "report_title"  # 读取 report_title 字段
        ),  # report_title 字段设置结束
        report_content=result.get(  # 从最终 State 中读取报告正文
            "report_content"  # 读取 report_content 字段
        ),  # report_content 字段设置结束
        report_id=result.get(  # 从最终 State 中读取报告 ID
            "report_id"  # 读取 report_id 字段
        ),  # report_id 字段设置结束
        markdown_file_path=result.get(  # 从最终 State 中读取 Markdown 文件路径
            "markdown_file_path"  # 读取 markdown_file_path 字段
        ),  # markdown_file_path 字段设置结束
    )  # AgentChatResponse 构造结束


@router.post(  # 注册确认报告任务接口
    "/tasks/{task_id}/approve",  # 设置接口路径
    response_model=dict[str, Any],  # 使用字典作为响应模型
)  # 路由装饰器结束
def approve_report_task(  # 定义确认报告任务接口函数
    task_id: int,  # 接收路径参数 task_id
) -> dict[str, Any]:  # 返回字典结果
    result = approve_report_task_save_and_export(  # 调用确认并保存报告服务
        task_id=task_id  # 传入任务 ID
    )  # 服务调用结束

    if not result.get("success"):  # 判断服务是否执行失败
        raise HTTPException(  # 抛出 HTTP 异常
            status_code=400,  # 返回 400 状态码
            detail=result.get("error", "确认报告任务失败"),  # 返回错误详情
        )  # HTTP 异常结束

    return result  # 返回成功结果


@router.post(
    "/tasks/{task_id}/reject", response_model=AgentTaskActionResponse
)  # 注册用户拒绝 Agent 任务接口
def reject_task(task_id: int):  # 定义拒绝任务接口函数，task_id 来自路径参数
    steps: list[str] = []  # 创建本次接口执行步骤列表，用来返回给前端或 Swagger 查看

    task = get_agent_task(task_id)  # 根据任务 ID 查询 AgentTask 任务记录

    if task is None:  # 判断任务是否不存在
        return AgentTaskActionResponse(  # 返回任务不存在的响应
            success=False,  # success 为 False，表示操作失败
            task_id=None,  # 任务不存在，所以 task_id 返回 None
            task_status=None,  # 任务不存在，所以 task_status 返回 None
            answer="任务不存在。",  # 返回给用户看的提示
            steps=steps,  # 返回当前步骤列表
            error="任务不存在",  # 返回错误原因
        )  # 任务不存在响应结束

    if task.status != "waiting_approval":  # 判断任务当前状态是否不是等待确认
        return AgentTaskActionResponse(  # 返回状态不允许拒绝的响应
            success=False,  # success 为 False，表示操作失败
            task_id=task.id,  # 返回当前任务 ID
            task_status=task.status,  # 返回当前任务状态
            answer="当前任务状态不是 waiting_approval，不能执行拒绝操作。",  # 返回状态错误提示
            report_id=task.report_id,  # 返回任务已经关联的报告 ID，可能为空
            markdown_file_path=task.markdown_file_path,  # 返回任务已经关联的 Markdown 文件路径，可能为空
            steps=steps,  # 返回当前步骤列表
            error="任务状态不允许拒绝",  # 返回错误原因
        )  # 状态不允许拒绝响应结束

    steps.append("用户拒绝任务")  # 记录步骤：用户已经拒绝任务

    answer = "用户已拒绝执行报告生成任务。"  # 定义返回给用户看的拒绝提示

    updated_task = update_agent_task_status(  # 更新任务状态
        task_id=task.id,  # 传入任务 ID
        status="rejected",  # 把任务状态改成 rejected，表示用户已拒绝
        answer=answer,  # 保存拒绝提示到任务 answer 字段
    )  # rejected 状态更新结束

    create_agent_step(  # 创建任务步骤记录
        task_id=task.id,  # 关联当前任务 ID
        step_name="reject_task",  # 设置步骤名称为用户拒绝任务
        step_type="approval",  # 设置步骤类型为人工确认
        status="success",  # 设置步骤状态为成功
        input_data={  # 保存步骤输入数据
            "task_id": task.id,  # 保存任务 ID
            "old_status": task.status,  # 保存拒绝前的任务状态
        },  # 输入数据结束
        output_data={  # 保存步骤输出数据
            "task_status": "rejected",  # 保存拒绝后的任务状态
            "message": answer,  # 保存拒绝提示
        },  # 输出数据结束
    )  # reject_task 步骤记录创建结束

    steps.append("任务状态更新为 rejected")  # 记录步骤：任务状态已经改成 rejected

    return AgentTaskActionResponse(  # 返回拒绝任务成功的响应
        success=True,  # success 为 True，表示拒绝操作成功
        task_id=task.id,  # 返回任务 ID
        task_status=(
            updated_task.status if updated_task else "rejected"
        ),  # 返回最新任务状态
        answer=answer,  # 返回拒绝提示
        report_id=None,  # 用户拒绝后不会生成报告，所以 report_id 为 None
        markdown_file_path=None,  # 用户拒绝后不会导出 Markdown，所以文件路径为 None
        steps=steps,  # 返回本次接口执行步骤
        error=None,  # 成功时错误信息为空
    )  # 拒绝任务成功响应结束


@router.get(
    "/tasks/failed", response_model=list[AgentTaskSummaryResponse]
)  # 注册查询失败 Agent 任务列表接口
def list_failed_tasks(
    limit: int = 20,
):  # 定义查询失败任务接口，limit 控制最多返回多少条
    tasks = list_failed_agent_tasks(
        limit=limit
    )  # 调用服务函数，查询 failed 状态的任务列表

    return [  # 返回任务摘要列表
        AgentTaskSummaryResponse(  # 把每个 AgentTask 数据库对象转换成响应模型
            id=task.id or 0,  # 返回任务 ID，如果为空就返回 0
            task_type=task.task_type,  # 返回任务类型
            status=task.status,  # 返回任务状态
            user_input=task.user_input,  # 返回用户原始输入
            retry_count=task.retry_count,  # 返回已经重试次数
            max_retries=task.max_retries,  # 返回最大重试次数
            error=task.error,  # 返回失败原因
            failed_at=task.failed_at,  # 返回失败时间
            last_retry_at=task.last_retry_at,  # 返回最后一次重试时间
            created_at=task.created_at,  # 返回任务创建时间
        )  # 单条任务响应模型构造结束
        for task in tasks  # 遍历所有失败任务
    ]  # 失败任务列表返回结束


@router.post(
    "/tasks/{task_id}/retry", response_model=AgentTaskActionResponse
)  # 注册重试失败 Agent 任务接口
def retry_task(task_id: int):  # 定义重试任务接口函数，task_id 来自路径参数
    steps: list[str] = []  # 创建本次接口执行步骤列表，用来返回给前端或 Swagger 查看

    task = get_agent_task(task_id)  # 根据任务 ID 查询 AgentTask 任务记录

    if task is None:  # 判断任务是否不存在
        return AgentTaskActionResponse(  # 返回任务不存在响应
            success=False,  # success 为 False，表示操作失败
            task_id=None,  # 任务不存在，所以 task_id 返回 None
            task_status=None,  # 任务不存在，所以 task_status 返回 None
            answer="任务不存在。",  # 返回给用户看的提示
            steps=steps,  # 返回当前步骤列表
            error="任务不存在",  # 返回错误原因
        )  # 任务不存在响应结束

    if not can_retry_agent_task(task):  # 判断任务是否不允许重试
        steps.append(
            f"当前任务状态为 {task.status}，重试次数为 {task.retry_count}/{task.max_retries}，不能执行重试"
        )  # 记录不能重试的原因

        return AgentTaskActionResponse(  # 返回不能重试响应
            success=False,  # success 为 False，表示操作失败
            task_id=task.id,  # 返回当前任务 ID
            task_status=task.status,  # 返回当前任务状态
            answer="当前任务不允许重试，只有 failed 状态且未超过最大重试次数的任务才能重试。",  # 返回不能重试提示
            report_id=task.report_id,  # 返回任务已有报告 ID，可能为空
            markdown_file_path=task.markdown_file_path,  # 返回任务已有 Markdown 路径，可能为空
            steps=steps,  # 返回步骤列表
            error="任务不允许重试",  # 返回错误原因
        )  # 不能重试响应结束

    updated_retry_task = increase_agent_task_retry_count(
        task.id
    )  # 增加任务重试次数，并记录最后一次重试时间

    if updated_retry_task is None:  # 判断增加重试次数后任务是否不存在
        return AgentTaskActionResponse(  # 返回任务不存在响应
            success=False,  # success 为 False，表示操作失败
            task_id=None,  # 任务不存在，所以 task_id 返回 None
            task_status=None,  # 任务不存在，所以 task_status 返回 None
            answer="任务不存在。",  # 返回给用户看的提示
            steps=steps,  # 返回当前步骤列表
            error="任务不存在",  # 返回错误原因
        )  # 任务不存在响应结束

    retry_count = updated_retry_task.retry_count  # 取出更新后的重试次数

    steps.append(f"开始第 {retry_count} 次重试任务")  # 记录步骤：开始重试任务

    update_agent_task_status(  # 更新任务状态
        task_id=task.id,  # 传入任务 ID
        status="running",  # 把任务状态改成 running，表示正在重试执行
        error=None,  # 清空旧错误信息
    )  # running 状态更新结束

    create_agent_step(  # 创建重试任务步骤记录
        task_id=task.id,  # 关联当前任务 ID
        step_name="retry_task",  # 设置步骤名称为重试任务
        step_type="system",  # 设置步骤类型为系统流程
        status="running",  # 设置步骤状态为运行中
        input_data={  # 保存步骤输入数据
            "task_id": task.id,  # 保存任务 ID
            "old_status": task.status,  # 保存重试前任务状态
            "retry_count": retry_count,  # 保存当前是第几次重试
        },  # 输入数据结束
        output_data={  # 保存步骤输出数据
            "message": "任务开始重试。",  # 保存步骤说明
        },  # 输出数据结束
        retry_count=retry_count,  # 保存当前步骤属于第几次重试
        is_retry=True,  # 标记当前步骤来自重试流程
    )  # retry_task 步骤记录创建结束

    try:  # 尝试重新执行任务，防止中途报错导致接口崩掉
        if task.task_type != "report":  # 判断当前任务类型是否不是 report
            error_message = (
                "当前基础版 retry 只支持 report 类型任务。"  # 定义不支持重试的错误信息
            )

            update_agent_task_status(  # 更新任务状态为 failed
                task_id=task.id,  # 传入任务 ID
                status="failed",  # 设置任务状态为 failed
                answer=error_message,  # 保存失败提示
                error=error_message,  # 保存失败原因
            )  # failed 状态更新结束

            create_agent_step(  # 创建不支持任务类型的失败步骤记录
                task_id=task.id,  # 关联当前任务 ID
                step_name="retry_task_type_not_supported",  # 设置步骤名称为任务类型不支持重试
                step_type="system",  # 设置步骤类型为系统流程
                status="failed",  # 设置步骤状态为失败
                input_data={  # 保存步骤输入数据
                    "task_type": task.task_type,  # 保存任务类型
                },  # 输入数据结束
                output_data={},  # 没有正常输出，所以保存空字典
                error=error_message,  # 保存错误信息
                retry_count=retry_count,  # 保存当前重试次数
                is_retry=True,  # 标记这是重试流程产生的步骤
            )  # 不支持任务类型步骤记录创建结束

            return AgentTaskActionResponse(  # 返回重试失败响应
                success=False,  # success 为 False，表示重试失败
                task_id=task.id,  # 返回任务 ID
                task_status="failed",  # 返回任务状态
                answer=error_message,  # 返回失败提示
                steps=steps,  # 返回步骤列表
                error=error_message,  # 返回错误原因
            )  # 重试失败响应结束

        report_state = {  # 构造 generate_report_node 需要的 AgentState 数据
            "user_input": task.user_input,  # 放入用户原始输入
            "task_type": task.task_type,  # 放入任务类型
            "knowledge_base_id": task.knowledge_base_id,  # 放入知识库 ID
            "session_id": task.session_id,  # 放入会话 ID
            "context": task.context,  # 放入之前保存的知识库上下文
            "citations": task.citations,  # 放入之前保存的引用来源列表
            "steps": steps,  # 放入当前步骤列表，让报告节点继续追加步骤
        }  # AgentState 构造结束

        result = generate_report_node(
            report_state
        )  # 复用报告生成节点，重新生成报告、保存报告、导出 Markdown

        if result.get("error"):  # 判断报告生成节点是否返回错误
            error_message = result.get(
                "error", "任务重试失败"
            )  # 获取错误信息，如果没有就使用默认错误

            update_agent_task_status(  # 更新任务状态为 failed
                task_id=task.id,  # 传入任务 ID
                status="failed",  # 设置任务状态为 failed
                answer="任务重试失败。",  # 保存失败回答
                error=error_message,  # 保存错误信息
            )  # failed 状态更新结束

            create_agent_step(  # 创建重试失败步骤记录
                task_id=task.id,  # 关联当前任务 ID
                step_name="retry_failed",  # 设置步骤名称为重试失败
                step_type="system",  # 设置步骤类型为系统流程
                status="failed",  # 设置步骤状态为失败
                input_data=report_state,  # 保存重试输入数据
                output_data=result,  # 保存重试输出数据
                error=error_message,  # 保存错误信息
                retry_count=retry_count,  # 保存当前重试次数
                is_retry=True,  # 标记这是重试流程产生的步骤
            )  # 重试失败步骤记录创建结束

            return AgentTaskActionResponse(  # 返回重试失败响应
                success=False,  # success 为 False，表示重试失败
                task_id=task.id,  # 返回任务 ID
                task_status="failed",  # 返回任务状态
                answer="任务重试失败。",  # 返回失败提示
                steps=result.get("steps", steps),  # 返回执行步骤
                error=error_message,  # 返回错误原因
            )  # 重试失败响应结束

        final_answer = result.get("answer", "")  # 获取最终报告正文
        report_id = result.get("report_id")  # 获取报告 ID
        markdown_file_path = result.get("markdown_file_path")  # 获取 Markdown 文件路径
        final_steps = result.get("steps", steps)  # 获取完整步骤列表

        update_agent_task_status(  # 更新任务状态为 success
            task_id=task.id,  # 传入任务 ID
            status="success",  # 设置任务状态为 success
            answer=final_answer,  # 保存最终报告正文
            report_id=report_id,  # 保存报告 ID
            markdown_file_path=markdown_file_path,  # 保存 Markdown 文件路径
        )  # success 状态更新结束

        create_agent_step(  # 创建重试成功步骤记录
            task_id=task.id,  # 关联当前任务 ID
            step_name="retry_success",  # 设置步骤名称为重试成功
            step_type="system",  # 设置步骤类型为系统流程
            status="success",  # 设置步骤状态为成功
            input_data={  # 保存步骤输入数据
                "task_id": task.id,  # 保存任务 ID
                "retry_count": retry_count,  # 保存当前重试次数
            },  # 输入数据结束
            output_data={  # 保存步骤输出数据
                "report_id": report_id,  # 保存报告 ID
                "markdown_file_path": markdown_file_path,  # 保存 Markdown 文件路径
                "task_status": "success",  # 保存最终任务状态
            },  # 输出数据结束
            retry_count=retry_count,  # 保存当前重试次数
            is_retry=True,  # 标记这是重试流程产生的步骤
        )  # 重试成功步骤记录创建结束

        return AgentTaskActionResponse(  # 返回重试成功响应
            success=True,  # success 为 True，表示重试成功
            task_id=task.id,  # 返回任务 ID
            task_status="success",  # 返回最终任务状态
            answer=final_answer,  # 返回生成出来的报告正文
            report_id=report_id,  # 返回报告 ID
            markdown_file_path=markdown_file_path,  # 返回 Markdown 文件路径
            steps=final_steps,  # 返回完整步骤
            error=None,  # 成功时错误信息为空
        )  # 重试成功响应结束

    except Exception as exc:  # 捕获重试过程中的异常
        error_message = str(exc)  # 把异常对象转成字符串错误信息

        update_agent_task_status(  # 更新任务状态为 failed
            task_id=task.id,  # 传入任务 ID
            status="failed",  # 设置任务状态为 failed
            answer="任务重试失败。",  # 保存失败回答
            error=error_message,  # 保存异常错误信息
        )  # failed 状态更新结束

        create_agent_step(  # 创建重试异常步骤记录
            task_id=task.id,  # 关联当前任务 ID
            step_name="retry_error",  # 设置步骤名称为重试异常
            step_type="system",  # 设置步骤类型为系统流程
            status="failed",  # 设置步骤状态为失败
            input_data={  # 保存步骤输入数据
                "task_id": task.id,  # 保存任务 ID
                "retry_count": retry_count,  # 保存当前重试次数
            },  # 输入数据结束
            output_data={},  # 异常时没有正常输出，所以保存空字典
            error=error_message,  # 保存异常错误信息
            retry_count=retry_count,  # 保存当前重试次数
            is_retry=True,  # 标记这是重试流程产生的步骤
        )  # 重试异常步骤记录创建结束

        return AgentTaskActionResponse(  # 返回重试异常失败响应
            success=False,  # success 为 False，表示重试失败
            task_id=task.id,  # 返回任务 ID
            task_status="failed",  # 返回任务状态
            answer="任务重试失败。",  # 返回失败提示
            steps=steps,  # 返回已经执行过的步骤
            error=error_message,  # 返回异常错误信息
        )  # 重试异常失败响应结束


@router.post(
    "/tasks", response_model=AgentTaskCreateResponse
)  # 注册创建后台 Agent 任务接口
def create_background_agent_task(  # 定义创建后台任务接口函数，接收请求体数据
    request_data: AgentTaskCreateRequest,  # 后台 Agent 任务创建请求体
    session: Session = Depends(
        get_session
    ),  # 注入数据库会话，用来做知识库和会话权限校验
    current_user=Depends(get_current_user),  # 注入当前登录用户，用来做限流和权限判断
):  # 函数参数定义结束
    if request_data.task_type != "report":  # 判断当前任务类型是否不是 report
        return AgentTaskCreateResponse(  # 返回任务类型不支持的响应
            success=False,  # success 为 False，表示任务创建失败
            task_id=None,  # 创建失败时没有任务 ID
            task_status="failed",  # 返回失败状态
            job_id=None,  # 没有入队，所以没有 RQ Job ID
            message="当前后台任务暂时只支持 report 类型。",  # 返回给用户看的提示信息
            error="任务类型不支持",  # 返回错误原因
        )  # 任务类型不支持响应结束

    message = request_data.message.strip()  # 去掉任务内容前后的空白字符

    if not message:  # 判断清理后的任务内容是否为空
        return AgentTaskCreateResponse(  # 返回任务内容为空的响应
            success=False,  # success 为 False，表示任务创建失败
            task_id=None,  # 创建失败时没有任务 ID
            task_status="failed",  # 返回失败状态
            job_id=None,  # 没有入队，所以没有 RQ Job ID
            message="任务内容不能为空。",  # 返回给用户看的提示信息
            error="message 不能为空",  # 返回错误原因
        )  # 用户输入为空响应结束

    validate_prompt_security(  # 检查后台 Agent 任务输入是否包含 Prompt Injection 内容
        message  # 传入用户原始任务内容
    )  # 提示词安全检查结束

    if not message:  # 判断清理空白后的任务内容是否为空
        return AgentTaskCreateResponse(  # 返回任务内容为空的响应
            success=False,  # success 为 False，表示任务创建失败
            task_id=None,  # 创建失败时没有任务 ID
            task_status="failed",  # 返回失败状态
            job_id=None,  # 没有入队，所以没有 RQ Job ID
            message="任务内容不能为空。",  # 返回给用户看的提示信息
            error="message 不能为空",  # 返回错误原因
        )  # 用户输入为空响应结束

    validate_agent_request_project_permission(  # 校验本次 Agent 后台任务是否有项目空间访问权限
        session=session,  # 传入数据库会话
        knowledge_base_id=request_data.knowledge_base_id,  # 传入请求里的知识库 ID
        chat_session_id=request_data.session_id,  # 传入请求里的会话 ID
        current_user=current_user,  # 传入当前登录用户
    )  # 权限校验结束

    check_rate_limit(  # 检查当前用户创建 Agent 后台任务是否过于频繁
        user_id=current_user.id,  # 使用当前登录用户 ID 做限流维度
        action="agent_task",  # Agent 后台任务使用 agent_task 限流规则
    )  # 限流检查结束，超过限制会直接返回 429
    task = create_agent_task(  # 创建 AgentTask 数据库任务记录
        task_type=request_data.task_type,  # 保存任务类型，目前主要是 report
        user_input=message,  # 把接口里的 message 保存到数据库的 user_input 字段
        status="created",  # 初始状态设置为 created，表示任务刚创建
        knowledge_base_id=request_data.knowledge_base_id,  # 保存知识库 ID
        session_id=request_data.session_id,  # 保存会话 ID
        context="",  # 后台 Worker 执行检索后再保存 context
        citations=[],  # 后台 Worker 执行检索后再保存 citations
    )  # AgentTask 创建结束

    update_agent_task_progress(  # 更新任务为 queued 状态
        task_id=task.id,  # 传入任务 ID
        status="queued",  # 把任务状态改成 queued，表示已经准备加入队列
        progress=0,  # 初始进度为 0
        current_step="已加入队列，等待执行",  # 设置当前步骤说明
    )  # queued 状态更新结束

    create_agent_step(  # 创建任务入队步骤记录
        task_id=task.id,  # 关联当前 AgentTask ID
        step_name="queue_task",  # 设置步骤名称为任务入队
        step_type="queue",  # 设置步骤类型为队列
        status="success",  # 设置步骤状态为成功
        input_data={  # 保存步骤输入数据
            "task_type": request_data.task_type,  # 保存任务类型
            "message": message,  # 保存用户输入
            "knowledge_base_id": request_data.knowledge_base_id,  # 保存知识库 ID
            "session_id": request_data.session_id,  # 保存会话 ID
        },  # 输入数据结束
        output_data={  # 保存步骤输出数据
            "task_id": task.id,  # 保存创建出来的任务 ID
            "task_status": "queued",  # 保存当前任务状态
            "message": "任务已创建，准备加入 RQ 队列。",  # 保存步骤说明
        },  # 输出数据结束
    )  # 任务入队步骤记录创建结束

    try:  # 尝试把任务放入 RQ 队列，防止 Redis 或 RQ 出错导致接口崩掉
        job = agent_task_queue.enqueue(  # 把后台任务函数放入 RQ 队列
            run_agent_task,  # 传入 Worker 要执行的函数
            task.id,  # 传入函数参数，相当于后面执行 run_agent_task(task.id)
            job_timeout="10m",  # 设置任务最长执行时间为 10 分钟，避免任务无限卡住
        )  # RQ 入队结束

        update_agent_task_job_id(  # 把 RQ Job ID 保存回 AgentTask
            task_id=task.id,  # 传入任务 ID
            job_id=job.id,  # 保存 RQ 自动生成的 Job ID
        )  # Job ID 保存结束

        create_agent_step(  # 创建 RQ 入队成功步骤记录
            task_id=task.id,  # 关联当前 AgentTask ID
            step_name="rq_enqueue_success",  # 设置步骤名称为 RQ 入队成功
            step_type="queue",  # 设置步骤类型为队列
            status="success",  # 设置步骤状态为成功
            input_data={  # 保存步骤输入数据
                "task_id": task.id,  # 保存任务 ID
            },  # 输入数据结束
            output_data={  # 保存步骤输出数据
                "job_id": job.id,  # 保存 RQ Job ID
                "job_status": str(job.get_status()),  # 保存 RQ Job 当前状态
            },  # 输出数据结束
        )  # RQ 入队成功步骤记录创建结束

        return AgentTaskCreateResponse(  # 返回后台任务创建成功响应
            success=True,  # success 为 True，表示任务创建并入队成功
            task_id=task.id,  # 返回 AgentTask ID
            task_status="queued",  # 返回当前任务状态
            job_id=job.id,  # 返回 RQ Job ID
            message="任务已创建，正在排队执行。",  # 返回提示信息
            error=None,  # 成功时错误信息为空
        )  # 创建成功响应结束

    except Exception as exc:  # 捕获 RQ 入队过程中的异常
        error_message = str(exc)  # 把异常对象转成字符串错误信息

        update_agent_task_progress(  # 更新任务为 failed 状态
            task_id=task.id,  # 传入任务 ID
            status="failed",  # 把任务状态改成 failed
            progress=0,  # 入队失败时进度仍然是 0
            current_step="任务加入队列失败",  # 更新当前步骤说明
            error=error_message,  # 保存失败原因
        )  # 入队失败状态更新结束

        create_agent_step(  # 创建 RQ 入队失败步骤记录
            task_id=task.id,  # 关联当前 AgentTask ID
            step_name="rq_enqueue_failed",  # 设置步骤名称为 RQ 入队失败
            step_type="queue",  # 设置步骤类型为队列
            status="failed",  # 设置步骤状态为失败
            input_data={  # 保存步骤输入数据
                "task_id": task.id,  # 保存任务 ID
            },  # 输入数据结束
            output_data={},  # 入队失败时没有正常输出，所以保存空字典
            error=error_message,  # 保存错误信息
        )  # RQ 入队失败步骤记录创建结束

        return AgentTaskCreateResponse(  # 返回后台任务创建失败响应
            success=False,  # success 为 False，表示任务创建失败
            task_id=task.id,  # 返回已经创建出来的任务 ID
            task_status="failed",  # 返回任务状态 failed
            job_id=None,  # 入队失败时没有 Job ID
            message="任务创建失败：加入队列失败。",  # 返回给用户看的提示信息
            error=error_message,  # 返回错误原因
        )  # 创建失败响应结束


@router.get(
    "/tasks/{task_id}", response_model=AgentTaskDetailResponse
)  # 注册查询 Agent 后台任务详情接口
def get_agent_task_detail(task_id: int):  # 定义查询任务详情函数，接收路径参数 task_id
    task = get_agent_task(task_id)  # 根据任务 ID 查询 AgentTask 数据库记录

    if task is None:  # 判断任务是否不存在
        return AgentTaskDetailResponse(  # 返回任务不存在的响应体
            success=False,  # success 为 False，表示查询失败
            task_id=None,  # 任务不存在，所以 task_id 返回 None
            task_type=None,  # 任务不存在，所以任务类型返回 None
            task_status=None,  # 任务不存在，所以任务状态返回 None
            progress=0,  # 任务不存在，进度返回 0
            current_step="",  # 任务不存在，当前步骤返回空字符串
            user_input="",  # 任务不存在，用户输入返回空字符串
            answer="",  # 任务不存在，答案返回空字符串
            report_id=None,  # 任务不存在，报告 ID 返回 None
            markdown_file_path=None,  # 任务不存在，Markdown 文件路径返回 None
            job_id=None,  # 任务不存在，RQ Job ID 返回 None
            error="任务不存在",  # 返回错误原因
            queued_at=None,  # 任务不存在，入队时间返回 None
            started_at=None,  # 任务不存在，开始时间返回 None
            finished_at=None,  # 任务不存在，结束时间返回 None
            created_at=None,  # 任务不存在，创建时间返回 None
            updated_at=None,  # 任务不存在，更新时间返回 None
            message="任务不存在。",  # 返回给用户看的提示信息
        )  # 任务不存在响应体创建结束

    return build_agent_task_detail_response(
        task
    )  # 如果任务存在，就把 AgentTask 转成任务详情响应体并返回


@router.get(
    "/tasks/{task_id}/events", response_model=AgentTaskEventsResponse
)  # 注册查询 Agent 任务步骤事件接口
def get_agent_task_events(
    task_id: int,
):  # 定义查询任务事件接口函数，接收路径参数 task_id
    task = get_agent_task(task_id)  # 根据任务 ID 查询 AgentTask 主任务记录

    if task is None:  # 判断任务是否不存在
        return AgentTaskEventsResponse(  # 返回任务不存在的事件响应体
            success=False,  # success 为 False，表示查询失败
            task_id=None,  # 任务不存在，所以 task_id 返回 None
            task_status=None,  # 任务不存在，所以任务状态返回 None
            total=0,  # 任务不存在，所以事件数量为 0
            events=[],  # 任务不存在，所以事件列表为空
            message="任务不存在。",  # 返回给用户看的提示信息
            error="任务不存在",  # 返回错误原因
        )  # 任务不存在响应体创建结束

    steps = list_agent_steps(
        task_id
    )  # 根据任务 ID 查询该任务下的所有 AgentStep 步骤记录

    events = build_agent_task_event_items(
        steps
    )  # 把 AgentStep 数据库对象列表转换成接口事件对象列表

    return AgentTaskEventsResponse(  # 返回任务事件列表响应体
        success=True,  # success 为 True，表示查询成功
        task_id=task.id,  # 返回当前任务 ID
        task_status=task.status,  # 返回当前任务状态，例如 queued、running、success、failed
        total=len(events),  # 返回事件总数，也就是步骤数量
        events=events,  # 返回转换后的任务事件列表
        message="任务事件查询成功。",  # 返回给用户看的提示信息
        error=None,  # 查询成功时错误信息为空
    )  # 任务事件列表响应体创建结束


@router.post(
    "/tasks/{task_id}/cancel", response_model=AgentTaskCancelResponse
)  # 注册取消 Agent 后台任务接口
def cancel_background_agent_task(
    task_id: int,
):  # 定义取消后台任务接口函数，接收路径参数 task_id
    result = cancel_agent_task(task_id)  # 调用 Service 层函数，执行取消任务逻辑

    task = result.get("task")  # 从取消结果里取出任务对象，任务不存在时可能是 None

    if task is None:  # 判断任务是否不存在
        return AgentTaskCancelResponse(  # 返回任务不存在的响应体
            success=False,  # success 为 False，表示取消失败
            task_id=None,  # 任务不存在，所以任务 ID 返回 None
            task_status=None,  # 任务不存在，所以任务状态返回 None
            message=result.get("message", "任务不存在。"),  # 返回提示信息
            error=result.get("error", "任务不存在"),  # 返回错误原因
        )  # 任务不存在响应体创建结束

    if result.get("success"):  # 判断任务是否取消成功
        create_agent_step(  # 创建取消任务步骤记录
            task_id=task.id,  # 关联当前任务 ID
            step_name="cancel_task",  # 设置步骤名称为取消任务
            step_type="user_action",  # 设置步骤类型为用户操作
            status="success",  # 设置步骤状态为成功
            input_data={  # 保存步骤输入数据
                "task_id": task.id,  # 保存任务 ID
                "before_status": "cancellable",  # 表示取消前任务属于可取消状态
            },  # 输入数据结束
            output_data={  # 保存步骤输出数据
                "task_status": task.status,  # 保存取消后的任务状态
                "message": result.get("message", "任务已取消。"),  # 保存取消提示
            },  # 输出数据结束
            error=None,  # 取消成功时错误信息为空
        )  # 取消任务步骤记录创建结束

        return AgentTaskCancelResponse(  # 返回取消成功响应体
            success=True,  # success 为 True，表示取消成功
            task_id=task.id,  # 返回任务 ID
            task_status=task.status,  # 返回任务当前状态，正常是 cancelled
            message=result.get("message", "任务已取消。"),  # 返回提示信息
            error=None,  # 取消成功时错误信息为空
        )  # 取消成功响应体创建结束

    create_agent_step(  # 创建取消任务失败步骤记录
        task_id=task.id,  # 关联当前任务 ID
        step_name="cancel_task_failed",  # 设置步骤名称为取消任务失败
        step_type="user_action",  # 设置步骤类型为用户操作
        status="failed",  # 设置步骤状态为失败
        input_data={  # 保存步骤输入数据
            "task_id": task.id,  # 保存任务 ID
            "task_status": task.status,  # 保存任务当前状态
        },  # 输入数据结束
        output_data={  # 保存步骤输出数据
            "message": result.get("message", "任务取消失败。"),  # 保存失败提示
        },  # 输出数据结束
        error=result.get("error"),  # 保存取消失败原因
    )  # 取消任务失败步骤记录创建结束

    return AgentTaskCancelResponse(  # 返回取消失败响应体
        success=False,  # success 为 False，表示取消失败
        task_id=task.id,  # 返回任务 ID
        task_status=task.status,  # 返回任务当前状态
        message=result.get("message", "任务取消失败。"),  # 返回提示信息
        error=result.get("error"),  # 返回错误原因
    )  # 取消失败响应体创建结束


@router.get(  # 注册查询 Agent 任务完整调用链接口
    "/tasks/{task_id}/trace",  # 设置接口路径，最终访问路径通常是 /agent/tasks/{task_id}/trace
    response_model=dict[str, Any],  # 设置响应模型为字典，因为 trace 结构较复杂
)  # 接口装饰器结束
def get_agent_task_trace(  # 定义查询 Agent 任务调用链的接口函数
    task_id: int,  # 接收路径参数 task_id，表示要查询哪个 AgentTask 的调用链
) -> dict[str, Any]:  # 返回完整调用链字典
    trace_result = build_agent_task_trace(  # 调用服务层函数，组装完整任务调用链
        task_id=task_id  # 传入用户要查询的任务 ID
    )  # 调用链组装结束

    return trace_result  # 返回调用链结果给前端或 Swagger


@router.post(  # 注册创建 bad case 的接口
    "/tasks/{task_id}/bad-cases",  # 设置接口路径，最终通常是 /agent/tasks/{task_id}/bad-cases
    response_model=dict[str, Any],  # 设置响应模型为字典，方便先快速返回 bad case 结果
)  # 接口装饰器结束
def mark_agent_task_as_bad_case(  # 定义把某个 AgentTask 标记为 bad case 的接口函数
    task_id: int,  # 接收路径参数 task_id，表示要标记哪个 AgentTask
    request_data: BadCaseCreateRequest,  # 接收请求体数据，里面包含 reason、category、expected_answer 等
) -> dict[str, Any]:  # 返回创建结果字典
    bad_case = create_bad_case(  # 调用服务层函数创建 bad case
        task_id=task_id,  # 传入任务 ID
        reason=request_data.reason,  # 传入 bad case 原因
        expected_answer=request_data.expected_answer,  # 传入期望答案
        category=request_data.category,  # 传入 bad case 分类
        severity=request_data.severity,  # 传入严重程度
        feedback_source=request_data.feedback_source,  # 传入反馈来源
        prompt_name=request_data.prompt_name,  # 传入 prompt 名称，可以为空
        prompt_version=request_data.prompt_version,  # 传入 prompt 版本，可以为空
    )  # bad case 创建结束

    if bad_case is None:  # 判断 bad case 是否创建失败，通常是 task_id 不存在
        raise HTTPException(  # 抛出 FastAPI HTTP 异常
            status_code=404,  # 设置状态码为 404
            detail="Agent 任务不存在，无法创建 bad case",  # 设置错误提示
        )  # HTTP 异常抛出结束

    return {  # 返回创建成功结果
        "success": True,  # 标记创建成功
        "message": "bad case 创建成功",  # 返回提示信息
        "bad_case": {  # 返回 bad case 基本信息
            "id": bad_case.id,  # 返回 bad case ID
            "task_id": bad_case.task_id,  # 返回关联的任务 ID
            "task_type": bad_case.task_type,  # 返回任务类型
            "user_input": bad_case.user_input,  # 返回用户原问题
            "answer": bad_case.answer,  # 返回 AI 当时的回答
            "expected_answer": bad_case.expected_answer,  # 返回期望答案
            "reason": bad_case.reason,  # 返回 bad case 原因
            "category": bad_case.category,  # 返回 bad case 分类
            "severity": bad_case.severity,  # 返回严重程度
            "status": bad_case.status,  # 返回处理状态
            "feedback_source": bad_case.feedback_source,  # 返回反馈来源
            "prompt_name": bad_case.prompt_name,  # 返回 prompt 名称
            "prompt_version": bad_case.prompt_version,  # 返回 prompt 版本
            "trace_snapshot": bad_case.trace_snapshot,  # 返回调用链快照
            "created_at": (
                bad_case.created_at.isoformat() if bad_case.created_at else None
            ),  # 返回创建时间字符串
        },  # bad case 基本信息结束
    }  # 创建成功结果返回结束
