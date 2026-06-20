from typing import Any  # 导入 Any，用来表示字典里可以保存任意类型的数据

from services.agent_nodes import (
    generate_report_node,
)  # 导入报告生成节点，后台任务会复用它生成报告、保存报告、导出 Markdown

from services.agent_task_service import (
    create_agent_step,
)  # 导入创建任务步骤记录的服务函数

from services.agent_task_service import (
    get_agent_task,
)  # 导入根据任务 ID 查询 AgentTask 的服务函数

from services.agent_task_service import (
    update_agent_task_context,
)  # 导入更新任务检索上下文的服务函数

from services.agent_task_service import (
    update_agent_task_progress,
)  # 导入更新任务进度的服务函数

from services.agent_tools import (
    execute_agent_tool,
)  # 导入统一工具执行函数，用来调用 search_knowledge_base 工具


def run_agent_task(
    task_id: int,
) -> dict[str, Any]:  # 定义后台 Agent 任务执行函数，Worker 会调用这个函数
    steps: list[str] = []  # 创建步骤列表，用来记录本次后台任务执行过程

    task = get_agent_task(task_id)  # 根据任务 ID 查询 AgentTask 数据库记录

    if task is None:  # 判断任务是否不存在
        return {  # 返回任务不存在结果
            "success": False,  # success 为 False，表示后台任务执行失败
            "task_id": task_id,  # 返回传入的任务 ID
            "error": "任务不存在",  # 返回错误原因
        }  # 任务不存在结果返回结束
    if task.status == "cancelled":  # 判断任务是否已经被用户取消
        create_agent_step(  # 创建 Worker 发现任务已取消的步骤记录
            task_id=task.id,  # 关联当前任务 ID
            step_name="worker_skip_cancelled_task",  # 设置步骤名称为 Worker 跳过已取消任务
            step_type="worker",  # 设置步骤类型为 worker
            status="success",  # 设置步骤状态为成功，因为 Worker 正确跳过了任务
            input_data={  # 保存步骤输入数据
                "task_id": task.id,  # 保存任务 ID
                "task_status": task.status,  # 保存任务当前状态
            },  # 输入数据结束
            output_data={  # 保存步骤输出数据
                "message": "任务已取消，Worker 跳过执行。",  # 保存跳过执行说明
            },  # 输出数据结束
        )  # Worker 跳过取消任务步骤记录创建结束

        return {  # 返回跳过执行结果
            "success": False,  # success 为 False，表示没有真正执行任务
            "task_id": task.id,  # 返回任务 ID
            "error": "任务已取消，Worker 跳过执行",  # 返回跳过原因
        }  # 跳过执行结果返回结束
    if task.task_type != "report":  # 判断当前任务类型是否不是 report
        error_message = "当前后台任务暂时只支持 report 类型。"  # 定义错误提示

        update_agent_task_progress(  # 更新任务为失败状态
            task_id=task.id,  # 传入任务 ID
            status="failed",  # 把任务状态改成 failed
            current_step="任务类型不支持",  # 更新当前步骤说明
            error=error_message,  # 保存失败原因
        )  # 任务失败状态更新结束

        create_agent_step(  # 创建任务步骤记录
            task_id=task.id,  # 关联当前任务 ID
            step_name="task_type_not_supported",  # 设置步骤名称为任务类型不支持
            step_type="system",  # 设置步骤类型为系统流程
            status="failed",  # 设置步骤状态为失败
            input_data={  # 保存步骤输入数据
                "task_type": task.task_type,  # 保存当前任务类型
            },  # 输入数据结束
            output_data={},  # 没有正常输出，所以保存空字典
            error=error_message,  # 保存错误信息
        )  # 步骤记录创建结束

        return {  # 返回任务类型不支持结果
            "success": False,  # success 为 False，表示执行失败
            "task_id": task.id,  # 返回任务 ID
            "error": error_message,  # 返回错误原因
        }  # 任务类型不支持结果返回结束

    try:  # 尝试执行完整后台任务，防止异常导致 Worker 崩掉
        update_agent_task_progress(  # 更新任务为运行中
            task_id=task.id,  # 传入任务 ID
            status="running",  # 把任务状态改成 running
            progress=10,  # 把任务进度改成 10
            current_step="开始执行后台任务",  # 更新当前步骤说明
        )  # 任务运行状态更新结束

        steps.append("开始执行后台任务")  # 把开始执行任务加入步骤列表

        create_agent_step(  # 创建后台任务开始步骤记录
            task_id=task.id,  # 关联当前任务 ID
            step_name="background_task_started",  # 设置步骤名称为后台任务开始
            step_type="worker",  # 设置步骤类型为 worker
            status="success",  # 设置步骤状态为成功
            input_data={  # 保存步骤输入数据
                "task_id": task.id,  # 保存任务 ID
            },  # 输入数据结束
            output_data={  # 保存步骤输出数据
                "message": "后台任务开始执行。",  # 保存步骤说明
            },  # 输出数据结束
        )  # 后台任务开始步骤记录创建结束

        if task.knowledge_base_id is None:  # 判断 report 任务是否没有知识库 ID
            error_message = (
                "报告任务缺少 knowledge_base_id，无法检索知识库。"  # 定义错误信息
            )

            update_agent_task_progress(  # 更新任务为失败状态
                task_id=task.id,  # 传入任务 ID
                status="failed",  # 把任务状态改成 failed
                current_step="缺少知识库 ID",  # 更新当前步骤说明
                error=error_message,  # 保存失败原因
            )  # 任务失败状态更新结束

            create_agent_step(  # 创建缺少知识库 ID 的失败步骤
                task_id=task.id,  # 关联当前任务 ID
                step_name="missing_knowledge_base_id",  # 设置步骤名称为缺少知识库 ID
                step_type="validation",  # 设置步骤类型为参数校验
                status="failed",  # 设置步骤状态为失败
                input_data={  # 保存步骤输入数据
                    "knowledge_base_id": task.knowledge_base_id,  # 保存知识库 ID
                },  # 输入数据结束
                output_data={},  # 没有正常输出，所以保存空字典
                error=error_message,  # 保存错误信息
            )  # 缺少知识库 ID 步骤记录创建结束

            return {  # 返回失败结果
                "success": False,  # success 为 False，表示执行失败
                "task_id": task.id,  # 返回任务 ID
                "error": error_message,  # 返回错误原因
            }  # 失败结果返回结束

        update_agent_task_progress(  # 更新任务进度为知识库检索阶段
            task_id=task.id,  # 传入任务 ID
            progress=30,  # 把任务进度改成 30
            current_step="正在检索知识库",  # 更新当前步骤说明
        )  # 知识库检索进度更新结束

        steps.append("正在检索知识库")  # 把知识库检索步骤加入步骤列表

        search_result = execute_agent_tool(  # 调用统一工具执行函数，执行知识库检索工具
            "search_knowledge_base",  # 工具名称是 search_knowledge_base
            {  # 工具输入参数
                "knowledge_base_id": task.knowledge_base_id,  # 传入知识库 ID
                "question": task.user_input,  # 传入用户原始输入作为检索问题
                "top_k": 5,  # 设置最多检索 5 条相关内容
            },  # 工具输入参数结束
        )  # 知识库检索工具调用结束

        if not search_result.get("success"):  # 判断知识库检索是否失败
            error_message = search_result.get(
                "error", "知识库检索失败"
            )  # 取出错误信息，如果没有就使用默认错误

            update_agent_task_progress(  # 更新任务为失败状态
                task_id=task.id,  # 传入任务 ID
                status="failed",  # 把任务状态改成 failed
                progress=30,  # 保留失败时的进度为 30
                current_step="知识库检索失败",  # 更新当前步骤说明
                error=error_message,  # 保存失败原因
            )  # 任务失败状态更新结束

            create_agent_step(  # 创建知识库检索失败步骤记录
                task_id=task.id,  # 关联当前任务 ID
                step_name="retrieve_knowledge_failed",  # 设置步骤名称为知识库检索失败
                step_type="tool",  # 设置步骤类型为工具调用
                status="failed",  # 设置步骤状态为失败
                input_data={  # 保存步骤输入数据
                    "knowledge_base_id": task.knowledge_base_id,  # 保存知识库 ID
                    "question": task.user_input,  # 保存检索问题
                    "top_k": 5,  # 保存检索数量
                },  # 输入数据结束
                output_data=search_result,  # 保存工具返回结果
                error=error_message,  # 保存错误信息
            )  # 知识库检索失败步骤记录创建结束

            return {  # 返回失败结果
                "success": False,  # success 为 False，表示执行失败
                "task_id": task.id,  # 返回任务 ID
                "error": error_message,  # 返回错误原因
            }  # 失败结果返回结束

        search_data = search_result.get("data", {})  # 从工具结果中取出 data 数据

        context = search_data.get("context", "")  # 从 data 中取出知识库上下文

        citations = search_data.get("citations", [])  # 从 data 中取出引用来源列表

        update_agent_task_context(  # 把检索结果保存回 AgentTask
            task_id=task.id,  # 传入任务 ID
            context=context,  # 保存知识库上下文
            citations=citations,  # 保存引用来源列表
        )  # 检索上下文保存结束

        create_agent_step(  # 创建知识库检索成功步骤记录
            task_id=task.id,  # 关联当前任务 ID
            step_name="retrieve_knowledge",  # 设置步骤名称为知识库检索
            step_type="tool",  # 设置步骤类型为工具调用
            status="success",  # 设置步骤状态为成功
            input_data={  # 保存步骤输入数据
                "knowledge_base_id": task.knowledge_base_id,  # 保存知识库 ID
                "question": task.user_input,  # 保存检索问题
                "top_k": 5,  # 保存检索数量
            },  # 输入数据结束
            output_data={  # 保存步骤输出数据
                "context_length": len(context),  # 保存上下文长度
                "citations_count": len(citations),  # 保存引用数量
            },  # 输出数据结束
        )  # 知识库检索成功步骤记录创建结束

        update_agent_task_progress(  # 更新任务进度为报告生成阶段
            task_id=task.id,  # 传入任务 ID
            progress=60,  # 把任务进度改成 60
            current_step="正在生成报告内容",  # 更新当前步骤说明
        )  # 报告生成进度更新结束

        steps.append("正在生成报告内容")  # 把报告生成步骤加入步骤列表

        report_state = {  # 构造 generate_report_node 需要的 AgentState 数据
            "user_input": task.user_input,  # 放入用户原始输入
            "task_type": task.task_type,  # 放入任务类型
            "knowledge_base_id": task.knowledge_base_id,  # 放入知识库 ID
            "session_id": task.session_id,  # 放入会话 ID
            "context": context,  # 放入检索得到的上下文
            "citations": citations,  # 放入检索得到的引用来源
            "steps": steps,  # 放入当前步骤列表
        }  # AgentState 构造结束

        result = generate_report_node(
            report_state
        )  # 调用报告生成节点，生成报告、保存报告、导出 Markdown

        if result.get("error"):  # 判断报告生成节点是否返回错误
            error_message = result.get(
                "error", "报告生成失败"
            )  # 取出错误信息，如果没有就使用默认错误

            update_agent_task_progress(  # 更新任务为失败状态
                task_id=task.id,  # 传入任务 ID
                status="failed",  # 把任务状态改成 failed
                progress=60,  # 保留失败时进度为 60
                current_step="报告生成失败",  # 更新当前步骤说明
                error=error_message,  # 保存失败原因
            )  # 任务失败状态更新结束

            create_agent_step(  # 创建报告生成失败步骤记录
                task_id=task.id,  # 关联当前任务 ID
                step_name="generate_report_failed",  # 设置步骤名称为报告生成失败
                step_type="tool",  # 设置步骤类型为工具调用
                status="failed",  # 设置步骤状态为失败
                input_data=report_state,  # 保存报告生成输入数据
                output_data=result,  # 保存报告生成输出结果
                error=error_message,  # 保存错误信息
            )  # 报告生成失败步骤记录创建结束

            return {  # 返回失败结果
                "success": False,  # success 为 False，表示执行失败
                "task_id": task.id,  # 返回任务 ID
                "error": error_message,  # 返回错误原因
            }  # 失败结果返回结束

        final_answer = result.get("answer", "")  # 从报告生成结果中取出最终报告正文

        report_id = result.get("report_id")  # 从报告生成结果中取出报告 ID

        markdown_file_path = result.get(
            "markdown_file_path"
        )  # 从报告生成结果中取出 Markdown 文件路径

        update_agent_task_progress(  # 更新任务为成功状态
            task_id=task.id,  # 传入任务 ID
            status="success",  # 把任务状态改成 success
            progress=100,  # 把任务进度改成 100
            current_step="任务完成",  # 更新当前步骤说明
            answer=final_answer,  # 保存最终报告正文
            report_id=report_id,  # 保存报告 ID
            markdown_file_path=markdown_file_path,  # 保存 Markdown 文件路径
        )  # 任务成功状态更新结束

        create_agent_step(  # 创建后台任务成功步骤记录
            task_id=task.id,  # 关联当前任务 ID
            step_name="background_task_success",  # 设置步骤名称为后台任务成功
            step_type="worker",  # 设置步骤类型为 worker
            status="success",  # 设置步骤状态为成功
            input_data={  # 保存步骤输入数据
                "task_id": task.id,  # 保存任务 ID
            },  # 输入数据结束
            output_data={  # 保存步骤输出数据
                "report_id": report_id,  # 保存报告 ID
                "markdown_file_path": markdown_file_path,  # 保存 Markdown 文件路径
            },  # 输出数据结束
        )  # 后台任务成功步骤记录创建结束

        return {  # 返回后台任务成功结果
            "success": True,  # success 为 True，表示执行成功
            "task_id": task.id,  # 返回任务 ID
            "report_id": report_id,  # 返回报告 ID
            "markdown_file_path": markdown_file_path,  # 返回 Markdown 文件路径
        }  # 成功结果返回结束

    except Exception as exc:  # 捕获后台任务执行过程中的异常
        error_message = str(exc)  # 把异常对象转换成字符串错误信息

        update_agent_task_progress(  # 更新任务为失败状态
            task_id=task.id,  # 传入任务 ID
            status="failed",  # 把任务状态改成 failed
            current_step="后台任务执行失败",  # 更新当前步骤说明
            error=error_message,  # 保存异常错误信息
        )  # 任务失败状态更新结束

        create_agent_step(  # 创建后台任务异常步骤记录
            task_id=task.id,  # 关联当前任务 ID
            step_name="background_task_error",  # 设置步骤名称为后台任务异常
            step_type="worker",  # 设置步骤类型为 worker
            status="failed",  # 设置步骤状态为失败
            input_data={  # 保存步骤输入数据
                "task_id": task.id,  # 保存任务 ID
            },  # 输入数据结束
            output_data={},  # 异常时没有正常输出，所以保存空字典
            error=error_message,  # 保存异常错误信息
        )  # 后台任务异常步骤记录创建结束

        return {  # 返回后台任务失败结果
            "success": False,  # success 为 False，表示执行失败
            "task_id": task.id,  # 返回任务 ID
            "error": error_message,  # 返回错误原因
        }  # 后台任务失败结果返回结束
