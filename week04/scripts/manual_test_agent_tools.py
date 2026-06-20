import sys  # 导入 sys 模块，用来修改 Python 模块搜索路径
from pathlib import Path  # 导入 Path，用来处理文件路径

BASE_DIR = (
    Path(__file__).resolve().parents[1]
)  # 获取当前脚本所在项目根目录，也就是 week03 目录
sys.path.append(
    str(BASE_DIR)
)  # 把项目根目录加入 Python 搜索路径，避免找不到 services 包


from services.agent_tools import execute_agent_tool  # 导入统一工具执行函数


def run_case(
    case_name: str, tool_input: dict
):  # 定义单个测试用例函数，接收用例名称和工具输入
    print("\n==============================")  # 打印分隔线，方便区分不同测试用例
    print("测试用例：", case_name)  # 打印当前测试用例名称
    print("工具输入：", tool_input)  # 打印当前传入工具的输入参数

    result = execute_agent_tool(  # 通过统一工具执行入口调用工具
        "search_knowledge_base",  # 传入工具名称，让注册表找到 search_knowledge_base_tool
        tool_input,  # 传入工具输入参数
    )  # 工具执行结束，拿到统一格式结果

    print("工具是否成功：", result.get("success"))  # 打印 success，查看工具是否执行成功
    print("工具名称：", result.get("tool_name"))  # 打印 tool_name，确认执行的是哪个工具
    print(
        "工具数据：", result.get("data")
    )  # 打印 data，成功时这里应该有 context 和 citations
    print("错误信息：", result.get("error"))  # 打印 error，失败时这里应该有错误原因


def main():  # 定义测试脚本主函数
    success_input = {  # 定义成功测试输入
        "question": "请根据知识库总结 Redis 的作用",  # 设置用户问题
        "knowledge_base_id": 1,  # 设置知识库 ID
        "top_k": 5,  # 设置检索数量
    }  # 成功测试输入结束

    missing_question_input = {  # 定义缺少 question 的测试输入
        "knowledge_base_id": 1,  # 只传知识库 ID
        "top_k": 5,  # 传检索数量
    }  # 缺少 question 的测试输入结束

    missing_kb_input = {  # 定义缺少 knowledge_base_id 的测试输入
        "question": "请根据知识库总结 Redis 的作用",  # 只传用户问题
        "top_k": 5,  # 传检索数量
    }  # 缺少 knowledge_base_id 的测试输入结束

    run_case("正常输入", success_input)  # 执行正常输入测试
    run_case("缺少 question", missing_question_input)  # 执行缺少 question 测试
    run_case("缺少 knowledge_base_id", missing_kb_input)  # 执行缺少知识库 ID 测试


if __name__ == "__main__":  # 判断当前文件是否是直接运行
    main()  # 如果是直接运行，就执行 main 函数
