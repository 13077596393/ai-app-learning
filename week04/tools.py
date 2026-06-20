import ast  # 导入 Python 抽象语法树模块用于安全解析表达式
import json  # 导入 JSON 模块用于解析模型返回的工具调用结果
import operator  # 导入运算符函数模块用于执行数学运算
from openai import OpenAI  # 导入 OpenAI 兼容客户端

from settings import settings  # 导入项目配置对象
from pydantic import BaseModel, ValidationError  # 导入参数模型基类和校验异常

notes = []  # 使用内存列表临时保存笔记数据


TOOL_DECISION_SYSTEM_PROMPT = (  # 定义工具调用决策的系统提示词
    """
你是一个工具调用决策器。

你的任务：
根据用户输入，判断是否需要调用工具。

当前可用工具只有两个：

1. calculator_tool
用途：计算数学表达式。
参数：
{
  "expression": "数学表达式字符串"
}

2. save_note_tool
用途：保存用户提供的笔记内容。
参数：
{
  "content": "要保存的笔记内容"
}

输出规则：
你必须只输出 JSON。
不要输出解释。
不要输出 Markdown。
不要使用 ```json 代码块。
不要输出多余文字。

如果用户想计算数学表达式，输出：
{
  "tool_name": "calculator_tool",
  "tool_args": {
    "expression": "表达式"
  }
}

如果用户想保存笔记，输出：
{
  "tool_name": "save_note_tool",
  "tool_args": {
    "content": "笔记内容"
  }
}

如果用户不需要调用工具，输出：
{
  "tool_name": null,
  "tool_args": {}
}
"""  # 结束系统提示词文本
)  # 结束提示词变量赋值
client = OpenAI(  # 创建大模型 API 客户端
    api_key=settings.llm_api_key,  # 设置 API Key
    base_url=settings.llm_base_url,  # 设置大模型服务地址
    timeout=settings.llm_timeout,  # 设置请求超时时间
)  # 结束客户端初始化


def llm_tool_decision(user_message: str) -> dict:  # 定义让大模型判断是否需要调用工具的函数
    messages = [  # 构造发送给大模型的消息列表
        {  # 构造系统提示词消息
            "role": "system",  # 设置消息角色为 system
            "content": TOOL_DECISION_SYSTEM_PROMPT,  # 设置工具决策系统提示词
        },  # 结束系统提示词消息
        {  # 构造用户消息
            "role": "user",  # 设置消息角色为 user
            "content": user_message,  # 设置用户输入内容
        },  # 结束用户消息
    ]  # 结束消息列表

    try:  # 尝试调用大模型进行工具决策
        response = client.chat.completions.create(  # 发起聊天补全请求
            model=settings.llm_model_name,  # 指定大模型名称
            messages=messages,  # 传入工具决策上下文消息
            temperature=0,  # 使用 0 温度让工具选择更稳定
        )  # 结束聊天补全请求

        model_output = response.choices[0].message.content  # 读取模型返回的工具调用 JSON 字符串

        if model_output is None:  # 判断模型是否没有返回内容
            return {  # 返回工具决策失败结果
                "tool_name": None,  # 标记没有工具可执行
                "tool_args": {},  # 返回空工具参数
                "error": "模型没有返回工具调用结果",  # 返回错误说明
            }  # 结束错误结果字典

        tool_call = parse_tool_call_json(model_output)  # 解析模型输出为工具调用字典

        return tool_call  # 返回解析后的工具调用信息

    except Exception as e:  # 捕获工具决策调用过程中的异常
        return {  # 返回工具决策异常结果
            "tool_name": None,  # 标记没有工具可执行
            "tool_args": {},  # 返回空工具参数
            "error": f"模型工具判断失败：{e}",  # 返回异常说明
        }  # 结束异常结果字典

# 比如用户输入：帮我计算 8 / 2
# 模型看到 system 规则后，应该返回：
# {
# "tool_name": "calculator_tool",
#  "tool_args": {
#    "expression": "8 / 2"
#  }
# }
#


class CalculatorToolArgs(BaseModel):  # 定义计算器工具参数模型
    expression: str  # 声明数学表达式参数


class SaveNoteToolArgs(BaseModel):  # 定义保存笔记工具参数模型
    content: str  # 声明要保存的笔记内容参数


def calculator_tool(expression: str) -> float:  # 定义安全计算数学表达式的工具函数
    allowed_operators = {  # 定义允许执行的运算符映射
        ast.Add: operator.add,  # 允许加法运算
        ast.Sub: operator.sub,  # 允许减法运算
        ast.Mult: operator.mul,  # 允许乘法运算
        ast.Div: operator.truediv,  # 允许除法运算
    }  # 结束允许运算符映射

    def calculate_node(node):  # 定义递归计算语法树节点的内部函数
        if isinstance(node, ast.Constant):  # 判断当前节点是否为常量
            if isinstance(node.value, int | float):  # 判断常量值是否为数字
                return node.value  # 数字常量直接返回

            raise ValueError("只支持数字")  # 非数字常量抛出错误

        if isinstance(node, ast.BinOp):  # 判断当前节点是否为二元运算表达式
            left_value = calculate_node(node.left)  # 递归计算左侧表达式
            right_value = calculate_node(node.right)  # 递归计算右侧表达式

            operator_type = type(node.op)  # 获取当前二元运算符类型

            if operator_type not in allowed_operators:  # 判断运算符是否在允许列表中
                raise ValueError("不支持的运算符")  # 不允许的运算符直接报错

            calculate = allowed_operators[operator_type]  # 根据运算符类型取出对应计算函数

            return calculate(left_value, right_value)  # 执行运算并返回计算结果

        raise ValueError("不支持的表达式")  # 其他语法节点一律视为不支持

    parsed_expression = ast.parse(expression, mode="eval")  # 把字符串表达式解析为 eval 模式语法树

    result = calculate_node(parsed_expression.body)  # 从表达式主体开始递归计算结果

    return result  # 返回最终计算结果


def save_note_tool(content: str) -> dict:  # 定义保存笔记的工具函数
    note = {  # 构造笔记字典
        "id": len(notes) + 1,  # 使用当前笔记数量加一作为临时 ID
        "content": content,  # 保存笔记正文内容
    }  # 结束笔记字典构造

    notes.append(note)  # 将笔记追加到内存列表中

    return note  # 返回刚保存的笔记


def parse_tool_call_json(model_output: str) -> dict:  # 定义解析模型工具调用 JSON 的函数
    try:  # 尝试解析 JSON 字符串
        tool_call = json.loads(model_output)  # 将模型输出解析为 Python 对象

        if not isinstance(tool_call, dict):  # 判断解析结果是否不是字典对象
            return {  # 返回模型输出格式错误结果
                "tool_name": None,  # 标记没有工具可执行
                "tool_args": {},  # 返回空工具参数
                "error": "模型输出不是 JSON 对象",  # 返回格式错误说明
            }  # 结束格式错误结果字典

        if "tool_name" not in tool_call:  # 判断工具调用结果是否缺少工具名
            return {  # 返回缺少工具名的错误结果
                "tool_name": None,  # 标记没有工具可执行
                "tool_args": {},  # 返回空工具参数
                "error": "模型输出缺少 tool_name",  # 返回缺少字段说明
            }  # 结束缺少工具名结果字典

        if "tool_args" not in tool_call:  # 判断工具调用结果是否缺少工具参数
            return {  # 返回缺少工具参数的错误结果
                "tool_name": None,  # 标记没有工具可执行
                "tool_args": {},  # 返回空工具参数
                "error": "模型输出缺少 tool_args",  # 返回缺少字段说明
            }  # 结束缺少工具参数结果字典

        return tool_call  # 返回合法的工具调用字典

    except json.JSONDecodeError as e:  # 捕获 JSON 解析失败异常
        return {  # 返回 JSON 解析失败结果
            "tool_name": None,  # 标记没有工具可执行
            "tool_args": {},  # 返回空工具参数
            "error": f"JSON 解析失败：{e}",  # 返回解析失败说明
        }  # 结束解析失败结果字典


def execute_tool_call(tool_call: dict) -> dict:  # 定义执行工具调用的统一入口函数
    if "error" in tool_call:  # 判断工具调用决策是否已经包含错误
        return {  # 返回工具错误响应
            "type": "tool_error",  # 标记结果类型为工具错误
            "message": tool_call["error"],  # 返回上游错误信息
        }  # 结束工具错误响应字典

    tool_name = tool_call.get("tool_name")  # 从工具调用字典中读取工具名
    tool_args = tool_call.get("tool_args", {})  # 从工具调用字典中读取工具参数，默认空字典

    if tool_name is None:  # 判断是否无需调用任何工具
        return {  # 返回无需工具的响应
            "type": "no_tool",  # 标记结果类型为不调用工具
            "message": "这条消息不需要调用工具",  # 返回无需工具说明
        }  # 结束无需工具响应字典

    try:  # 尝试执行具体工具
        if tool_name == "calculator_tool":  # 判断要执行的是否为计算器工具
            args = CalculatorToolArgs(**tool_args)  # 使用 Pydantic 校验并解析计算器参数

            result = calculator_tool(args.expression)  # 调用计算器工具得到计算结果

            return {  # 返回工具执行成功结果
                "type": "tool_result",  # 标记结果类型为工具结果
                "tool_name": "calculator_tool",  # 返回实际执行的工具名
                "result": result,  # 返回计算结果
            }  # 结束工具成功结果字典

        if tool_name == "save_note_tool":  # 判断要执行的是否为保存笔记工具
            args = SaveNoteToolArgs(**tool_args)  # 使用 Pydantic 校验并解析保存笔记参数

            result = save_note_tool(args.content)  # 调用保存笔记工具得到保存结果

            return {  # 返回工具执行成功结果
                "type": "tool_result",  # 标记结果类型为工具结果
                "tool_name": "save_note_tool",  # 返回实际执行的工具名
                "result": result,  # 返回保存后的笔记数据
            }  # 结束工具成功结果字典

        return {  # 返回未知工具错误结果
            "type": "tool_error",  # 标记结果类型为工具错误
            "message": f"不支持的工具：{tool_name}",  # 返回不支持的工具名
        }  # 结束未知工具错误字典

    except ValidationError as e:  # 捕获工具参数校验失败异常
        return {  # 返回参数校验错误结果
            "type": "tool_error",  # 标记结果类型为工具错误
            "message": "工具参数校验失败",  # 返回参数校验失败说明
            "error": str(e),  # 返回详细校验错误
        }  # 结束参数校验错误字典

    except Exception as e:  # 捕获工具执行过程中的其他异常
        return {  # 返回工具执行失败结果
            "type": "tool_error",  # 标记结果类型为工具错误
            "message": "工具执行失败",  # 返回工具执行失败说明
            "error": str(e),  # 返回异常详情
        }  # 结束工具执行失败字典
# 输入：{
#    "tool_name": "calculator_tool",
#    "tool_args": {
#        "expression": "1+1"
#   }
# }
# 输出：
# {
#    "type": "tool_result",
#    "tool_name": "calculator_tool",
#   "result": 2
# }

