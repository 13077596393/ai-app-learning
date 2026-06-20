import time  # 导入 time 模块，用来模拟耗时任务


def say_hello_task(
    name: str,
) -> str:  # 定义一个测试后台任务函数，接收一个名字，返回一段文字
    print(f"后台任务开始执行：name={name}")  # 在 Worker 终端打印任务开始信息

    time.sleep(3)  # 暂停 3 秒，模拟一个耗时任务

    result = f"你好，{name}，这是 RQ 后台任务返回的结果。"  # 构造任务执行结果

    print(f"后台任务执行完成：result={result}")  # 在 Worker 终端打印任务完成信息

    return result  # 返回任务结果，RQ 会把这个结果保存到 Job 里
