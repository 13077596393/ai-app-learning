# 这里是LangGraph的Graph，由 State、Node、Edge 组成的完整工作流，add_node就是告诉LangGraph有什么节点
# 然后add_edge告诉LangGraph的执行节点流程路线
# add_node：告诉图“有哪些步骤”
# add_edge：告诉图“步骤之间怎么走”
# compile：把图准备好
# invoke：真正开始执行

from langgraph.graph import (  # 从 LangGraph 中导入图相关对象
    END,  # 导入 END，表示工作流结束节点
    START,  # 导入 START，表示工作流开始节点
    StateGraph,  # 导入 StateGraph，用来构建状态图
)  # LangGraph 导入结束

from schemas import AgentState  # 导入 AgentState，作为整张图共享的状态结构

from services.agent_nodes import classify_task_node  # 导入任务分类节点

from services.agent_nodes import create_approval_task_node  # 导入创建等待确认任务节点

from services.agent_nodes import generate_answer_node  # 导入普通回答生成节点

from services.agent_nodes import generate_report_draft_node  # 导入生成报告草稿节点

from services.agent_nodes import (
    generate_report_node,
)  # 导入报告生成节点，后面确认接口可以复用

from services.agent_nodes import retrieve_knowledge_node  # 导入知识库检索节点

from services.agent_nodes import save_result_node  # 导入保存 Agent 执行结果节点


def route_by_task_type(  # 定义条件路由函数
    state: AgentState,  # 接收当前 AgentState
) -> str:  # 返回下一条路线名称
    task_type = state.get(  # 从 State 中读取任务类型
        "task_type",  # 读取 task_type 字段
        "normal_chat",  # 如果没有任务类型，就默认 normal_chat
    )  # 任务类型读取结束

    if task_type == "report":  # 判断任务类型是否是报告生成任务
        return "need_report_approval"  # 返回报告任务路线，后面会进入检索、生成草稿、等待确认

    if task_type == "rag_chat":  # 判断任务类型是否是知识库问答
        return "need_retrieval"  # 返回知识库检索路线

    return "direct_answer"  # 其他情况直接进入普通回答路线


def build_agent_graph():  # 定义构建 Agent 工作流图的函数
    graph_builder = StateGraph(  # 创建 LangGraph 状态图构建器
        AgentState  # 指定状态结构为 AgentState
    )  # 状态图构建器创建结束

    graph_builder.add_node(  # 注册任务分类节点
        "classify_task",  # 设置节点名称为 classify_task
        classify_task_node,  # 绑定任务分类函数
    )  # 任务分类节点注册结束

    graph_builder.add_node(  # 注册普通知识库检索节点
        "retrieve_knowledge",  # 设置节点名称为 retrieve_knowledge
        retrieve_knowledge_node,  # 绑定知识库检索函数
    )  # 普通知识库检索节点注册结束

    graph_builder.add_node(  # 注册报告专用知识库检索节点
        "retrieve_report_knowledge",  # 设置节点名称为 retrieve_report_knowledge
        retrieve_knowledge_node,  # 复用知识库检索函数
    )  # 报告知识库检索节点注册结束

    graph_builder.add_node(  # 注册生成报告草稿节点
        "generate_report_draft",  # 设置节点名称为 generate_report_draft
        generate_report_draft_node,  # 绑定生成报告草稿函数
    )  # 生成报告草稿节点注册结束

    graph_builder.add_node(  # 注册创建等待确认任务节点
        "create_approval_task",  # 设置节点名称为 create_approval_task
        create_approval_task_node,  # 绑定创建等待确认任务函数
    )  # 创建等待确认任务节点注册结束

    graph_builder.add_node(  # 注册普通回答生成节点
        "generate_answer",  # 设置节点名称为 generate_answer
        generate_answer_node,  # 绑定普通回答生成函数
    )  # 普通回答生成节点注册结束

    graph_builder.add_node(  # 注册正式报告生成节点
        "generate_report",  # 设置节点名称为 generate_report
        generate_report_node,  # 绑定正式报告生成函数，后面确认接口可复用
    )  # 正式报告生成节点注册结束

    graph_builder.add_node(  # 注册保存 AgentRun 节点
        "save_result",  # 设置节点名称为 save_result
        save_result_node,  # 绑定保存 Agent 执行结果函数
    )  # 保存结果节点注册结束

    graph_builder.add_edge(  # 配置开始边
        START,  # 从 START 开始
        "classify_task",  # 进入 classify_task 节点
    )  # 开始边配置结束

    graph_builder.add_conditional_edges(  # 给 classify_task 添加条件路由
        "classify_task",  # classify_task 执行完成后判断下一步
        route_by_task_type,  # 使用 route_by_task_type 决定路线
        {  # 定义路由返回值和节点名称的映射
            "need_report_approval": "retrieve_report_knowledge",  # 报告任务先进入报告知识库检索节点
            "need_retrieval": "retrieve_knowledge",  # RAG 问答进入普通知识库检索节点
            "direct_answer": "generate_answer",  # 普通聊天直接进入生成回答节点
        },  # 条件路由映射结束
    )  # 条件路由配置结束

    graph_builder.add_edge(  # 配置 RAG 问答检索后的路线
        "retrieve_knowledge",  # 当前节点是普通知识库检索
        "generate_answer",  # 下一步进入生成回答节点
    )  # RAG 问答路线配置结束

    graph_builder.add_edge(  # 配置报告知识库检索后的路线
        "retrieve_report_knowledge",  # 当前节点是报告知识库检索
        "generate_report_draft",  # 下一步进入生成报告草稿节点
    )  # 报告检索到草稿生成路线配置结束

    graph_builder.add_edge(  # 配置报告草稿生成后的路线
        "generate_report_draft",  # 当前节点是生成报告草稿
        "create_approval_task",  # 下一步进入创建等待确认任务节点
    )  # 报告草稿到等待确认路线配置结束

    graph_builder.add_edge(  # 配置等待确认任务创建后的路线
        "create_approval_task",  # 当前节点是创建等待确认任务
        "save_result",  # 下一步进入保存 AgentRun 节点
    )  # 等待确认到保存结果路线配置结束

    graph_builder.add_edge(  # 配置普通回答生成后的路线
        "generate_answer",  # 当前节点是生成回答
        "save_result",  # 下一步进入保存 AgentRun 节点
    )  # 普通回答保存路线配置结束

    graph_builder.add_edge(  # 配置正式报告生成后的路线
        "generate_report",  # 当前节点是正式报告生成
        "save_result",  # 下一步进入保存 AgentRun 节点
    )  # 正式报告保存路线配置结束

    graph_builder.add_edge(  # 配置保存结果后的路线
        "save_result",  # 当前节点是保存结果
        END,  # 下一步进入 END 结束节点
    )  # 结束边配置完成

    agent_graph = graph_builder.compile()  # 编译工作流图，让它可以被 invoke 执行

    return agent_graph  # 返回编译后的 Agent 工作流对象


agent_graph = build_agent_graph()  # 创建一个全局可复用的 Agent 工作流对象
