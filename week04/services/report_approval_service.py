import json  # 导入 json 模块，用来兼容 output_data 是字符串时的解析

from datetime import datetime  # 导入 datetime，用来更新任务时间

from typing import Any  # 导入 Any，用来标注任意类型

from sqlalchemy import desc  # 导入 desc，用来按 ID 倒序查询最新步骤

from sqlmodel import Session, select  # 导入 Session 和 select，用来操作数据库

from database import engine  # 导入数据库 engine，用来创建数据库会话

from models import AgentStep, AgentTask  # 导入 AgentStep 和 AgentTask 模型

from services.agent_task_service import create_agent_step  # 导入创建任务步骤的函数

from services.tool_logging_service import (
    call_tool_with_logging,
)  # 导入带日志记录的工具调用函数


def normalize_json_dict(  # 定义 JSON 字典标准化函数
    value: Any,  # 接收任意类型的数据
) -> dict[str, Any]:  # 返回字典类型
    if isinstance(value, dict):  # 判断 value 是否已经是字典
        return value  # 如果已经是字典，就直接返回

    if isinstance(value, str):  # 判断 value 是否是字符串
        try:  # 尝试解析 JSON 字符串
            parsed_value = json.loads(value)  # 把字符串解析成 Python 对象

            if isinstance(parsed_value, dict):  # 判断解析结果是否是字典
                return parsed_value  # 如果是字典，就返回解析结果

            return {}  # 如果解析结果不是字典，就返回空字典

        except Exception:  # 捕获 JSON 解析异常
            return {}  # 解析失败时返回空字典

    return {}  # 其他类型统一返回空字典


def get_latest_report_approval_step(  # 定义查询最新报告确认步骤的函数
    task_id: int,  # 接收 AgentTask ID
) -> AgentStep | None:  # 返回 AgentStep 对象或者 None
    with Session(engine) as session:  # 创建数据库会话
        statement = (  # 构造查询语句
            select(AgentStep)  # 查询 AgentStep 表
            .where(AgentStep.task_id == task_id)  # 限制 task_id 等于当前任务 ID
            .where(
                AgentStep.step_name == "wait_for_report_approval"
            )  # 限制步骤名称为等待报告确认
            .order_by(desc(AgentStep.id))  # 按 ID 倒序，最新的排在前面
        )  # 查询语句构造结束

        approval_step = session.exec(statement).first()  # 执行查询并取第一条记录

        return approval_step  # 返回查询到的确认步骤


def update_agent_task_status(  # 定义更新 AgentTask 状态的函数
    task_id: int,  # 接收任务 ID
    status: str,  # 接收新的任务状态
) -> None:  # 不返回数据
    with Session(engine) as session:  # 创建数据库会话
        task = session.get(AgentTask, task_id)  # 根据 task_id 查询 AgentTask

        if task is None:  # 判断任务是否不存在
            return  # 任务不存在就直接结束

        task.status = status  # 更新任务状态

        if hasattr(task, "updated_at"):  # 判断模型是否有 updated_at 字段
            task.updated_at = datetime.now()  # 如果有，就更新时间

        session.add(task)  # 把更新后的任务对象加入会话
        session.commit()  # 提交事务


def approve_report_task_save_and_export(  # 定义确认报告任务、保存报告并导出 Markdown 的函数
    task_id: int,  # 接收需要确认的 AgentTask ID
) -> dict[str, Any]:  # 返回统一字典结果
    with Session(engine) as session:  # 创建数据库会话
        task = session.get(AgentTask, task_id)  # 根据 task_id 查询 AgentTask

        if task is None:  # 判断任务是否不存在
            return {  # 返回失败结果
                "success": False,  # 标记执行失败
                "task_id": task_id,  # 返回任务 ID
                "error": "Agent 任务不存在",  # 返回错误信息
            }  # 失败结果结束

        if task.status != "waiting_approval":  # 判断当前任务是否不是等待确认状态
            return {  # 返回失败结果
                "success": False,  # 标记执行失败
                "task_id": task_id,  # 返回任务 ID
                "task_status": task.status,  # 返回当前任务状态
                "error": "当前任务不是 waiting_approval 状态，不能确认生成报告",  # 返回错误信息
            }  # 失败结果结束

    approval_step = get_latest_report_approval_step(  # 查询最新的报告等待确认步骤
        task_id=task_id  # 传入任务 ID
    )  # 查询确认步骤结束

    if approval_step is None:  # 判断是否没有找到等待确认步骤
        return {  # 返回失败结果
            "success": False,  # 标记执行失败
            "task_id": task_id,  # 返回任务 ID
            "error": "没有找到报告草稿确认步骤",  # 返回错误信息
        }  # 失败结果结束

    approval_data = normalize_json_dict(  # 标准化等待确认步骤里的 output_data
        approval_step.output_data  # 传入 output_data，可能是 dict，也可能是 JSON 字符串
    )  # output_data 标准化结束

    report_title = approval_data.get(  # 从 output_data 中读取报告标题
        "report_title",  # 读取 report_title 字段
        "知识库学习报告",  # 如果没有标题，就使用默认标题
    )  # 报告标题读取结束

    report_content = approval_data.get(  # 从 output_data 中读取报告草稿正文
        "report_content",  # 读取 report_content 字段
        "",  # 如果没有正文，就使用空字符串
    )  # 报告正文读取结束

    citations = approval_data.get(  # 从 output_data 中读取引用来源
        "citations",  # 读取 citations 字段
        [],  # 如果没有引用来源，就使用空列表
    )  # 引用来源读取结束

    knowledge_base_id = approval_data.get(  # 从 output_data 中读取知识库 ID
        "knowledge_base_id"  # 读取 knowledge_base_id 字段
    )  # 知识库 ID 读取结束

    if not report_content:  # 判断报告草稿正文是否为空
        return {  # 返回失败结果
            "success": False,  # 标记执行失败
            "task_id": task_id,  # 返回任务 ID
            "error": "报告草稿内容为空，不能保存和导出",  # 返回错误信息
        }  # 失败结果结束

    save_step = create_agent_step(  # 创建保存正式报告的步骤记录
        task_id=task_id,  # 关联当前 AgentTask
        step_name="save_report_after_approval",  # 设置步骤名称为确认后保存报告
        step_type="tool",  # 设置步骤类型为工具调用
        status="running",  # 设置步骤状态为运行中
        input_data={  # 保存步骤输入数据
            "report_title": report_title,  # 保存报告标题
            "report_content_preview": report_content[
                :300
            ],  # 保存报告正文前 300 字，避免日志太长
        },  # 输入数据结束
        output_data={},  # 初始化输出数据为空
    )  # 保存报告步骤创建结束

    save_step_id = (
        save_step.id if save_step else None
    )  # 获取保存报告步骤 ID，如果没有创建成功就为 None

    save_result = call_tool_with_logging(  # 调用保存报告工具，并写入 tool_calls 日志
        task_id=task_id,  # 传入任务 ID
        step_id=save_step_id,  # 传入保存报告步骤 ID
        tool_name="save_report",  # 指定工具名称为 save_report
        tool_input={  # 构造保存报告工具输入
            "title": report_title,  # 传入报告标题
            "report_content": report_content,  # 传入报告正文
            "report_type": "study_report",  # 设置报告类型为学习报告
            "source_type": "knowledge_base",  # 设置来源类型为知识库
            "source_metadata": {  # 构造来源元数据
                "knowledge_base_id": knowledge_base_id,  # 保存知识库 ID
                "citations": citations,  # 保存引用来源
                "approval_task_id": task_id,  # 保存确认任务 ID
            },  # 来源元数据结束
        },  # 工具输入结束
    )  # 保存报告工具调用结束

    if not save_result.get("success"):  # 判断保存报告是否失败
        error_message = save_result.get(  # 读取错误信息
            "error",  # 读取 error 字段
            "保存正式报告失败",  # 默认错误信息
        )  # 错误信息读取结束

        update_agent_task_status(  # 更新任务状态为 failed
            task_id=task_id,  # 传入任务 ID
            status="failed",  # 设置状态为 failed
        )  # 状态更新结束

        return {  # 返回失败结果
            "success": False,  # 标记执行失败
            "task_id": task_id,  # 返回任务 ID
            "task_status": "failed",  # 返回任务状态
            "error": error_message,  # 返回错误信息
        }  # 失败结果结束

    save_data = save_result.get(  # 读取保存报告工具返回的 data
        "data",  # 读取 data 字段
        {},  # 如果没有 data，就使用空字典
    )  # data 读取结束

    report_id = save_data.get(  # 从 data 中读取 report_id
        "report_id"  # 读取 report_id 字段
    )  # report_id 读取结束

    if report_id is None:  # 判断保存成功后是否没有返回 report_id
        update_agent_task_status(  # 更新任务状态为 failed
            task_id=task_id,  # 传入任务 ID
            status="failed",  # 设置状态为 failed
        )  # 状态更新结束

        return {  # 返回失败结果
            "success": False,  # 标记执行失败
            "task_id": task_id,  # 返回任务 ID
            "task_status": "failed",  # 返回任务状态
            "error": "保存报告成功但没有返回 report_id",  # 返回错误信息
        }  # 失败结果结束

    export_step = create_agent_step(  # 创建导出 Markdown 的步骤记录
        task_id=task_id,  # 关联当前 AgentTask
        step_name="export_markdown_after_approval",  # 设置步骤名称为确认后导出 Markdown
        step_type="tool",  # 设置步骤类型为工具调用
        status="running",  # 设置步骤状态为运行中
        input_data={  # 保存步骤输入数据
            "report_id": report_id,  # 保存报告 ID
            "report_title": report_title,  # 保存报告标题
        },  # 输入数据结束
        output_data={},  # 初始化输出数据为空
    )  # 导出 Markdown 步骤创建结束

    export_step_id = (
        export_step.id if export_step else None
    )  # 获取导出步骤 ID，如果没有创建成功就为 None

    export_result = (
        call_tool_with_logging(  # 调用导出 Markdown 工具，并写入 tool_calls 日志
            task_id=task_id,  # 传入任务 ID
            step_id=export_step_id,  # 传入导出 Markdown 步骤 ID
            tool_name="export_markdown",  # 指定工具名称为 export_markdown
            tool_input={  # 构造导出 Markdown 工具输入
                "report_id": report_id,  # 传入报告 ID
            },  # 工具输入结束
        )
    )  # 导出 Markdown 工具调用结束

    if not export_result.get("success"):  # 判断导出 Markdown 是否失败
        error_message = export_result.get(  # 读取错误信息
            "error",  # 读取 error 字段
            "导出 Markdown 失败",  # 默认错误信息
        )  # 错误信息读取结束

        update_agent_task_status(  # 更新任务状态为 export_failed
            task_id=task_id,  # 传入任务 ID
            status="export_failed",  # 设置状态为 export_failed，表示报告已保存但导出失败
        )  # 状态更新结束

        return {  # 返回失败结果
            "success": False,  # 标记执行失败
            "task_id": task_id,  # 返回任务 ID
            "task_status": "export_failed",  # 返回任务状态
            "report_id": report_id,  # 返回已经保存成功的报告 ID
            "report_title": report_title,  # 返回报告标题
            "error": error_message,  # 返回错误信息
        }  # 失败结果结束

    export_data = export_result.get(  # 读取导出工具返回 data
        "data",  # 读取 data 字段
        {},  # 如果没有 data，就使用空字典
    )  # data 读取结束

    markdown_file_path = (  # 从导出工具返回结果中读取 Markdown 文件路径
        export_data.get("file_path")  # 你的 export_markdown 工具现在返回的是 file_path
        or export_data.get(
            "markdown_file_path"
        )  # 兼容以后可能返回 markdown_file_path 的情况
        or export_data.get("path")  # 兜底兼容 path 字段
    )  # Markdown 路径读取结束

    if not markdown_file_path:  # 判断导出成功后是否没有返回文件路径
        with Session(engine) as session:  # 创建数据库会话
            task = session.get(AgentTask, task_id)  # 查询当前任务

            if task is not None:  # 判断任务是否存在
                task.status = "export_failed"  # 设置任务状态为导出失败
                task.error = (
                    "导出 Markdown 成功，但工具返回结果中缺少 file_path"  # 写入错误信息
                )
                task.report_id = report_id  # 保存已经生成成功的报告 ID

                if hasattr(task, "updated_at"):  # 判断是否有更新时间字段
                    task.updated_at = datetime.now()  # 更新时间

                session.add(task)  # 保存任务修改
                session.commit()  # 提交事务

        return {  # 返回失败结果
            "success": False,  # 标记执行失败
            "task_id": task_id,  # 返回任务 ID
            "task_status": "export_failed",  # 返回任务状态
            "report_id": report_id,  # 返回已经保存成功的报告 ID
            "report_title": report_title,  # 返回报告标题
            "error": "导出 Markdown 成功，但工具返回结果中缺少 file_path",  # 返回错误信息
        }  # 返回结束

    with Session(engine) as session:  # 创建新的数据库会话，用来更新最终任务结果
        task = session.get(AgentTask, task_id)  # 根据 task_id 查询 AgentTask

        if task is None:  # 判断任务是否不存在
            return {  # 返回失败结果
                "success": False,  # 标记失败
                "task_id": task_id,  # 返回任务 ID
                "error": "Agent 任务不存在，无法写回 report_id 和 markdown_file_path",  # 返回错误原因
            }  # 返回结束

        task.status = "completed"  # 把任务状态更新为 completed
        task.progress = 100  # 把任务进度更新为 100
        task.current_step = "报告已确认、保存并导出 Markdown"  # 更新当前步骤说明
        task.report_id = report_id  # 把保存报告得到的 report_id 写回 agent_tasks 表
        task.markdown_file_path = (
            markdown_file_path  # 把导出的 Markdown 文件路径写回 agent_tasks 表
        )
        task.error = None  # 清空错误信息

        if hasattr(task, "updated_at"):  # 判断模型是否有 updated_at 字段
            task.updated_at = datetime.now()  # 更新时间

        if save_step_id is not None:  # 判断保存报告步骤是否存在
            save_step_record = session.get(AgentStep, save_step_id)  # 查询保存报告步骤

            if save_step_record is not None:  # 判断步骤是否存在
                save_step_record.status = "success"  # 更新步骤状态为成功
                save_step_record.output_data = save_result  # 保存 save_report 工具返回结果
                session.add(save_step_record)  # 保存步骤修改

        if export_step_id is not None:  # 判断导出 Markdown 步骤是否存在
            export_step_record = session.get(
                AgentStep, export_step_id
            )  # 查询导出 Markdown 步骤

            if export_step_record is not None:  # 判断步骤是否存在
                export_step_record.status = "success"  # 更新步骤状态为成功
                export_step_record.output_data = (
                    export_result  # 保存 export_markdown 工具返回结果
                )
                session.add(export_step_record)  # 保存步骤修改

        session.add(task)  # 保存任务修改
        session.commit()  # 提交事务
        session.refresh(task)  # 刷新任务对象，拿到最新数据库数据

    return {  # 返回成功结果
        "success": True,  # 标记执行成功
        "task_id": task_id,  # 返回任务 ID
        "task_status": "completed",  # 返回最终任务状态
        "report_id": report_id,  # 返回正式报告 ID
        "report_title": report_title,  # 返回报告标题
        "markdown_file_path": markdown_file_path,  # 返回 Markdown 文件路径
        "message": "报告已确认、保存并导出 Markdown 成功",  # 返回成功提示
    }  # 成功结果结束
