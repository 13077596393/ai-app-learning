import sys  # 导入 sys 模块，用来修改 Python 的模块搜索路径
from pathlib import Path  # 导入 Path，用来处理项目路径

BASE_DIR = Path(__file__).resolve().parents[1]  # 获取项目根目录，也就是 week03 目录
sys.path.append(
    str(BASE_DIR)
)  # 把项目根目录加入 Python 搜索路径，避免找不到 services、models、database 等模块


from services.agent_tools import (
    execute_agent_tool,
)  # 导入统一工具执行函数，用来通过工具名调用工具


def run_case(
    case_name: str, tool_input: dict
):  # 定义单个测试用例函数，接收测试名称和工具输入
    print("\n==============================")  # 打印分隔线，方便区分不同测试用例
    print("测试用例：", case_name)  # 打印当前测试用例名称
    print("工具输入：", tool_input)  # 打印本次传给工具的输入参数

    result = execute_agent_tool(  # 通过统一工具入口调用工具
        "query_database",  # 指定工具名称为 query_database
        tool_input,  # 传入本次测试的工具输入参数
    )  # 工具执行结束，返回统一格式结果

    print("工具是否成功：", result.get("success"))  # 打印 success，查看工具是否执行成功
    print(
        "工具名称：", result.get("tool_name")
    )  # 打印 tool_name，确认调用的是 query_database
    print("工具数据：", result.get("data"))  # 打印 data，成功时这里应该有 records
    print("错误信息：", result.get("error"))  # 打印 error，失败时这里会显示失败原因


def main():  # 定义测试脚本主函数
    success_input = {  # 定义成功测试输入
        "query_type": "recent_agent_runs",  # 查询类型：查询最近 Agent 执行记录
        "limit": 5,  # 查询最近 5 条记录
    }  # 成功测试输入结束

    unsupported_query_input = {  # 定义不支持 query_type 的测试输入
        "query_type": "unknown_query",  # 故意传入一个不支持的查询类型
        "limit": 5,  # 查询数量仍然传 5
    }  # 不支持 query_type 的测试输入结束

    invalid_limit_input = {  # 定义 limit 非法的测试输入
        "query_type": "recent_agent_runs",  # 查询类型仍然是正确的
        "limit": "abc",  # 故意传入不能转成整数的 limit
    }  # limit 非法测试输入结束

    zero_limit_input = {  # 定义 limit 小于等于 0 的测试输入
        "query_type": "recent_agent_runs",  # 查询类型仍然是正确的
        "limit": 0,  # 故意传入 0，测试 limit 必须大于 0 的校验
    }  # limit 为 0 测试输入结束

    run_case("正常查询最近 Agent 执行记录", success_input)  # 执行成功查询测试
    run_case("不支持的 query_type", unsupported_query_input)  # 执行不支持查询类型测试
    run_case("limit 不是整数", invalid_limit_input)  # 执行 limit 非整数测试
    run_case("limit 小于等于 0", zero_limit_input)  # 执行 limit 小于等于 0 测试


if __name__ == "__main__":  # 判断当前脚本是否是直接运行
    main()  # 如果是直接运行，就执行 main 函数
