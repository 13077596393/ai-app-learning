#这个文件做了
#1. 接收 tool_name 和 tool_input
#2. 调用 execute_agent_tool()
#3. 记录工具执行耗时
#4. 判断 success / failed
#5. 写入 tool_calls 表
#6. 返回工具执行结果
import time  # 导入 time 模块，用来记录工具调用开始和结束时间，从而计算耗时

from typing import Any  # 导入 Any 类型，用来表示工具输入和输出里可以有任意结构的数据

from services.agent_tools import (
    execute_agent_tool,
)  # 导入原来的统一工具执行函数，真正负责执行具体工具

from services.observability_service import (
    create_tool_call,
)  # 导入工具调用日志写入函数，用来保存 tool_calls 记录


def call_tool_with_logging(  # 定义带日志记录的工具调用函数
    task_id: int | None,  # 接收 AgentTask ID，用来关联一次完整任务，也就是 trace
    step_id: int | None,  # 接收 AgentStep ID，用来关联任务里的某个步骤，也就是 span
    tool_name: str,  # 接收工具名称，例如 search_knowledge_base、generate_report、save_report、export_markdown
    tool_input: dict[str, Any] | None = None,  # 接收工具输入参数，默认可以为空
    cost: float = 0.0,  # 接收工具调用成本，本地工具一般是 0
) -> dict[str, Any]:  # 返回工具执行结果，格式仍然保持 execute_agent_tool 的返回字典
    if tool_input is None:  # 判断调用方有没有传工具输入
        tool_input = {}  # 如果没有传，就使用空字典，避免后面工具调用或日志写入出现 None

    start_time = time.time()  # 记录工具调用开始时间，用来计算 latency_ms

    try:  # 使用 try 包住工具调用，保证成功和失败都能写日志
        tool_result = execute_agent_tool(  # 调用原来的统一工具执行函数
            tool_name,  # 传入工具名称
            tool_input,  # 传入工具输入参数
        )  # 工具执行结束，返回统一格式结果

        latency_ms = int(
            (time.time() - start_time) * 1000
        )  # 计算工具执行耗时，单位是毫秒

        success = bool(
            tool_result.get("success")
        )  # 从工具结果中取出 success，并转成布尔值

        error_message = tool_result.get(
            "error"
        )  # 从工具结果中取出错误信息，成功时通常为空

        create_tool_call(  # 写入一条工具调用日志
            task_id=task_id,  # 保存任务 ID，用来关联 AgentTask
            step_id=step_id,  # 保存步骤 ID，用来关联 AgentStep
            tool_name=tool_name,  # 保存工具名称
            tool_input=tool_input,  # 保存工具输入参数
            tool_output=tool_result,  # 保存完整工具输出结果
            latency_ms=latency_ms,  # 保存工具执行耗时
            cost=cost,  # 保存工具调用成本
            status=(
                "success" if success else "failed"
            ),  # 根据工具结果保存 success 或 failed
            error=error_message,  # 保存错误信息
        )  # 工具调用日志写入结束

        return tool_result  # 返回原始工具结果，让业务流程继续使用

    except Exception as exc:  # 捕获工具执行过程中直接抛出的异常
        latency_ms = int(
            (time.time() - start_time) * 1000
        )  # 即使失败，也计算工具执行耗时

        error_message = str(exc)  # 把异常对象转成字符串，方便保存到数据库

        failed_result = {  # 构造一个统一格式的失败结果
            "success": False,  # 标记工具调用失败
            "tool_name": tool_name,  # 返回工具名称
            "data": {},  # 失败时没有正常数据，所以 data 为空字典
            "error": error_message,  # 返回错误信息
        }  # 失败结果构造结束

        create_tool_call(  # 工具抛异常时，也写入一条失败日志
            task_id=task_id,  # 保存任务 ID
            step_id=step_id,  # 保存步骤 ID
            tool_name=tool_name,  # 保存工具名称
            tool_input=tool_input,  # 保存工具输入参数
            tool_output=failed_result,  # 保存失败结果
            latency_ms=latency_ms,  # 保存失败调用耗时
            cost=cost,  # 保存工具调用成本
            status="failed",  # 保存状态为 failed
            error=error_message,  # 保存异常信息
        )  # 失败日志写入结束

        return failed_result  # 返回统一格式失败结果，避免上层业务直接崩掉
