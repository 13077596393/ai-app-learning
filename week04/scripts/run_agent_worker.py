import sys  # 导入 sys 模块，用来修改 Python 模块搜索路径

from pathlib import Path  # 导入 Path，用来处理项目路径

from rq import SimpleWorker  # 导入 SimpleWorker，用来在 Windows 环境下执行 RQ 后台任务

BASE_DIR = (
    Path(__file__).resolve().parents[1]
)  # 获取项目根目录，也就是 scripts 文件夹的上一级目录

sys.path.append(
    str(BASE_DIR)
)  # 把项目根目录加入 Python 搜索路径，避免 Worker 找不到 services 模块


from services.rq_queue import (
    agent_task_queue,
)  # 导入 agent_tasks 队列对象，Worker 会监听这个队列

from services.rq_queue import (
    redis_connection,
)  # 导入 Redis 连接对象，Worker 需要通过它连接 Redis

worker = SimpleWorker(  # 创建 SimpleWorker 对象
    [agent_task_queue],  # 指定 Worker 监听的队列列表，这里只监听 agent_tasks 队列
    connection=redis_connection,  # 指定 Worker 使用的 Redis 连接
)  # SimpleWorker 创建结束


print("Agent SimpleWorker 已启动")  # 打印 Worker 启动提示

print("正在监听队列：agent_tasks")  # 打印当前监听的队列名称

print("等待执行后台 Agent 任务...")  # 打印等待任务提示


worker.work(  # 启动 Worker，开始从 Redis 队列中取任务执行
    burst=True,  # burst=True 表示执行完当前队列已有任务后自动退出，适合学习测试
)  # Worker 执行结束
