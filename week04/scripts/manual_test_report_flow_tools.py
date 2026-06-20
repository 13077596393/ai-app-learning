import sys  # 导入 sys 模块，用来修改 Python 模块搜索路径
from pathlib import Path  # 导入 Path，用来处理文件路径

BASE_DIR = Path(__file__).resolve().parents[1]  # 获取项目根目录，也就是 week03 目录
sys.path.append(
    str(BASE_DIR)
)  # 把项目根目录加入 Python 搜索路径，避免找不到 services、models、database 等模块


from services.agent_tools import (
    execute_agent_tool,
)  # 导入统一工具执行函数，用来通过工具名调用不同工具


def main():  # 定义测试脚本主函数
    generate_result = execute_agent_tool(  # 第一步：调用 generate_report 工具生成报告
        "generate_report",  # 指定工具名称为 generate_report
        {  # 构造 generate_report 工具输入
            "title": "Redis 学习报告",  # 设置报告标题
            "user_input": "请根据知识库生成一份 Redis 学习报告",  # 设置用户原始需求
            "source_content": "Redis 是一个基于内存的键值数据库，常用于缓存、会话存储和任务队列。",  # 设置报告参考材料
            "report_type": "study_report",  # 设置报告类型
        },  # generate_report 工具输入结束
    )  # generate_report 工具调用结束

    print("\n第一步：生成报告结果")  # 打印第一步标题
    print(generate_result)  # 打印生成报告工具的完整返回结果

    if not generate_result.get("success"):  # 判断生成报告是否失败
        print("生成报告失败，停止后续测试")  # 打印失败提示
        return  # 直接结束 main 函数，不再继续保存和导出

    report_data = generate_result.get("data", {})  # 从生成报告结果中取出 data 字典
    report_title = report_data.get("title", "")  # 从 data 中取出报告标题
    report_content = report_data.get("report_content", "")  # 从 data 中取出报告正文
    report_type = report_data.get(
        "report_type", "study_report"
    )  # 从 data 中取出报告类型

    save_result = execute_agent_tool(  # 第二步：调用 save_report 工具保存报告
        "save_report",  # 指定工具名称为 save_report
        {  # 构造 save_report 工具输入
            "title": report_title,  # 把生成报告返回的标题传给保存工具
            "report_content": report_content,  # 把生成报告返回的正文传给保存工具
            "report_type": report_type,  # 把生成报告返回的类型传给保存工具
            "source_type": "manual_test",  # 设置报告来源类型为手动测试
            "source_metadata": {  # 设置报告来源补充信息
                "test_script": "scripts/test_report_flow_tools.py",  # 记录本次报告来自哪个测试脚本
            },  # source_metadata 字典结束
        },  # save_report 工具输入结束
    )  # save_report 工具调用结束

    print("\n第二步：保存报告结果")  # 打印第二步标题
    print(save_result)  # 打印保存报告工具的完整返回结果

    if not save_result.get("success"):  # 判断保存报告是否失败
        print("保存报告失败，停止后续测试")  # 打印失败提示
        return  # 直接结束 main 函数，不再继续导出

    saved_data = save_result.get("data", {})  # 从保存报告结果中取出 data 字典
    report_id = saved_data.get("report_id")  # 从 data 中取出数据库生成的报告 ID

    export_result = (
        execute_agent_tool(  # 第三步：调用 export_markdown 工具导出 Markdown 文件
            "export_markdown",  # 指定工具名称为 export_markdown
            {  # 构造 export_markdown 工具输入
                "report_id": report_id,  # 把保存报告得到的 report_id 传给导出工具
            },  # export_markdown 工具输入结束
        )
    )  # export_markdown 工具调用结束

    print("\n第三步：导出 Markdown 结果")  # 打印第三步标题
    print(export_result)  # 打印导出 Markdown 工具的完整返回结果

    if export_result.get("success"):  # 判断导出是否成功
        file_path = export_result.get("data", {}).get(
            "file_path"
        )  # 从导出结果中取出文件路径
        print("\nMarkdown 文件路径：", file_path)  # 打印 Markdown 文件路径
    else:  # 如果导出失败
        print("导出 Markdown 失败")  # 打印失败提示


if __name__ == "__main__":  # 判断当前脚本是否是直接运行
    main()  # 如果是直接运行，就执行 main 函数
