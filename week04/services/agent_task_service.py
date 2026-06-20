from datetime import (
    datetime,
)  # 导入 datetime，用来记录任务更新时间、步骤开始时间和结束时间

from typing import Any  # 导入 Any，用来表示 JSON 字段里可以保存任意类型的数据

from sqlmodel import (
    Session,
    select,
)  # 导入 Session 用来操作数据库，导入 select 用来查询数据

from database import engine  # 从 database.py 导入数据库 engine，用来创建数据库连接

from models import (
    AgentStep,
    AgentTask,
)  # 从 models.py 导入 AgentTask 和 AgentStep 数据模型


def create_agent_task(  # 定义创建 Agent 任务的服务函数
    task_type: str,  # 接收任务类型，例如 report、rag_chat、normal_chat
    user_input: str,  # 接收用户原始输入
    status: str = "created",  # 接收任务状态，默认是 created
    knowledge_base_id: int | None = None,  # 接收知识库 ID，可以为空
    session_id: int | None = None,  # 接收会话 ID，可以为空
    context: str = "",  # 接收知识库检索上下文，默认空字符串
    citations: list[dict[str, Any]] | None = None,  # 接收引用来源列表，可以为空
) -> AgentTask:  # 返回创建好的 AgentTask 对象
    citations = (
        citations or []
    )  # 如果 citations 是 None，就改成空列表，避免 JSON 字段保存 None

    task = AgentTask(  # 创建 AgentTask 数据库对象
        task_type=task_type,  # 保存任务类型
        status=status,  # 保存任务状态
        user_input=user_input,  # 保存用户原始输入
        knowledge_base_id=knowledge_base_id,  # 保存知识库 ID
        session_id=session_id,  # 保存会话 ID
        context=context,  # 保存检索上下文
        citations=citations,  # 保存引用来源列表
    )  # AgentTask 对象创建结束

    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        session.add(task)  # 把任务对象加入数据库会话
        session.commit()  # 提交数据库事务，把任务真正写入 agent_tasks 表
        session.refresh(task)  # 刷新任务对象，拿到数据库自动生成的 id
        return task  # 返回创建好的任务对象


def get_agent_task(
    task_id: int,
) -> AgentTask | None:  # 定义根据任务 ID 查询任务的服务函数
    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        task = session.get(AgentTask, task_id)  # 根据主键 ID 查询 AgentTask 记录
        return task  # 返回查询到的任务，如果不存在则返回 None


def update_agent_task_status(  # 定义更新 Agent 任务状态的服务函数
    task_id: int,  # 接收任务 ID
    status: str,  # 接收新的任务状态
    answer: str | None = None,  # 接收最终回答，可以为空
    report_id: int | None = None,  # 接收报告 ID，可以为空
    markdown_file_path: str | None = None,  # 接收 Markdown 文件路径，可以为空
    error: str | None = None,  # 接收错误信息，可以为空
) -> AgentTask | None:  # 返回更新后的任务对象，如果任务不存在则返回 None
    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        task = session.get(AgentTask, task_id)  # 根据任务 ID 查询 AgentTask 记录

        if task is None:  # 判断任务是否不存在
            return None  # 如果任务不存在，直接返回 None

        task.status = status  # 更新任务状态
        task.updated_at = datetime.now()  # 更新任务更新时间
        if status in ["running", "success", "completed"]:  # 如果任务进入运行中或完成状态
            task.error = None  # 清空旧错误信息
        if status == "failed":  # 判断任务是否进入失败状态
            task.failed_at = datetime.now()  # 如果任务失败，就记录失败时间

        if answer is not None:  # 判断是否传入了最终回答
            task.answer = answer  # 如果传入了，就更新任务回答

        if report_id is not None:  # 判断是否传入了报告 ID
            task.report_id = report_id  # 如果传入了，就更新任务关联的报告 ID

        if markdown_file_path is not None:  # 判断是否传入了 Markdown 文件路径
            task.markdown_file_path = (
                markdown_file_path  # 如果传入了，就更新 Markdown 文件路径
            )

        if error is not None:  # 判断是否传入了错误信息
            task.error = error  # 如果传入了，就更新错误信息

        session.add(task)  # 把修改后的任务对象加入数据库会话
        session.commit()  # 提交数据库事务，保存修改
        session.refresh(task)  # 刷新任务对象，拿到最新数据
        return task  # 返回更新后的任务对象


def update_agent_task_progress(  # 定义更新 Agent 任务进度的服务函数
    task_id: int,  # 接收任务 ID，用来定位要更新哪一个 AgentTask
    status: str | None = None,  # 接收任务状态，可以为空；为空时不更新状态
    progress: int | None = None,  # 接收任务进度，可以为空；为空时不更新进度
    current_step: str | None = None,  # 接收当前步骤说明，可以为空；为空时不更新当前步骤
    answer: str | None = None,  # 接收任务最终回答，可以为空；为空时不更新回答
    report_id: int | None = None,  # 接收报告 ID，可以为空；为空时不更新报告 ID
    markdown_file_path: (
        str | None
    ) = None,  # 接收 Markdown 文件路径，可以为空；为空时不更新文件路径
    error: str | None = None,  # 接收错误信息，可以为空；为空时不更新错误信息
) -> AgentTask | None:  # 返回更新后的 AgentTask，如果任务不存在则返回 None
    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        task = session.get(AgentTask, task_id)  # 根据任务 ID 查询 AgentTask 记录

        if task is None:  # 判断任务是否不存在
            return None  # 如果任务不存在，直接返回 None

        now = datetime.now()  # 获取当前时间，后面用于更新时间字段

        if status is not None:  # 判断是否传入了新的任务状态
            task.status = status  # 如果传入了状态，就更新任务状态

            if status == "queued":  # 判断任务状态是否变成 queued
                task.queued_at = now  # 记录任务入队时间

            if (
                status == "running" and task.started_at is None
            ):  # 判断任务是否第一次进入 running 状态
                task.started_at = now  # 记录任务开始执行时间

            if status in ["success", "completed", "failed", "cancelled", "export_failed"]:  # 判断任务是否进入结束状态
                task.finished_at = now  # 记录任务结束时间

            if status == "failed":  # 判断任务是否失败
                task.failed_at = now  # 记录任务失败时间

            if status in ["running", "success", "completed"]:  # 判断任务是否进入运行中或完成状态
                task.error = None  # 清空旧错误信息，避免重试成功后还保留旧错误

        if progress is not None:  # 判断是否传入了任务进度
            if progress < 0:  # 判断进度是否小于 0
                progress = 0  # 如果小于 0，就修正为 0

            if progress > 100:  # 判断进度是否大于 100
                progress = 100  # 如果大于 100，就修正为 100

            task.progress = progress  # 更新任务进度

        if current_step is not None:  # 判断是否传入了当前步骤说明
            task.current_step = current_step  # 更新当前任务步骤说明

        if answer is not None:  # 判断是否传入了最终回答
            task.answer = answer  # 更新任务回答

        if report_id is not None:  # 判断是否传入了报告 ID
            task.report_id = report_id  # 更新报告 ID

        if markdown_file_path is not None:  # 判断是否传入了 Markdown 文件路径
            task.markdown_file_path = markdown_file_path  # 更新 Markdown 文件路径

        if error is not None:  # 判断是否传入了错误信息
            task.error = error  # 更新错误信息

        task.updated_at = now  # 更新任务更新时间

        session.add(task)  # 把修改后的任务对象加入数据库会话
        session.commit()  # 提交数据库事务，保存修改
        session.refresh(task)  # 刷新任务对象，拿到最新数据库数据

        return task  # 返回更新后的任务对象

def update_agent_task_type(  # 定义更新 AgentTask 任务类型的函数
    task_id: int,  # 接收要更新的 AgentTask ID
    task_type: str,  # 接收新的任务类型，例如 normal_chat、rag_chat、report
) -> None:  # 这个函数只负责更新数据库，不返回数据
    with Session(engine) as session:  # 创建数据库会话
        task = session.get(AgentTask, task_id)  # 根据任务 ID 查询 AgentTask 记录

        if task is None:  # 判断任务是否不存在
            return  # 如果任务不存在，就直接结束函数

        task.task_type = task_type  # 把数据库里的任务类型更新成最新分类结果

        if hasattr(task, "updated_at"):  # 判断 AgentTask 模型是否有 updated_at 字段
            task.updated_at = datetime.now()  # 如果有 updated_at，就更新修改时间

        session.add(task)  # 把修改后的任务对象加入数据库会话
        session.commit()  # 提交事务，让修改真正写入数据库

def cancel_agent_task(  # 定义取消 Agent 后台任务的服务函数
    task_id: int,  # 接收任务 ID，用来定位要取消哪一个 AgentTask
) -> dict[str, Any]:  # 返回字典结果，里面包含 success、task、message、error 等信息
    cancellable_statuses = [  # 定义允许取消的任务状态列表
        "created",  # created 表示任务刚创建，还没有真正执行，可以取消
        "queued",  # queued 表示任务已入队但 Worker 还没开始执行，可以取消
        "waiting_approval",  # waiting_approval 表示任务正在等待人工确认，可以取消
        "approved",  # approved 表示任务已确认但还没真正执行，可以取消
    ]  # 允许取消状态列表结束

    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        task = session.get(AgentTask, task_id)  # 根据任务 ID 查询 AgentTask 记录

        if task is None:  # 判断任务是否不存在
            return {  # 返回任务不存在结果
                "success": False,  # success 为 False，表示取消失败
                "task": None,  # 任务不存在，所以 task 返回 None
                "message": "任务不存在。",  # 返回给用户看的提示信息
                "error": "任务不存在",  # 返回错误原因
            }  # 任务不存在结果返回结束

        if task.status == "cancelled":  # 判断任务是否已经取消过
            return {  # 返回重复取消结果
                "success": False,  # success 为 False，表示这次没有执行新的取消操作
                "task": task,  # 返回当前任务对象
                "message": "任务已经取消。",  # 返回给用户看的提示信息
                "error": "任务已经取消",  # 返回错误原因
            }  # 重复取消结果返回结束

        if task.status in ["success", "completed"]:  # 判断任务是否已经成功完成
            return {  # 返回不能取消成功任务的结果
                "success": False,  # success 为 False，表示取消失败
                "task": task,  # 返回当前任务对象
                "message": "任务已经完成，不能取消。",  # 返回给用户看的提示信息
                "error": "任务已完成，不能取消",  # 返回错误原因
            }  # 成功任务不能取消结果返回结束

        if task.status == "failed":  # 判断任务是否已经失败
            return {  # 返回不能取消失败任务的结果
                "success": False,  # success 为 False，表示取消失败
                "task": task,  # 返回当前任务对象
                "message": "任务已经失败，不能取消；如果需要重新执行，请使用 retry。",  # 返回给用户看的提示信息
                "error": "任务已失败，不能取消",  # 返回错误原因
            }  # 失败任务不能取消结果返回结束

        if task.status == "running":  # 判断任务是否正在执行
            return {  # 返回 running 暂不支持取消的结果
                "success": False,  # success 为 False，表示取消失败
                "task": task,  # 返回当前任务对象
                "message": "任务正在执行中，当前学习版暂不支持强制取消。",  # 返回给用户看的提示信息
                "error": "running 状态暂不支持取消",  # 返回错误原因
            }  # running 不能取消结果返回结束

        if (
            task.status not in cancellable_statuses
        ):  # 判断任务状态是否不在允许取消列表里
            return {  # 返回状态不支持取消的结果
                "success": False,  # success 为 False，表示取消失败
                "task": task,  # 返回当前任务对象
                "message": f"当前任务状态为 {task.status}，不支持取消。",  # 返回给用户看的提示信息
                "error": "当前状态不支持取消",  # 返回错误原因
            }  # 状态不支持取消结果返回结束

        now = datetime.now()  # 获取当前时间，用来记录任务结束时间和更新时间

        task.status = "cancelled"  # 把任务状态更新为 cancelled

        task.current_step = "任务已取消"  # 更新当前任务步骤说明

        task.finished_at = now  # 记录任务取消完成时间

        task.updated_at = now  # 更新任务更新时间

        task.error = None  # 取消成功不是异常失败，所以清空错误信息

        session.add(task)  # 把修改后的任务对象加入数据库会话

        session.commit()  # 提交数据库事务，保存取消结果

        session.refresh(task)  # 刷新任务对象，拿到最新数据库数据

        return {  # 返回取消成功结果
            "success": True,  # success 为 True，表示取消成功
            "task": task,  # 返回取消后的任务对象
            "message": "任务已取消。",  # 返回给用户看的提示信息
            "error": None,  # 取消成功时错误信息为空
        }  # 取消成功结果返回结束


def update_agent_task_job_id(  # 定义更新 AgentTask 对应 RQ Job ID 的服务函数
    task_id: int,  # 接收任务 ID，用来定位要更新哪一个 AgentTask
    job_id: str,  # 接收 RQ Job ID，用来关联 Redis Queue 里的后台任务
) -> AgentTask | None:  # 返回更新后的 AgentTask，如果任务不存在则返回 None
    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        task = session.get(AgentTask, task_id)  # 根据任务 ID 查询 AgentTask 记录

        if task is None:  # 判断任务是否不存在
            return None  # 如果任务不存在，直接返回 None

        task.job_id = job_id  # 保存 RQ Job ID

        task.updated_at = datetime.now()  # 更新任务更新时间

        session.add(task)  # 把修改后的任务对象加入数据库会话

        session.commit()  # 提交数据库事务，保存 Job ID

        session.refresh(task)  # 刷新任务对象，拿到最新数据库数据

        return task  # 返回更新后的任务对象


def create_agent_step(  # 定义创建 Agent 执行步骤记录的服务函数
    task_id: int,  # 接收任务 ID，表示这个步骤属于哪个 AgentTask
    step_name: str,  # 接收步骤名称，例如 retrieve_knowledge、wait_for_approval、retry_task
    step_type: str = "system",  # 接收步骤类型，例如 node、tool、approval、database、file
    status: str = "success",  # 接收步骤状态，默认 success
    input_data: dict[str, Any] | None = None,  # 接收步骤输入数据，可以为空
    output_data: dict[str, Any] | None = None,  # 接收步骤输出数据，可以为空
    error: str | None = None,  # 接收错误信息，可以为空
    retry_count: int = 0,  # 接收当前步骤属于第几次重试，默认 0 表示第一次正常执行
    is_retry: bool = False,  # 接收当前步骤是否来自重试流程，默认 False
    started_at: datetime | None = None,  # 接收步骤开始时间，可以为空
    finished_at: datetime | None = None,  # 接收步骤结束时间，可以为空
) -> AgentStep:  # 返回创建好的 AgentStep 对象
    input_data = input_data or {}  # 如果 input_data 是 None，就改成空字典
    output_data = output_data or {}  # 如果 output_data 是 None，就改成空字典

    step = AgentStep(  # 创建 AgentStep 数据库对象
        task_id=task_id,  # 保存所属任务 ID
        step_name=step_name,  # 保存步骤名称
        step_type=step_type,  # 保存步骤类型
        status=status,  # 保存步骤状态
        input_data=input_data,  # 保存步骤输入数据
        output_data=output_data,  # 保存步骤输出数据
        error=error,  # 保存错误信息
        retry_count=retry_count,  # 保存当前步骤属于第几次重试
        is_retry=is_retry,  # 保存当前步骤是否来自重试流程
        started_at=started_at,  # 保存步骤开始时间
        finished_at=finished_at,  # 保存步骤结束时间
    )  # AgentStep 对象创建结束

    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        session.add(step)  # 把步骤对象加入数据库会话
        session.commit()  # 提交数据库事务，把步骤写入 agent_steps 表
        session.refresh(step)  # 刷新步骤对象，拿到数据库自动生成的 id
        return step  # 返回创建好的步骤对象



def update_agent_step_result(  # 定义更新 AgentStep 执行结果的服务函数
    step_id: int | None,  # 接收步骤 ID，可以为空；为空时直接跳过
    status: str,  # 接收步骤最终状态，例如 success、failed、waiting_approval
    output_data: dict[str, Any] | None = None,  # 接收步骤输出数据，可以为空
    error: str | None = None,  # 接收步骤错误信息，可以为空
) -> AgentStep | None:  # 返回更新后的步骤对象，如果不存在就返回 None
    if step_id is None:  # 判断是否没有传入步骤 ID
        return None  # 没有步骤 ID 时无法更新，直接返回 None

    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        step = session.get(AgentStep, step_id)  # 根据步骤 ID 查询 AgentStep 记录

        if step is None:  # 判断步骤是否不存在
            return None  # 步骤不存在就直接返回 None

        step.status = status  # 更新步骤状态

        if output_data is not None:  # 判断是否传入了输出数据
            step.output_data = output_data  # 更新步骤输出数据

        step.error = error  # 更新步骤错误信息，成功时通常为 None

        if status in ["success", "failed", "cancelled", "export_failed"]:  # 判断步骤是否进入结束状态
            step.finished_at = datetime.now()  # 记录步骤结束时间

        session.add(step)  # 把修改后的步骤对象加入数据库会话
        session.commit()  # 提交数据库事务，保存步骤结果
        session.refresh(step)  # 刷新步骤对象，拿到最新数据库数据

        return step  # 返回更新后的步骤对象

def list_agent_steps(
    task_id: int,
) -> list[AgentStep]:  # 定义根据任务 ID 查询步骤列表的服务函数
    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        statement = (  # 创建查询语句
            select(AgentStep)  # 查询 AgentStep 表
            .where(AgentStep.task_id == task_id)  # 只查询指定 task_id 的步骤
            .order_by(
                AgentStep.created_at.asc()
            )  # 按创建时间升序排列，先创建的步骤排前面
        )  # 查询语句创建结束

        steps = session.exec(statement).all()  # 执行查询语句，获取所有步骤记录
        return list(steps)  # 把查询结果转换成列表并返回


def list_failed_agent_tasks(
    limit: int = 20,
) -> list[AgentTask]:  # 定义查询失败任务列表的服务函数，默认最多返回 20 条
    if limit <= 0:  # 判断 limit 是否小于等于 0
        limit = 20  # 如果传入不合理，就恢复默认查询 20 条

    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        statement = (  # 创建查询语句
            select(AgentTask)  # 查询 AgentTask 表
            .where(AgentTask.status == "failed")  # 只查询状态为 failed 的任务
            .order_by(
                AgentTask.failed_at.desc()
            )  # 按失败时间倒序排列，最近失败的排前面
            .limit(limit)  # 限制返回数量，避免一次查太多数据
        )  # 查询语句创建结束

        tasks = session.exec(statement).all()  # 执行查询语句，获取失败任务列表
        return list(tasks)  # 把查询结果转换成普通列表并返回

def increase_agent_task_retry_count(
    task_id: int,
) -> AgentTask | None:  # 定义增加任务重试次数的服务函数
    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        task = session.get(AgentTask, task_id)  # 根据任务 ID 查询 AgentTask 记录

        if task is None:  # 判断任务是否不存在
            return None  # 如果任务不存在，直接返回 None

        task.retry_count = task.retry_count + 1  # 把任务重试次数加 1
        task.last_retry_at = datetime.now()  # 记录最后一次重试时间
        task.updated_at = datetime.now()  # 更新任务更新时间

        session.add(task)  # 把修改后的任务对象加入数据库会话
        session.commit()  # 提交数据库事务，保存 retry_count 和 last_retry_at
        session.refresh(task)  # 刷新任务对象，拿到最新数据
        return task  # 返回更新后的任务对象


def can_retry_agent_task(task: AgentTask) -> bool:  # 定义判断任务是否还能重试的服务函数
    if task.status != "failed":  # 判断任务状态是否不是 failed
        return False  # 只有 failed 状态的任务才允许重试

    if task.retry_count >= task.max_retries:  # 判断当前重试次数是否已经达到最大重试次数
        return False  # 如果已经达到最大次数，就不允许继续重试

    return True  # 如果任务是 failed，并且重试次数还没超限，就允许重试


def update_agent_task_context(  # 定义更新 AgentTask 检索上下文的服务函数
    task_id: int,  # 接收任务 ID，用来定位要更新哪一个 AgentTask
    context: str,  # 接收知识库检索上下文
    citations: list[dict[str, Any]] | None = None,  # 接收引用来源列表，可以为空
) -> AgentTask | None:  # 返回更新后的 AgentTask，如果任务不存在则返回 None
    citations = (
        citations or []
    )  # 如果 citations 是 None，就改成空列表，避免 JSON 字段保存 None

    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        task = session.get(AgentTask, task_id)  # 根据任务 ID 查询 AgentTask 记录

        if task is None:  # 判断任务是否不存在
            return None  # 如果任务不存在，直接返回 None

        task.context = context  # 更新任务的知识库检索上下文

        task.citations = citations  # 更新任务的引用来源列表

        task.updated_at = datetime.now()  # 更新任务更新时间

        session.add(task)  # 把修改后的任务对象加入数据库会话

        session.commit()  # 提交数据库事务，保存 context 和 citations

        session.refresh(task)  # 刷新任务对象，拿到最新数据库数据

        return task  # 返回更新后的任务对象


def update_agent_task_final_result(  # 定义更新 Agent 任务最终结果的函数
    task_id: int,  # 接收任务 ID
    status: str,  # 接收最终任务状态，比如 completed、failed、waiting_approval
    current_step: str | None = None,  # 接收当前步骤说明，可以为空
    error: str | None = None,  # 接收错误信息，可以为空
    report_id: int | None = None,  # 接收报告 ID，可以为空
    markdown_file_path: str | None = None,  # 接收 Markdown 文件路径，可以为空
    progress: int | None = None,  # 接收任务进度，可以为空
) -> AgentTask | None:  # 返回更新后的 AgentTask，如果任务不存在就返回 None
    with Session(engine) as session:  # 创建数据库会话
        task = session.get(AgentTask, task_id)  # 根据任务 ID 查询 AgentTask

        if task is None:  # 判断任务是否不存在
            return None  # 如果任务不存在，直接返回 None

        now = datetime.now()  # 获取当前时间，用来统一更新时间字段

        task.status = status  # 更新任务状态

        if current_step is not None:  # 判断是否传入当前步骤说明
            task.current_step = current_step  # 更新当前步骤说明

        if error is not None:  # 判断是否传入错误信息
            task.error = error  # 更新错误信息

        if status in ["running", "success", "completed", "waiting_approval"] and error is None:  # 判断是否进入非失败状态
            task.error = None  # 清空旧错误信息，避免成功任务仍显示历史错误

        if report_id is not None:  # 判断是否传入报告 ID
            task.report_id = report_id  # 更新报告 ID

        if markdown_file_path is not None:  # 判断是否传入 Markdown 文件路径
            task.markdown_file_path = markdown_file_path  # 更新 Markdown 文件路径

        if progress is not None:  # 判断是否传入进度
            if progress < 0:  # 判断进度是否小于 0
                progress = 0  # 小于 0 时修正为 0

            if progress > 100:  # 判断进度是否大于 100
                progress = 100  # 大于 100 时修正为 100

            task.progress = progress  # 更新任务进度

        if status == "running" and task.started_at is None:  # 判断任务是否第一次进入 running
            task.started_at = now  # 记录任务开始时间

        if status in ["success", "completed", "failed", "cancelled", "export_failed"]:  # 判断任务是否进入结束状态
            task.finished_at = now  # 记录任务结束时间

        if status == "failed":  # 判断任务是否失败
            task.failed_at = now  # 记录任务失败时间

        task.updated_at = now  # 更新时间

        session.add(task)  # 保存任务修改
        session.commit()  # 提交数据库事务
        session.refresh(task)  # 刷新任务对象，拿到最新数据

        return task  # 返回更新后的任务对象
