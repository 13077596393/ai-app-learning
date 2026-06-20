# 这里其实就是定义很多工具，统一用execute_agent_tool方法去调用，比如result = execute_agent_tool(
#    "search_knowledge_base",
#    {
#        "question": "Redis 是什么？",
#        "knowledge_base_id": 1,
#        "top_k": 5,
#    },
# )调用 search_knowledge_base 这个工具
# 参数是 question、knowledge_base_id、top_k
# search_knowledge_base 对应这个工具tool_registry里面的search_knowledge_base_tool这个方法
from typing import Any  # 导入 Any，用来表示工具输入和输出里可以包含多种类型的数据
from datetime import datetime  # 导入 datetime，用来更新报告的 updated_at 时间
from pathlib import Path  # 导入 Path，用来创建文件夹和文件路径
from sqlmodel import (
    Session,
    select,
)  # 导入 Session 用来连接数据库，导入 select 用来查询数据

from database import engine  # 从 database.py 导入数据库 engine，用来创建数据库会话
from models import AgentRun, Report  # 从 models.py 导入 AgentRun 和 Report，AgentRun 用来查询历史记录，Report 用来保存报告
from services.agent_rag_service import (
    search_knowledge_base_for_agent,
)  # 导入真实的 Agent RAG 检索函数

def search_knowledge_base_tool(
    tool_input: dict[str, Any],
) -> dict[str, Any]:  # 定义搜索知识库工具，接收统一工具输入，返回统一工具结果
    question = tool_input.get(
        "question", ""
    )  # 从工具输入中取出用户问题，如果没有就使用空字符串
    knowledge_base_id = tool_input.get(
        "knowledge_base_id"
    )  # 从工具输入中取出知识库 ID，如果没有就是 None
    top_k = tool_input.get(
        "top_k", 5
    )  # 从工具输入中取出 top_k，如果没有就默认检索 5 条

    if not question:  # 判断用户问题是否为空
        return {  # 返回统一格式的失败结果
            "success": False,  # success 为 False，表示工具执行失败
            "tool_name": "search_knowledge_base",  # 返回当前工具名称
            "data": {},  # 失败时没有业务数据，所以 data 为空字典
            "error": "question 不能为空",  # 返回失败原因
        }  # 失败结果返回结束

    if knowledge_base_id is None:  # 判断知识库 ID 是否为空
        return {  # 返回统一格式的失败结果
            "success": False,  # success 为 False，表示工具执行失败
            "tool_name": "search_knowledge_base",  # 返回当前工具名称
            "data": {},  # 失败时没有业务数据，所以 data 为空字典
            "error": "knowledge_base_id 不能为空",  # 返回失败原因
        }  # 失败结果返回结束

    search_result = (
        search_knowledge_base_for_agent(  # 调用真实的 Agent RAG 检索服务函数
            knowledge_base_id=knowledge_base_id,  # 把知识库 ID 传给检索函数
            question=question,  # 把用户问题传给检索函数
            top_k=top_k,  # 把检索数量传给检索函数
        )
    )  # 真实检索函数调用结束，返回 context 和 citations

    context = search_result.get(
        "context", ""
    )  # 从检索结果中取出上下文文本，如果没有就使用空字符串
    citations = search_result.get(
        "citations", []
    )  # 从检索结果中取出引用来源，如果没有就使用空列表

    return {  # 返回统一格式的工具成功结果
        "success": True,  # success 为 True，表示工具执行成功
        "tool_name": "search_knowledge_base",  # 返回当前工具名称
        "data": {  # data 里面保存工具真正返回的数据
            "context": context,  # 返回真实检索到的上下文
            "citations": citations,  # 返回真实检索到的引用来源
        },  # data 字典结束
        "error": None,  # 成功时 error 为 None
    }  # 工具成功结果返回结束


def query_database_tool(
    tool_input: dict[str, Any],
) -> dict[str, Any]:  # 定义查询数据库工具，接收统一工具输入，返回统一工具结果
    query_type = tool_input.get(  # 从工具输入中取出查询类型
        "query_type",  # 要读取的字段名是 query_type
        "recent_agent_runs",  # 如果没有传 query_type，就默认查询最近 Agent 执行记录
    )  # query_type 读取结束

    limit = tool_input.get(  # 从工具输入中取出 limit
        "limit",  # 要读取的字段名是 limit
        5,  # 如果没有传 limit，就默认返回 5 条
    )  # limit 读取结束

    try:  # 尝试把 limit 转成整数，避免前端传字符串、None 或其他非法值导致查询报错
        limit = int(limit)  # 把 limit 转换成 int 类型
    except (TypeError, ValueError):  # 如果 limit 是 None 或不能转换成整数，就进入这里
        return {  # 返回统一格式的失败结果
            "success": False,  # success 为 False，表示工具执行失败
            "tool_name": "query_database",  # 返回当前工具名称
            "data": {},  # 失败时没有业务数据，所以 data 为空字典
            "error": "limit 必须是整数",  # 返回失败原因
        }  # 失败结果返回结束

    if limit <= 0:  # 判断 limit 是否小于等于 0
        return {  # 返回统一格式的失败结果
            "success": False,  # success 为 False，表示工具执行失败
            "tool_name": "query_database",  # 返回当前工具名称
            "data": {},  # 失败时没有业务数据
            "error": "limit 必须大于 0",  # 返回失败原因
        }  # 失败结果返回结束

    if (
        query_type != "recent_agent_runs"
    ):  # 判断当前查询类型是否不是我们支持的 recent_agent_runs
        return {  # 返回统一格式的失败结果
            "success": False,  # success 为 False，表示工具执行失败
            "tool_name": "query_database",  # 返回当前工具名称
            "data": {},  # 不支持查询类型时没有业务数据
            "error": f"不支持的 query_type：{query_type}",  # 返回不支持的查询类型
        }  # 失败结果返回结束

    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        statement = (  # 创建 SQL 查询语句
            select(AgentRun)  # 查询 AgentRun 模型，也就是 agent_runs 表
            .order_by(AgentRun.created_at.desc())  # 按创建时间倒序排列，最新的排在前面
            .limit(limit)  # 限制返回记录数量
        )  # 查询语句创建结束

        agent_runs = session.exec(statement).all()  # 执行查询语句，并获取所有查询结果

    records = []  # 创建空列表，用来保存整理后的记录

    for run in agent_runs:  # 遍历每一条 AgentRun 查询结果
        records.append(  # 往 records 列表里追加一条记录
            {  # 构造一条返回给工具调用方的记录字典
                "id": run.id,  # 保存 AgentRun 记录 ID
                "user_input": run.user_input,  # 保存用户输入
                "task_type": run.task_type,  # 保存任务类型
                "answer": run.answer,  # 保存 Agent 最终回答
                "status": run.status,  # 保存执行状态
                "created_at": run.created_at.isoformat(),  # 把创建时间转换成字符串，方便 JSON 返回
            }  # 单条记录字典结束
        )  # 追加记录结束

    return {  # 返回统一格式的工具成功结果
        "success": True,  # success 为 True，表示工具执行成功
        "tool_name": "query_database",  # 返回当前工具名称
        "data": {  # data 里面保存真正的查询结果
            "query_type": query_type,  # 返回本次查询类型
            "records": records,  # 返回整理后的 AgentRun 记录列表
        },  # data 字典结束
        "error": None,  # 成功时 error 为 None
    }  # 成功结果返回结束


def generate_report_tool(
    tool_input: dict[str, Any],
) -> dict[str, Any]:  # 定义生成报告工具，接收统一工具输入，返回统一工具结果
    title = str(
        tool_input.get("title") or ""
    ).strip()  # 从工具输入中取出报告标题，如果为空就转成空字符串并去掉首尾空格
    user_input = str(
        tool_input.get("user_input") or ""
    ).strip()  # 从工具输入中取出用户原始需求，如果为空就转成空字符串并去掉首尾空格
    source_content = str(
        tool_input.get("source_content") or ""
    ).strip()  # 从工具输入中取出参考材料，如果为空就转成空字符串并去掉首尾空格
    report_type = str(
        tool_input.get("report_type") or "study_report"
    ).strip()  # 从工具输入中取出报告类型，如果没有就默认 study_report

    if not title:  # 判断报告标题是否为空
        return {  # 返回统一格式的失败结果
            "success": False,  # success 为 False，表示工具执行失败
            "tool_name": "generate_report",  # 返回当前工具名称
            "data": {},  # 失败时没有报告数据，所以 data 为空字典
            "error": "title 不能为空",  # 返回失败原因
        }  # 标题为空的失败结果返回结束

    if not source_content:  # 判断参考材料是否为空
        return {  # 返回统一格式的失败结果
            "success": False,  # success 为 False，表示工具执行失败
            "tool_name": "generate_report",  # 返回当前工具名称
            "data": {},  # 失败时没有报告数据，所以 data 为空字典
            "error": "source_content 不能为空",  # 返回失败原因
        }  # 参考材料为空的失败结果返回结束

    if not user_input:  # 判断用户原始需求是否为空
        user_input = "用户未提供明确需求，系统将根据参考材料生成基础报告。"  # 如果用户需求为空，就给一个默认说明，避免报告内容缺失

    report_lines = [  # 创建报告文本列表，后面用换行符拼接成完整 Markdown 报告
        f"# {title}",  # 报告一级标题
        "",  # 空行，让 Markdown 排版更清晰
        "## 一、用户需求",  # 报告第一部分标题
        user_input,  # 写入用户原始需求
        "",  # 空行，让不同部分之间有间距
        "## 二、参考材料",  # 报告第二部分标题
        source_content,  # 写入报告参考材料
        "",  # 空行，让不同部分之间有间距
        "## 三、分析总结",  # 报告第三部分标题
        "根据以上参考材料可以看出，本报告主要围绕用户需求和已有资料进行整理。",  # 写入基础分析总结第一句
        "当前版本先使用固定模板生成报告，后续可以接入 LLM，让报告内容更加自然、完整和个性化。",  # 写入基础分析总结第二句
        "",  # 空行，让不同部分之间有间距
        "## 四、后续建议",  # 报告第四部分标题
        "1. 可以继续补充更多知识库资料，提高报告内容的完整度。",  # 写入第一条建议
        "2. 可以结合具体业务场景，把报告改成项目方案、学习总结或技术复盘。",  # 写入第二条建议
        "3. 后续可以把报告保存到数据库，并支持导出 Markdown 文件。",  # 写入第三条建议
    ]  # 报告文本列表结束

    report_content = "\n".join(
        report_lines
    )  # 使用换行符把列表中的每一行拼接成完整报告正文

    return {  # 返回统一格式的工具成功结果
        "success": True,  # success 为 True，表示工具执行成功
        "tool_name": "generate_report",  # 返回当前工具名称
        "data": {  # data 里面保存真正的报告生成结果
            "title": title,  # 返回报告标题
            "report_content": report_content,  # 返回完整 Markdown 报告正文
            "report_type": report_type,  # 返回报告类型
        },  # data 字典结束
        "error": None,  # 成功时 error 为 None
    }  # 工具成功结果返回结束


def save_report_tool(
    tool_input: dict[str, Any],
) -> dict[str, Any]:  # 定义保存报告工具，接收统一工具输入，返回统一工具结果
    title = str(
        tool_input.get("title") or ""
    ).strip()  # 从工具输入中取出报告标题，如果为空就转成空字符串并去掉首尾空格
    content = str(  # 把报告正文统一转换成字符串
        tool_input.get("content")  # 优先从 content 字段中读取报告正文
        or tool_input.get(
            "report_content"
        )  # 如果没有 content，就从 report_content 字段中读取报告正文
        or ""  # 如果两个字段都没有，就使用空字符串
    ).strip()  # 去掉报告正文首尾空格
    report_type = str(
        tool_input.get("report_type") or "study_report"
    ).strip()  # 从工具输入中取出报告类型，如果没有就默认 study_report
    source_type = str(
        tool_input.get("source_type") or "manual"
    ).strip()  # 从工具输入中取出报告来源类型，如果没有就默认 manual
    source_metadata = (
        tool_input.get("source_metadata") or {}
    )  # 从工具输入中取出报告来源补充信息，如果没有就使用空字典
    agent_run_id = tool_input.get(
        "agent_run_id"
    )  # 从工具输入中取出关联的 AgentRun ID，如果没有就得到 None

    if not title:  # 判断报告标题是否为空
        return {  # 返回统一格式的失败结果
            "success": False,  # success 为 False，表示工具执行失败
            "tool_name": "save_report",  # 返回当前工具名称
            "data": {},  # 失败时没有业务数据，所以 data 为空字典
            "error": "title 不能为空",  # 返回失败原因
        }  # 标题为空的失败结果返回结束

    if not content:  # 判断报告正文是否为空
        return {  # 返回统一格式的失败结果
            "success": False,  # success 为 False，表示工具执行失败
            "tool_name": "save_report",  # 返回当前工具名称
            "data": {},  # 失败时没有业务数据，所以 data 为空字典
            "error": "content 或 report_content 不能为空",  # 返回失败原因
        }  # 正文为空的失败结果返回结束

    if not isinstance(source_metadata, dict):  # 判断 source_metadata 是否不是字典
        return {  # 返回统一格式的失败结果
            "success": False,  # success 为 False，表示工具执行失败
            "tool_name": "save_report",  # 返回当前工具名称
            "data": {},  # 失败时没有业务数据，所以 data 为空字典
            "error": "source_metadata 必须是字典",  # 返回失败原因
        }  # source_metadata 类型错误的失败结果返回结束

    if agent_run_id is not None:  # 判断是否传入了 agent_run_id
        try:  # 尝试把 agent_run_id 转成整数
            agent_run_id = int(agent_run_id)  # 把 agent_run_id 转成 int 类型
        except (TypeError, ValueError):  # 如果 agent_run_id 是非法值，就进入这里
            return {  # 返回统一格式的失败结果
                "success": False,  # success 为 False，表示工具执行失败
                "tool_name": "save_report",  # 返回当前工具名称
                "data": {},  # 失败时没有业务数据，所以 data 为空字典
                "error": "agent_run_id 必须是整数",  # 返回失败原因
            }  # agent_run_id 非法的失败结果返回结束

    report = Report(  # 创建 Report 数据库对象，准备保存到 reports 表
        title=title,  # 保存报告标题
        report_type=report_type,  # 保存报告类型
        content=content,  # 保存报告正文
        source_type=source_type,  # 保存报告来源类型
        source_metadata=source_metadata,  # 保存报告来源补充信息
        agent_run_id=agent_run_id,  # 保存关联的 AgentRun ID
    )  # Report 对象创建结束

    with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
        session.add(report)  # 把 report 对象加入数据库会话，准备写入数据库
        session.commit()  # 提交数据库事务，把报告真正保存到 reports 表
        session.refresh(
            report
        )  # 刷新 report 对象，拿到数据库自动生成的 id、created_at 等字段

    return {  # 返回统一格式的工具成功结果
        "success": True,  # success 为 True，表示工具执行成功
        "tool_name": "save_report",  # 返回当前工具名称
        "data": {  # data 里面保存真正的保存结果
            "report_id": report.id,  # 返回数据库生成的报告 ID
            "title": report.title,  # 返回报告标题
            "report_type": report.report_type,  # 返回报告类型
            "source_type": report.source_type,  # 返回报告来源类型
            "agent_run_id": report.agent_run_id,  # 返回关联的 AgentRun ID
            "created_at": report.created_at.isoformat(),  # 返回报告创建时间，并转换成字符串
        },  # data 字典结束
        "error": None,  # 成功时 error 为 None
    }  # 工具成功结果返回结束

def export_markdown_tool(tool_input: dict[str, Any]) -> dict[str, Any]:  # 定义导出 Markdown 工具，接收统一工具输入，返回统一工具结果
    report_id = tool_input.get("report_id")  # 从工具输入中取出 report_id，如果没有就得到 None
    title = str(tool_input.get("title") or "").strip()  # 从工具输入中取出标题，如果没有就转成空字符串并去掉首尾空格
    content = str(  # 把报告正文统一转换成字符串
        tool_input.get("content")  # 优先从 content 字段读取报告正文
        or tool_input.get("report_content")  # 如果没有 content，就从 report_content 字段读取报告正文
        or ""  # 如果两个字段都没有，就使用空字符串
    ).strip()  # 去掉报告正文首尾空格
    export_dir = str(tool_input.get("export_dir") or "exports").strip()  # 从工具输入中取出导出目录，如果没有就默认 exports
    file_name = str(tool_input.get("file_name") or "").strip()  # 从工具输入中取出文件名，如果没有就后面自动生成

    if report_id is not None:  # 判断是否传入了 report_id
        try:  # 尝试把 report_id 转成整数
            report_id = int(report_id)  # 把 report_id 转成 int 类型
        except (TypeError, ValueError):  # 如果 report_id 不是合法整数
            return {  # 返回统一格式的失败结果
                "success": False,  # success 为 False，表示工具执行失败
                "tool_name": "export_markdown",  # 返回当前工具名称
                "data": {},  # 失败时没有业务数据
                "error": "report_id 必须是整数",  # 返回失败原因
            }  # report_id 非法的失败结果返回结束

        with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
            report = session.get(Report, report_id)  # 根据 report_id 从 reports 表中查询报告记录

            if report is None:  # 判断是否没有查询到报告
                return {  # 返回统一格式的失败结果
                    "success": False,  # success 为 False，表示工具执行失败
                    "tool_name": "export_markdown",  # 返回当前工具名称
                    "data": {},  # 没有查到报告，所以 data 为空
                    "error": f"报告不存在：report_id={report_id}",  # 返回失败原因
                }  # 报告不存在的失败结果返回结束

            title = report.title  # 如果查到了报告，就使用数据库里的报告标题
            content = report.content  # 如果查到了报告，就使用数据库里的报告正文

    if not title:  # 判断标题是否为空
        return {  # 返回统一格式的失败结果
            "success": False,  # success 为 False，表示工具执行失败
            "tool_name": "export_markdown",  # 返回当前工具名称
            "data": {},  # 标题为空时没有导出结果
            "error": "title 不能为空",  # 返回失败原因
        }  # 标题为空的失败结果返回结束

    if not content:  # 判断报告正文是否为空
        return {  # 返回统一格式的失败结果
            "success": False,  # success 为 False，表示工具执行失败
            "tool_name": "export_markdown",  # 返回当前工具名称
            "data": {},  # 正文为空时没有导出结果
            "error": "content 或 report_content 不能为空",  # 返回失败原因
        }  # 正文为空的失败结果返回结束

    export_path = Path(export_dir)  # 把导出目录字符串转换成 Path 对象，方便后面创建文件夹
    export_path.mkdir(parents=True, exist_ok=True)  # 创建导出目录，如果目录已存在就不报错

    if not file_name:  # 判断用户是否没有手动传入文件名
        safe_title = "".join(  # 生成安全文件名，把不适合出现在文件名里的符号过滤掉
            char  # 保留当前字符
            for char in title  # 遍历标题里的每一个字符
            if char not in '\\/:*?"<>|'  # 过滤 Windows 文件名不允许使用的特殊字符
        ).strip()  # 去掉过滤后标题首尾空格

        if not safe_title:  # 判断过滤后的标题是否为空
            safe_title = "report"  # 如果标题过滤后为空，就使用默认文件名 report

        if report_id is not None:  # 判断是否有 report_id
            file_name = f"report_{report_id}_{safe_title}.md"  # 如果有 report_id，就把 report_id 加到文件名里，避免重名
        else:  # 如果没有 report_id
            file_name = f"{safe_title}.md"  # 如果没有 report_id，就直接使用标题作为文件名

    if not file_name.endswith(".md"):  # 判断文件名是否没有以 .md 结尾
        file_name = f"{file_name}.md"  # 如果没有 .md 后缀，就自动补上 .md
        
    markdown_file_path = export_path / file_name  # 拼接最终 Markdown 文件路径

    markdown_file_path.write_text(  # 把报告正文写入 Markdown 文件
        content,  # 要写入文件的报告正文
        encoding="utf-8",  # 使用 utf-8 编码，避免中文乱码
    )  # 文件写入结束

    if report_id is not None:  # 判断是否是根据数据库报告 ID 导出的
        with Session(engine) as session:  # 创建数据库会话，用完后自动关闭
            report = session.get(Report, report_id)  # 重新查询报告记录，准备更新文件路径

            if report is not None:  # 判断报告记录是否存在
                report.markdown_file_path = str(markdown_file_path)  # 把 Markdown 文件路径保存到报告记录里
                report.updated_at = datetime.now()  # 更新报告的更新时间
                session.add(report)  # 把修改后的 report 对象加入数据库会话
                session.commit()  # 提交数据库事务，保存 markdown_file_path 和 updated_at

    return {  # 返回统一格式的工具成功结果
        "success": True,  # success 为 True，表示工具执行成功
        "tool_name": "export_markdown",  # 返回当前工具名称
        "data": {  # data 里面保存真正的导出结果
            "report_id": report_id,  # 返回报告 ID，如果不是从数据库导出则可能为 None
            "title": title,  # 返回报告标题
            "file_path": str(markdown_file_path),  # 返回 Markdown 文件路径
            "file_name": file_name,  # 返回 Markdown 文件名
        },  # data 字典结束
        "error": None,  # 成功时 error 为 None
    }  # 工具成功结果返回结束

tool_registry = {  # 定义工具注册表，用来保存工具名称和工具函数之间的映射关系
    "search_knowledge_base": search_knowledge_base_tool,  # 注册搜索知识库工具，工具名对应 search_knowledge_base_tool 函数
    "query_database": query_database_tool,  # 注册查询数据库工具，工具名对应 query_database_tool 函数
    "generate_report": generate_report_tool,  # 注册生成报告工具，工具名对应 generate_report_tool 函数
    "save_report": save_report_tool,  # 注册保存报告工具，工具名对应 save_report_tool 函数
    "export_markdown": export_markdown_tool,  # 注册导出 Markdown 工具，工具名对应 export_markdown_tool 函数
}  # 工具注册表定义结束

def execute_agent_tool(  # 定义统一工具执行函数，让 Agent 可以通过工具名调用工具
    tool_name: str,  # 接收工具名称，例如 search_knowledge_base
    tool_input: dict[str, Any],  # 接收工具输入参数，统一使用字典格式
) -> dict[str, Any]:  # 返回工具执行结果，统一使用字典格式
    tool_func = tool_registry.get(tool_name)  # 根据工具名称从注册表中取出对应的工具函数

    if tool_func is None:  # 判断工具函数是否不存在
        return {  # 如果工具不存在，就返回统一的失败结果
            "success": False,  # success 为 False，表示工具执行失败
            "tool_name": tool_name,  # 返回用户想调用的工具名称
            "data": {},  # 工具不存在时没有数据，所以 data 为空字典
            "error": f"工具不存在：{tool_name}",  # 返回错误信息，说明工具名称没有注册
        }  # 工具不存在的失败结果返回结束

    try:  # 尝试执行工具函数，防止工具内部报错导致整个 Agent 崩掉
        return tool_func(tool_input)  # 调用真实工具函数，并把工具执行结果返回出去
    except Exception as exc:  # 捕获工具执行过程中出现的异常
        return {  # 返回统一的工具执行失败结果
            "success": False,  # success 为 False，表示工具执行失败
            "tool_name": tool_name,  # 返回当前执行失败的工具名称
            "data": {},  # 执行失败时 data 为空字典
            "error": str(exc),  # 把异常信息转成字符串返回
        }  # 工具异常失败结果返回结束
