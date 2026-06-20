import sys  # 导入 sys 模块，用来修改 Python 的模块搜索路径
from pathlib import Path  # 导入 Path，用来处理项目路径

BASE_DIR = Path(__file__).resolve().parents[1]  # 获取当前脚本所在项目的根目录
sys.path.append(
    str(BASE_DIR)
)  # 把项目根目录加入 Python 模块搜索路径，避免找不到 services 包


from services.agent_graph import agent_graph  # 导入已经编译好的 LangGraph 工作流对象


def main():  # 定义脚本入口函数
    input_state = {
        "user_input": "请根据知识库总结 Redis 的作用"
    }  # 准备输入状态，只传入用户问题

    result = agent_graph.invoke(
        input_state
    )  # 执行 LangGraph 工作流，并拿到最终状态结果

    print("用户输入：", result.get("user_input"))  # 打印用户原始输入
    print("任务类型：", result.get("task_type"))  # 打印 Agent 判断出来的任务类型
    print("检索上下文：", result.get("context"))  # 打印模拟出来的知识库上下文
    print("最终回答：", result.get("answer"))  # 打印最终生成的回答


if __name__ == "__main__":  # 判断当前文件是否是被直接运行
    main()  # 如果是直接运行，就调用 main 函数
