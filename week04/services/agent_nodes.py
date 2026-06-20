# 这里就是LangGraph的节点node，这里本质上就是定义多个方法，特殊点就是
# def classify_task_node(
#       state: AgentState,
#   ) -> AgentState:这个返回结构体，最后return出去的数据，在LangGraph 节点可以只返回要更新的字段，LangGraph 会自动合并进完整 State

import time  # 导入 time 模块，用来计算知识库检索整体耗时
from schemas import (
    AgentState,
)  # 从 agent_state 文件导入 AgentState 状态类型
from services.agent_answer_service import (
    generate_agent_answer,
)  # 导入 Agent 回答生成函数
from services.agent_result_service import (
    save_agent_run_to_db,
)  # 导入保存 Agent 执行结果到数据库的函数
from services.tool_logging_service import (  # 从工具日志服务中导入带日志记录的工具调用函数
    call_tool_with_logging,  # 导入 call_tool_with_logging，用来执行工具并自动写入 tool_calls 日志
)  # 导入结束
from services.agent_task_service import (  # 从 AgentTask 服务中导入任务相关函数
    create_agent_step,  # 导入创建 AgentStep 的函数
    update_agent_step_result,  # 导入更新 AgentStep 执行结果的函数
    update_agent_task_type,  # 导入更新 AgentTask 任务类型的函数
)  # 导入结束
from services.agent_task_service import (
    create_agent_task,
    update_agent_task_status,
)  # 导入创建 AgentTask 任务的服务函数
from services.rag_logging_service import (  # 从 RAG 日志服务中导入记录 RAG 检索日志的函数
    record_rag_retrieval_from_tool_result,  # 导入函数，用来把 search_knowledge_base 的结果写入 rag_retrieval_logs 表
)  # RAG 日志服务导入结束
from services.llm_logging_service import (  # 从 LLM 日志服务中导入带日志记录的大模型调用函数
    call_llm_with_logging,  # 导入 call_llm_with_logging，用来调用大模型并写入 llm_calls 日志
)  # LLM 日志服务导入结束

def classify_task_node(  # 定义任务分类节点
    state: AgentState,  # 接收当前 AgentState
) -> AgentState:  # 返回需要更新到 AgentState 的字段
    user_input = state.get(  # 从 State 中读取用户输入
        "user_input",  # 读取 user_input 字段
        "",  # 如果没有 user_input，就使用空字符串
    )  # 用户输入读取结束

    old_steps = state.get(  # 从 State 中读取旧步骤列表
        "steps",  # 读取 steps 字段
        [],  # 如果没有 steps，就使用空列表
    )  # 旧步骤列表读取结束

    if (  # 判断用户输入是否像报告生成任务
        "报告" in user_input or "生成一份" in user_input
    ):  # 报告任务判断结束
        task_type = "report"  # 如果是报告类需求，就设置任务类型为 report
    elif state.get("knowledge_base_id") is not None:  # 判断是否传入了知识库 ID
        task_type = "rag_chat"  # 如果有知识库 ID，就设置任务类型为 RAG 问答
    else:  # 如果既不是报告，也没有知识库 ID
        task_type = "normal_chat"  # 设置任务类型为普通聊天

    task_id = state.get("task_id")  # 从 State 中读取当前 AgentTask ID

    if task_id is not None:  # 判断当前任务 ID 是否存在
        update_agent_task_type(  # 同步更新数据库里的 AgentTask 任务类型
            task_id=task_id,  # 传入当前任务 ID
            task_type=task_type,  # 传入分类后的任务类型
        )  # 数据库任务类型更新结束
    new_steps = old_steps + [  # 构造新的步骤列表
        f"任务分类完成：{task_type}"  # 追加任务分类结果
    ]  # 新步骤列表构造结束

    return {  # 返回要更新到 AgentState 的字段
        "task_type": task_type,  # 写入任务类型
        "steps": new_steps,  # 写入更新后的步骤列表
    }  # 任务分类节点返回结束


def retrieve_knowledge_node(  # 定义知识库检索节点
    state: AgentState,  # 接收当前 AgentState 状态
) -> AgentState:  # 返回要更新到 AgentState 的字段
    user_input = state.get(  # 从 State 中读取用户输入
        "user_input",  # 指定读取 user_input 字段
        "",  # 如果没有 user_input，就使用空字符串
    )  # 用户输入读取结束

    knowledge_base_id = state.get(  # 从 State 中读取知识库 ID
        "knowledge_base_id"  # 指定读取 knowledge_base_id 字段
    )  # 知识库 ID 读取结束

    old_steps = state.get(  # 从 State 中读取已有步骤列表
        "steps",  # 指定读取 steps 字段
        [],  # 如果没有 steps，就使用空列表
    )  # 旧步骤列表读取结束

    top_k = state.get(  # 从 State 中读取 top_k
        "top_k",  # 读取 top_k 字段
        5,  # 如果没有 top_k，就默认使用 5
    )  # top_k 读取结束
    if knowledge_base_id is None:  # 判断是否没有传入知识库 ID
        error_message = "知识库检索失败：未传入 knowledge_base_id"  # 定义错误信息

        return {  # 返回要更新到 AgentState 的失败字段
            "context": "",  # 没有知识库 ID 时，上下文为空
            "citations": [],  # 没有知识库 ID 时，引用来源为空
            "steps": old_steps + [error_message],  # 把错误信息追加到步骤列表
            "error": error_message,  # 把错误信息写入 State
        }  # 失败状态返回结束
    tool_input = {  # 构造传给 search_knowledge_base 工具的输入参数
        "question": user_input,  # 把用户输入作为检索问题
        "knowledge_base_id": knowledge_base_id,  # 把知识库 ID 传给工具
        "top_k": top_k,  # 把 top_k 传给工具
    }  # 工具输入参数构造结束
    task_id = state.get("task_id")  # 从 State 中读取当前 AgentTask ID，用来绑定 tool_calls 和 rag_retrieval_logs

    step_id = state.get("step_id")  # 先从 State 中读取旧 step_id，作为没有创建新步骤时的兜底值

    created_step = None  # 初始化 created_step，避免没有 task_id 时变量不存在

    if task_id is not None:  # 判断当前 State 中是否有任务 ID
        created_step = create_agent_step(  # 创建知识库检索步骤记录
            task_id=task_id,  # 关联当前 AgentTask
            step_name="retrieve_knowledge",  # 设置步骤名称为 retrieve_knowledge
            step_type="tool",  # 设置步骤类型为 tool，因为这个节点会调用知识库检索工具
            status="running",  # 设置步骤状态为 running
            input_data={  # 保存当前步骤输入数据
                "user_input": user_input,  # 保存用户输入
                "knowledge_base_id": knowledge_base_id,  # 保存知识库 ID
                "top_k": top_k,  # 保存检索数量
            },  # 输入数据结束
            output_data={},  # 初始化输出数据为空
        )  # AgentStep 创建结束

        step_id = created_step.id  # 使用新创建的 AgentStep ID 作为当前步骤 ID
    start_time = time.time()  # 记录知识库检索开始时间，用来计算检索耗时

    tool_result = call_tool_with_logging(  # 调用带日志记录的工具执行函数
        task_id=task_id,  # 传入当前任务 ID，用来关联 tool_calls
        step_id=step_id,  # 传入当前步骤 ID，用来关联 tool_calls
        tool_name="search_knowledge_base",  # 指定要调用的工具名称为 search_knowledge_base
        tool_input=tool_input,  # 传入工具输入参数
    )  # 工具调用结束，并自动写入 tool_calls 表

    latency_ms = int(
        (time.time() - start_time) * 1000
    )  # 计算本次知识库检索整体耗时，单位是毫秒

    record_rag_retrieval_from_tool_result(  # 把知识库检索结果写入 rag_retrieval_logs 表
        task_id=task_id,  # 传入当前任务 ID
        step_id=step_id,  # 传入当前步骤 ID
        knowledge_base_id=knowledge_base_id,  # 传入本次检索使用的知识库 ID
        query=user_input,  # 传入本次检索问题
        top_k=top_k,  # 传入本次检索 top_k
        tool_result=tool_result,  # 传入 search_knowledge_base 工具返回的完整结果
        latency_ms=latency_ms,  # 传入本次检索耗时
    )  # RAG 检索日志写入结束

    if not tool_result.get("success"):  # 判断知识库检索工具是否执行失败
        error_message = tool_result.get(  # 从工具结果中读取错误信息
            "error",  # 读取 error 字段
            "知识库检索工具执行失败",  # 如果没有 error，就使用默认错误信息
        )  # 错误信息读取结束

        new_steps = old_steps + [  # 构造新的步骤列表
            f"知识库检索失败：{error_message}"  # 把检索失败原因追加到步骤列表
        ]  # 新步骤列表构造结束

        update_agent_step_result(  # 把知识库检索步骤从 running 更新为 failed
            step_id=step_id,  # 传入当前检索步骤 ID
            status="failed",  # 标记步骤失败
            output_data=tool_result,  # 保存工具返回的失败结果，方便前端 trace 展示
            error=error_message,  # 保存失败原因
        )  # 检索步骤状态更新结束

        return {  # 返回要更新到 AgentState 的失败字段
            "context": "",  # 检索失败时上下文为空
            "citations": [],  # 检索失败时引用来源为空
            "step_id": step_id,  # 写入当前步骤 ID
            "steps": new_steps,  # 更新步骤列表
            "error": error_message,  # 把错误信息写入 State
        }  # 失败状态返回结束

    data = tool_result.get(  # 从工具结果中读取 data 字典
        "data",  # 读取 data 字段
        {},  # 如果没有 data，就使用空字典
    )  # data 字典读取结束

    context = data.get(  # 从 data 中读取最终上下文
        "context",  # 读取 context 字段
        "",  # 如果没有 context，就使用空字符串
    )  # 上下文读取结束

    citations = data.get(  # 从 data 中读取引用来源列表
        "citations",  # 读取 citations 字段
        [],  # 如果没有 citations，就使用空列表
    )  # 引用来源读取结束

    new_steps = old_steps + [  # 构造新的步骤列表
        "调用 search_knowledge_base 工具完成知识库检索，并写入 RAG 检索日志"  # 追加知识库检索成功步骤
    ]  # 新步骤列表构造结束

    update_agent_step_result(  # 把知识库检索步骤从 running 更新为 success
        step_id=step_id,  # 传入当前检索步骤 ID
        status="success",  # 标记步骤成功
        output_data={  # 保存检索步骤输出摘要，避免步骤表里塞入过长内容
            "context_length": len(context),  # 保存上下文长度
            "citations_count": len(citations),  # 保存引用来源数量
            "tool_result": tool_result,  # 保存完整工具返回结果，方便排查
        },  # 输出数据结束
        error=None,  # 成功时错误为空
    )  # 检索步骤状态更新结束

    return {  # 返回要更新到 AgentState 的成功字段
        "context": context,  # 把工具返回的上下文写回 State
        "citations": citations,  # 把工具返回的引用来源写回 State
        "step_id": step_id,  # 把当前步骤 ID 写回 State
        "steps": new_steps,  # 更新步骤列表
        "error": None,  # 检索成功时清空错误信息
    }  # 成功状态返回结束

def generate_report_draft_node(  # 定义生成报告草稿节点，只负责生成报告草稿，不保存、不导出
    state: AgentState,  # 接收当前 AgentState
) -> AgentState:  # 返回需要更新到 AgentState 的字段
    user_input = state.get(  # 从 State 中读取用户原始输入
        "user_input",  # 读取 user_input 字段
        "",  # 如果没有用户输入，就使用空字符串
    )  # 用户输入读取结束

    context = state.get(  # 从 State 中读取知识库检索上下文
        "context",  # 读取 context 字段
        "",  # 如果没有 context，就使用空字符串
    )  # 知识库上下文读取结束

    old_steps = state.get(  # 从 State 中读取已有步骤列表
        "steps",  # 读取 steps 字段
        [],  # 如果没有 steps，就使用空列表
    )  # 旧步骤列表读取结束

    task_id = state.get(  # 从 State 中读取当前 AgentTask ID
        "task_id"  # 读取 task_id 字段
    )  # task_id 读取结束

    step_id = state.get(  # 从 State 中读取当前 step_id
        "step_id"  # 读取 step_id 字段，后面如果创建新步骤会覆盖它
    )  # step_id 读取结束

    if not context:  # 判断是否没有知识库检索上下文
        error_message = "生成报告草稿失败：缺少知识库检索上下文"  # 定义错误信息

        if task_id is not None:  # 判断当前 State 中是否有任务 ID
            failed_step = create_agent_step(  # 创建生成报告草稿失败步骤
                task_id=task_id,  # 关联当前 AgentTask
                step_name="generate_report_draft",  # 设置步骤名称为 generate_report_draft
                step_type="llm",  # 设置步骤类型为 llm
                status="failed",  # 因为缺少上下文，直接标记失败
                input_data={  # 保存失败时的输入摘要
                    "user_input": user_input,  # 保存用户原始输入
                    "context_length": 0,  # 保存上下文长度为 0
                },  # 输入数据结束
                output_data={},  # 没有生成报告，输出为空
                error=error_message,  # 保存失败原因
            )  # 失败步骤创建结束

            update_agent_step_result(  # 立刻补充失败步骤结束时间
                step_id=failed_step.id if failed_step else None,  # 传入失败步骤 ID
                status="failed",  # 标记步骤失败
                output_data={},  # 输出为空
                error=error_message,  # 保存错误信息
            )  # 失败步骤状态更新结束

        return {  # 返回失败状态
            "answer": error_message,  # 把错误信息作为回答返回
            "report_title": "",  # 报告标题为空
            "report_content": "",  # 报告正文为空
            "steps": old_steps + [error_message],  # 追加错误步骤
            "error": error_message,  # 把错误信息写入 State
        }  # 失败状态返回结束

    if task_id is not None:  # 判断当前 State 中是否有任务 ID
        created_step = create_agent_step(  # 创建生成报告草稿步骤
            task_id=task_id,  # 关联当前 AgentTask
            step_name="generate_report_draft",  # 设置步骤名称为 generate_report_draft
            step_type="llm",  # 设置步骤类型为 llm，因为这里会调用大模型
            status="running",  # 设置步骤状态为 running
            input_data={  # 保存当前步骤输入数据
                "user_input": user_input,  # 保存用户原始输入
                "context_preview": context[:300],  # 保存知识库上下文前 300 字，避免日志太长
            },  # 输入数据结束
            output_data={},  # 初始化输出数据为空
        )  # AgentStep 创建结束

        step_id = created_step.id  # 使用新创建的步骤 ID 作为当前 step_id
    report_title = state.get("report_title") or "知识库学习报告"
    prompt = f"""你是一个专业的 AI 应用开发学习报告助手。

请根据【知识库资料】生成一份简洁、结构清晰的学习报告。

用户需求：
{user_input}

知识库资料：
{context}

报告标题：
{report_title}

输出要求：
1. 必须使用中文。
2. 必须输出 Markdown 格式。
3. 不要把知识库资料原文大段复制出来，要总结提炼。
4. 不要输出太长，控制在 1200 字以内。
5. 不要写完整代码块，除非知识库资料中明确包含关键代码。
6. 如果资料主要讲 Redis，而用户要求 LangGraph，请说明“当前知识库资料更偏 Redis 与后台任务，和 LangGraph 关系有限”。
7. 报告必须按下面结构输出：

# {report_title}

## 1. 学习主题概述
用 2 到 3 句话说明本报告主要讲什么。

## 2. 核心知识点
用分点方式总结最重要的知识点。

## 3. 实现流程
用步骤方式说明从用户请求到任务完成的流程。

## 4. 关键注意事项
列出开发时容易出错的地方。

## 5. 总结
用 2 到 3 句话总结本报告。
"""  # 构造更严格的报告生成 prompt

    try:  # 捕获大模型调用过程中的异常
        report_content = call_llm_with_logging(  # 调用带日志记录的大模型函数生成报告草稿
            task_id=task_id,  # 传入任务 ID，用来写入 llm_calls.task_id
            step_id=step_id,  # 传入步骤 ID，用来写入 llm_calls.step_id
            prompt=prompt,  # 传入报告生成 prompt
            model_name="default",  # 使用默认模型名称
            prompt_name="generate_report_draft_prompt",  # 保存 prompt 名称，方便后续分析效果
            prompt_version="v1",  # 保存 prompt 版本，方便后续做 prompt 迭代
        )  # 大模型调用结束

        answer = (  # 构造返回给用户看的确认提示
            "已根据知识库生成报告草稿，请确认是否保存并导出 Markdown。\n\n"  # 提示用户需要确认
            f"# {report_title}\n\n"  # 添加报告标题
            f"{report_content}"  # 添加报告正文
        )  # answer 构造结束

        new_steps = old_steps + [  # 构造新的步骤列表
            "调用大模型生成报告草稿"  # 追加报告草稿生成步骤
        ]  # 新步骤列表构造结束

        update_agent_step_result(  # 把生成报告草稿步骤从 running 更新为 success
            step_id=step_id,  # 传入当前报告草稿步骤 ID
            status="success",  # 标记步骤成功
            output_data={  # 保存报告草稿输出摘要
                "report_title": report_title,  # 保存报告标题
                "report_content_preview": report_content[:300],  # 保存报告正文前 300 字
                "report_content_length": len(report_content),  # 保存报告正文长度
            },  # 输出数据结束
            error=None,  # 成功时错误为空
        )  # 报告草稿步骤状态更新结束

        return {  # 返回成功状态
            "answer": answer,  # 把确认提示和报告草稿写入 answer
            "report_title": report_title,  # 把报告标题写入 State
            "report_content": report_content,  # 把报告草稿正文写入 State
            "step_id": step_id,  # 把当前步骤 ID 写回 State
            "steps": new_steps,  # 把新的步骤列表写回 State
            "error": None,  # 成功时清空错误信息
        }  # 成功状态返回结束

    except Exception as exc:  # 捕获生成报告草稿时出现的异常
        error_message = str(exc)  # 把异常对象转换成字符串

        failed_steps = old_steps + [  # 构造失败步骤列表
            f"生成报告草稿失败：{error_message}"  # 追加失败原因
        ]  # 失败步骤列表构造结束

        update_agent_step_result(  # 把生成报告草稿步骤从 running 更新为 failed
            step_id=step_id,  # 传入当前报告草稿步骤 ID
            status="failed",  # 标记步骤失败
            output_data={},  # 生成失败时输出为空
            error=error_message,  # 保存失败原因
        )  # 报告草稿步骤状态更新结束

        return {  # 返回失败状态
            "answer": f"生成报告草稿失败：{error_message}",  # 返回失败提示
            "report_title": report_title,  # 返回报告标题
            "report_content": "",  # 生成失败时报告正文为空
            "step_id": step_id,  # 返回当前步骤 ID
            "steps": failed_steps,  # 把失败步骤写回 State
            "error": error_message,  # 把错误信息写入 State
        }  # 失败状态返回结束


def create_approval_task_node(  # 定义创建等待确认任务节点
    state: AgentState,  # 接收当前 AgentState
) -> AgentState:  # 返回要更新到 AgentState 的字段
    user_input = state.get("user_input", "")  # 从 State 中取出用户原始输入

    knowledge_base_id = state.get("knowledge_base_id")  # 从 State 中取出知识库 ID

    session_id = state.get("session_id")  # 从 State 中取出会话 ID

    context = state.get("context", "")  # 从 State 中取出知识库检索上下文

    citations = state.get("citations", [])  # 从 State 中取出知识库引用来源列表

    report_title = state.get("report_title") or "知识库学习报告"

    report_content = state.get(  # 从 State 中读取报告草稿正文
        "report_content",  # 读取 report_content 字段
        "",  # 如果没有报告正文，就使用空字符串
    )  # 报告草稿读取结束

    old_steps = state.get(  # 从 State 中取出已有执行步骤
        "steps",  # 读取 steps 字段
        [],  # 如果没有 steps，就使用空列表
    )  # 旧步骤列表读取结束

    if not context:  # 判断是否没有检索到知识库上下文
        error_message = "创建等待确认任务失败：缺少知识库检索上下文"  # 定义错误信息

        new_steps = old_steps + [error_message]  # 把错误信息追加到步骤列表

        return {  # 返回失败状态
            "answer": error_message,  # 把错误信息作为最终回答
            "task_status": "failed",  # 当前任务状态设置为 failed
            "steps": new_steps,  # 返回更新后的步骤列表
            "error": error_message,  # 把错误信息写入 State
        }  # 失败状态返回结束

    if not report_content:  # 判断是否没有报告草稿
        error_message = "创建等待确认任务失败：缺少报告草稿内容"  # 定义错误信息

        new_steps = old_steps + [error_message]  # 把错误信息追加到步骤列表

        return {  # 返回失败状态
            "answer": error_message,  # 把错误信息作为最终回答
            "task_status": "failed",  # 当前任务状态设置为 failed
            "steps": new_steps,  # 返回更新后的步骤列表
            "error": error_message,  # 把错误信息写入 State
        }  # 失败状态返回结束

    current_task_id = state.get("task_id")  # 从 State 中读取当前已经存在的 AgentTask ID

    if current_task_id is None:  # 判断当前 State 中是否没有任务 ID
        task = create_agent_task(  # 如果没有任务 ID，就创建新的 AgentTask
            task_type="report",  # 设置任务类型为 report
            user_input=user_input,  # 保存用户原始输入
            status="waiting_approval",  # 设置任务状态为等待用户确认
            knowledge_base_id=knowledge_base_id,  # 保存知识库 ID
            session_id=session_id,  # 保存会话 ID
            context=context,  # 保存知识库检索上下文
            citations=citations,  # 保存引用来源列表
        )  # AgentTask 创建结束

        task_id = task.id  # 取出新创建的任务 ID

    else:  # 如果 State 中已经有任务 ID
        task_id = current_task_id  # 直接复用 /agent/chat 入口创建的 AgentTask ID

    task_status = "waiting_approval"  # 统一把当前任务状态设置为 waiting_approval

    if task_id is not None:  # 判断任务 ID 是否存在
        update_agent_task_status(  # 更新数据库里的 AgentTask 状态
            task_id=task_id,  # 传入当前任务 ID
            status=task_status,  # 把数据库状态更新为 waiting_approval
        )  # 数据库状态更新结束

    created_step = create_agent_step(  # 创建任务步骤记录：等待用户确认
        task_id=task_id,  # 关联当前 AgentTask ID
        step_name="wait_for_report_approval",  # 设置步骤名称为等待报告确认
        step_type="approval",  # 设置步骤类型为人工确认
        status="waiting_approval",  # 设置步骤状态为等待确认
        input_data={  # 保存这一步的输入数据
            "user_input": user_input,  # 保存用户原始输入
            "knowledge_base_id": knowledge_base_id,  # 保存知识库 ID
            "session_id": session_id,  # 保存会话 ID
        },  # 输入数据结束
        output_data={  # 保存这一步的输出数据，后面确认接口要从这里读取报告草稿
            "task_id": task_id,  # 保存任务 ID
            "task_status": task_status,  # 保存任务状态
            "report_title": report_title,  # 保存报告标题
            "report_content": report_content,  # 保存报告草稿正文
            "knowledge_base_id": knowledge_base_id,  # 保存知识库 ID
            "context": context,  # 保存知识库上下文
            "citations": citations,  # 保存引用来源
            "message": "报告草稿已生成，等待用户确认是否保存并导出 Markdown。",  # 保存确认提示
        },
    )  # 任务步骤记录创建结束

    answer = (  # 构造返回给用户的确认提示
        "我已经根据知识库生成了报告草稿。\n\n"  # 告诉用户报告草稿已生成
        f"任务 ID：{task_id}\n"  # 返回任务 ID
        "当前状态：waiting_approval\n\n"  # 返回当前任务状态
        "请确认是否保存报告并导出 Markdown。\n\n"  # 提示用户确认
        f"# {report_title}\n\n"  # 展示报告标题
        f"{report_content}"  # 展示报告草稿正文
    )  # 确认提示构造结束

    new_steps = old_steps + [  # 构造新的步骤列表
        "创建报告草稿等待确认任务"  # 追加当前节点执行记录
    ]  # 新步骤列表构造结束

    return {  # 返回要更新到 AgentState 的字段
        "answer": answer,  # 把确认提示写入 answer
        "task_id": task_id,  # 把任务 ID 写入 State
        "step_id": (
            created_step.id if created_step else state.get("step_id")
        ),  # 把等待确认步骤 ID 写入 State
        "task_status": task_status,  # 把任务状态写回 State
        "report_title": report_title,  # 把报告标题写回 State
        "report_content": report_content,  # 把报告草稿写回 State
        "steps": new_steps,  # 返回更新后的步骤列表
        "error": None,  # 成功时清空错误
    }


def generate_report_node(state: AgentState) -> AgentState:  # 定义报告生成节点，接收当前 AgentState，返回要更新的状态字段
    user_input = state.get("user_input", "")  # 从 State 中取出用户原始输入，也就是用户要求生成报告的需求
    context = state.get("context", "")  # 从 State 中取出知识库检索上下文，作为报告参考材料
    citations = state.get("citations", [])  # 从 State 中取出知识库引用来源，用来保存到报告来源信息里
    knowledge_base_id = state.get("knowledge_base_id")  # 从 State 中取出知识库 ID，方便保存报告来源
    old_steps = state.get("steps", [])  # 从 State 中取出已有执行步骤，如果没有就使用空列表
    task_id = state.get("task_id")  # 从 State 中读取当前 AgentTask ID，用来绑定报告流程里的 tool_calls

    step_id = state.get("step_id")  # 先从 State 中读取旧 step_id，作为兜底值

    created_step = None  # 初始化 created_step，避免没有 task_id 时变量不存在

    if task_id is not None:  # 判断当前 State 中是否有任务 ID
        created_step = create_agent_step(  # 创建报告生成工作流步骤记录
            task_id=task_id,  # 关联当前 AgentTask
            step_name="generate_report_workflow",  # 设置步骤名称为 generate_report_workflow
            step_type="tool",  # 设置步骤类型为 tool，因为这里会连续调用多个工具
            status="running",  # 设置步骤状态为 running
            input_data={  # 保存当前步骤输入数据
                "user_input": user_input,  # 保存用户原始需求
                "knowledge_base_id": knowledge_base_id,  # 保存知识库 ID
                "context_preview": context[:300],  # 保存上下文前 300 个字符，避免数据太长
            },  # 输入数据结束
            output_data={},  # 初始化输出数据为空
        )  # AgentStep 创建结束

        step_id = created_step.id  # 使用新创建的 AgentStep ID 作为当前步骤 ID
    if not context:  # 判断是否没有检索到参考材料
        error_message = "生成报告失败：缺少知识库检索上下文"  # 定义错误信息，说明为什么不能生成报告
        new_steps = old_steps + [error_message]  # 把错误步骤追加到执行步骤列表

        return {  # 返回要更新到 AgentState 的失败字段
            "answer": error_message,  # 把错误信息作为最终回答返回给用户
            "report_title": "",  # 报告标题为空，因为报告没有生成成功
            "report_content": "",  # 报告正文为空，因为报告没有生成成功
            "report_id": None,  # 报告 ID 为空，因为没有保存报告
            "markdown_file_path": None,  # Markdown 文件路径为空，因为没有导出文件
            "steps": new_steps,  # 返回更新后的执行步骤
            "error": error_message,  # 把错误信息写入 State
        }  # 失败状态返回结束

    report_title = state.get("report_title") or "知识库学习报告"

    generate_result = call_tool_with_logging(  # 调用带日志记录的工具执行函数
        task_id=task_id,  # 从 State 中取出任务 ID，用来关联当前 AgentTask
        step_id=step_id,  # 从 State 中取出步骤 ID，用来关联当前 AgentStep；没有时可以为 None
        tool_name="generate_report",  # 指定要调用的工具名称为 generate_report
        tool_input={  # 构造 generate_report 工具输入参数
            "title": report_title,  # 传入报告标题
            "user_input": user_input,  # 传入用户原始需求
            "source_content": context,  # 传入知识库检索上下文，作为报告参考材料
            "report_type": "study_report",  # 设置报告类型为学习报告
        },  # 工具输入参数构造结束
    )  # generate_report 工具调用结束，并自动写入 tool_calls 日志

    if not generate_result.get("success"):  # 判断生成报告工具是否执行失败
        error_message = generate_result.get("error", "生成报告工具执行失败")  # 取出工具错误信息，如果没有就使用默认错误
        new_steps = old_steps + [f"生成报告失败：{error_message}"]  # 把失败步骤追加到执行步骤列表

        return {  # 返回要更新到 AgentState 的失败字段
            "answer": f"生成报告失败：{error_message}",  # 把失败原因作为最终回答
            "report_title": report_title,  # 返回报告标题
            "report_content": "",  # 报告正文为空
            "report_id": None,  # 报告 ID 为空
            "markdown_file_path": None,  # 文件路径为空
            "steps": new_steps,  # 返回更新后的步骤
            "error": error_message,  # 把错误写入 State
        }  # 失败状态返回结束

    generate_data = generate_result.get("data", {})  # 从生成报告工具结果中取出 data 字典
    report_title = generate_data.get("title", report_title)  # 从 data 中取出报告标题，如果没有就继续使用默认标题
    report_content = generate_data.get("report_content", "")  # 从 data 中取出完整报告正文
    report_type = generate_data.get("report_type", "study_report")  # 从 data 中取出报告类型，如果没有就默认 study_report

    save_result = call_tool_with_logging(  # 调用带日志记录的工具执行函数
        task_id=task_id,  # 从 State 中取出任务 ID，用来关联当前 AgentTask
        step_id=step_id,  # 从 State 中取出步骤 ID，用来关联当前 AgentStep
        tool_name="save_report",  # 指定要调用的工具名称为 save_report
        tool_input={  # 构造 save_report 工具输入参数
            "title": report_title,  # 传入报告标题
            "report_content": report_content,  # 传入报告正文
            "report_type": report_type,  # 传入报告类型
            "source_type": "knowledge_base",  # 设置报告来源类型为知识库
            "source_metadata": {  # 构造报告来源补充信息
                "knowledge_base_id": knowledge_base_id,  # 保存知识库 ID
                "citations": citations,  # 保存引用来源列表
            },  # 来源补充信息结束
        },  # 工具输入参数构造结束
    )  # save_report 工具调用结束，并自动写入 tool_calls 日志

    if not save_result.get("success"):  # 判断保存报告工具是否执行失败
        error_message = save_result.get("error", "保存报告工具执行失败")  # 取出保存失败原因
        new_steps = old_steps + ["生成报告内容", f"保存报告失败：{error_message}"]  # 更新步骤列表

        return {  # 返回要更新到 AgentState 的失败字段
            "answer": report_content,  # 虽然保存失败，但报告正文已经生成，所以仍然返回报告内容
            "report_title": report_title,  # 返回报告标题
            "report_content": report_content,  # 返回报告正文
            "report_id": None,  # 保存失败，所以报告 ID 为空
            "markdown_file_path": None,  # 没有报告 ID，所以没有导出文件
            "steps": new_steps,  # 返回更新后的步骤
            "error": error_message,  # 把错误信息写入 State
        }  # 失败状态返回结束

    save_data = save_result.get("data", {})  # 从保存报告工具结果中取出 data 字典
    report_id = save_data.get("report_id")  # 从 data 中取出数据库生成的 report_id

    export_result = call_tool_with_logging(  # 调用带日志记录的工具执行函数
        task_id=task_id,  # 从 State 中取出任务 ID，用来关联当前 AgentTask
        step_id=step_id,  # 从 State 中取出步骤 ID，用来关联当前 AgentStep
        tool_name="export_markdown",  # 指定要调用的工具名称为 export_markdown
        tool_input={  # 构造 export_markdown 工具输入参数
            "report_id": report_id,  # 传入已经保存成功的报告 ID
        },  # 工具输入参数构造结束
    )  # export_markdown 工具调用结束，并自动写入 tool_calls 日志

    if not export_result.get("success"):  # 判断导出 Markdown 工具是否执行失败
        error_message = export_result.get("error", "导出 Markdown 工具执行失败")  # 取出导出失败原因
        new_steps = old_steps + ["生成报告内容", "保存报告到数据库", f"导出 Markdown 失败：{error_message}"]  # 更新步骤列表

        return {  # 返回要更新到 AgentState 的失败字段
            "answer": report_content,  # 导出失败时仍然返回报告正文
            "report_title": report_title,  # 返回报告标题
            "report_content": report_content,  # 返回报告正文
            "report_id": report_id,  # 返回已经保存成功的报告 ID
            "markdown_file_path": None,  # 导出失败，所以文件路径为空
            "steps": new_steps,  # 返回更新后的步骤
            "error": error_message,  # 把错误信息写入 State
        }  # 失败状态返回结束

    export_data = export_result.get("data", {})  # 从导出 Markdown 工具结果中取出 data 字典
    markdown_file_path = export_data.get("file_path")  # 从 data 中取出 Markdown 文件路径

    final_answer = (  # 构造最终返回给用户的回答内容
        f"{report_content}\n\n"  # 先放完整报告正文
        f"---\n"  # 添加 Markdown 分隔线
        f"报告已保存，report_id：{report_id}\n"  # 告诉用户报告已经保存，并返回 report_id
        f"Markdown 文件路径：{markdown_file_path}"  # 告诉用户 Markdown 文件导出路径
    )  # 最终回答构造结束

    new_steps = old_steps + [  # 构造最终成功的执行步骤列表
        "生成报告内容",  # 记录已经生成报告
        "保存报告到数据库",  # 记录已经保存报告
        "导出 Markdown 文件",  # 记录已经导出 Markdown
    ]  # 执行步骤列表结束

    return {  # 返回要更新到 AgentState 的成功字段
        "answer": final_answer,  # 把最终回答写入 State，接口会把它返回给用户
        "report_title": report_title,  # 把报告标题写入 State
        "report_content": report_content,  # 把报告正文写入 State
        "report_id": report_id,  # 把报告 ID 写入 State
        "markdown_file_path": markdown_file_path,  # 把 Markdown 文件路径写入 State
        "step_id": step_id,  # 把当前报告工作流步骤 ID 写回 State
        "steps": new_steps,  # 把执行步骤写入 State
        "error": None,  # 报告流程成功时清空错误信息
    }  # 成功状态返回结束

def generate_answer_node(  # 定义生成回答节点
    state: AgentState,  # 接收当前 AgentState
) -> AgentState:  # 返回要更新到 AgentState 的字段
    user_input = state.get(  # 从 State 中读取用户输入
        "user_input",  # 读取 user_input 字段
        "",  # 如果没有用户输入，就使用空字符串
    )  # 用户输入读取结束

    task_type = state.get(  # 从 State 中读取任务类型
        "task_type",  # 读取 task_type 字段
        "normal_chat",  # 如果没有任务类型，就默认普通聊天
    )  # 任务类型读取结束

    context = state.get(  # 从 State 中读取 RAG 上下文
        "context",  # 读取 context 字段
        "",  # 如果没有上下文，就使用空字符串
    )  # 上下文读取结束

    old_steps = state.get(  # 从 State 中读取已有步骤列表
        "steps",  # 读取 steps 字段
        [],  # 如果没有 steps，就使用空列表
    )  # 旧步骤列表读取结束
    task_id = state.get("task_id")  # 从 State 中读取当前 AgentTask ID，用来绑定 llm_calls

    step_id = state.get("step_id")  # 先从 State 中读取旧 step_id，作为兜底值

    created_step = None  # 初始化 created_step，避免没有 task_id 时变量不存在

    if task_id is not None:  # 判断当前 State 中是否有任务 ID
        created_step = create_agent_step(  # 创建生成回答步骤记录
            task_id=task_id,  # 关联当前 AgentTask
            step_name="generate_answer",  # 设置步骤名称为 generate_answer
            step_type="llm",  # 设置步骤类型为 llm，因为这个节点会调用大模型
            status="running",  # 设置步骤状态为 running
            input_data={  # 保存当前步骤输入数据
                "task_type": task_type,  # 保存任务类型
                "user_input": user_input,  # 保存用户问题
                "context": context,  # 保存 RAG 上下文，普通聊天时可能为空
            },  # 输入数据结束
            output_data={},  # 初始化输出数据为空
        )  # AgentStep 创建结束

        step_id = created_step.id  # 使用新创建的 AgentStep ID 作为当前步骤 ID
    try:  # 尝试调用大模型生成回答
        answer = generate_agent_answer(  # 调用统一的 Agent 回答生成函数
            task_type=task_type,  # 把当前任务类型传给回答生成函数
            user_input=user_input,  # 把用户问题传给回答生成函数
            context=context,  # 把知识库上下文传给回答生成函数
            task_id=task_id,  # 把当前任务 ID 传给回答生成函数，用来写 llm_calls
            step_id=step_id,  # 把当前步骤 ID 传给回答生成函数，用来写 llm_calls
        )  # 回答生成函数调用结束

        new_steps = old_steps + ["生成最终回答"]  # 在 steps 中追加生成回答的执行记录

        update_agent_step_result(  # 把生成最终回答步骤从 running 更新为 success
            step_id=step_id,  # 传入当前生成回答步骤 ID
            status="success",  # 标记步骤成功
            output_data={  # 保存回答输出摘要
                "answer_preview": answer[:300],  # 保存回答前 300 字
                "answer_length": len(answer),  # 保存回答长度
            },  # 输出数据结束
            error=None,  # 成功时错误为空
        )  # 生成回答步骤状态更新结束

        return {  # 返回要更新到 AgentState 的字段
            "answer": answer,  # 把最终回答写回 State
            "step_id": step_id,  # 把当前步骤 ID 写回 State
            "steps": new_steps,  # 把新的执行步骤列表写回 State
            "error": None,  # 生成成功时清空错误信息
        }  # 成功状态返回结束

    except Exception as exc:  # 捕获生成回答时出现的异常
        error_message = str(exc)  # 把异常对象转换成字符串

        failed_steps = old_steps + [  # 构造失败步骤列表
            f"生成最终回答失败：{error_message}"  # 追加失败原因
        ]  # 失败步骤列表构造结束

        update_agent_step_result(  # 把生成最终回答步骤从 running 更新为 failed
            step_id=step_id,  # 传入当前生成回答步骤 ID
            status="failed",  # 标记步骤失败
            output_data={},  # 生成失败时输出为空
            error=error_message,  # 保存失败原因
        )  # 生成回答步骤状态更新结束

        return {  # 返回失败状态字段
            "answer": "",  # 生成失败时回答为空
            "steps": failed_steps,  # 把失败步骤写回 State
            "error": error_message,  # 把错误信息写回 State
        }  # 失败状态返回结束


def save_result_node(
    state: AgentState,
) -> AgentState:  # 定义保存结果节点，接收当前 AgentState，返回更新后的状态字段
    user_input = state.get("user_input", "")  # 从 State 中取出用户输入的问题
    task_type = state.get(
        "task_type", "unknown"
    )  # 从 State 中取出任务类型，如果没有就使用 unknown
    answer = state.get("answer", "")  # 从 State 中取出最终回答
    context = state.get("context", "")  # 从 State 中取出知识库检索上下文
    citations = state.get("citations", [])  # 从 State 中取出引用来源列表
    steps = state.get("steps", [])  # 从 State 中取出已有执行步骤列表
    session_id = state.get("session_id")  # 从 State 中取出会话 ID
    knowledge_base_id = state.get("knowledge_base_id")  # 从 State 中取出知识库 ID
    error = state.get("error")  # 从 State 中取出错误信息

    status = (
        "failed" if error else "success"
    )  # 如果有错误信息，就标记 failed，否则标记 success
    new_steps = steps + ["保存 Agent 执行结果"]  # 在步骤列表中追加保存结果步骤

    try:  # 尝试执行数据库保存逻辑
        agent_run = save_agent_run_to_db(  # 调用保存函数，把 Agent 执行记录写入数据库
            task_id=state.get(
                "task_id"
            ),  # 传入 AgentTask ID，让 AgentRun 可以关联到任务调用链
            user_input=user_input,  # 传入用户输入
            task_type=task_type,  # 传入任务类型
            answer=answer,  # 传入最终回答
            context=context,  # 传入检索上下文
            citations=citations,  # 传入引用来源
            steps=new_steps,  # 传入包含保存步骤的新步骤列表
            session_id=session_id,  # 传入会话 ID
            knowledge_base_id=knowledge_base_id,  # 传入知识库 ID
            status=status,  # 传入执行状态
            error=error,  # 传入错误信息
        )  # 数据库保存调用结束

        return {  # 返回要更新到 AgentState 的字段
            "saved_result_id": agent_run.id,  # 把数据库生成的 AgentRun ID 写回 State
            "task_status": state.get(
                "task_status"
            ),  # 保留任务状态，例如 waiting_approval
            "steps": new_steps,  # 把新的步骤列表写回 State
        }  # 成功返回结束

    except Exception as exc:  # 捕获保存数据库时出现的异常，避免整个 Agent 流程直接崩掉
        failed_steps = steps + [
            f"保存 Agent 执行结果失败：{str(exc)}"
        ]  # 把保存失败原因记录到步骤列表

        return {  # 返回失败状态字段
            "saved_result_id": None,  # 保存失败时没有数据库记录 ID
            "steps": failed_steps,  # 把失败步骤写回 State
            "error": str(exc),  # 把异常信息写回 State
        }  # 失败返回结束
