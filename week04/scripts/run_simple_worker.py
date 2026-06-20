import sys  # 导入 sys 模块，用来修改 Python 模块搜索路径

from pathlib import Path  # 导入 Path，用来处理项目路径

from rq import SimpleWorker  # 导入 SimpleWorker，用来在 Windows 环境下执行 RQ 队列任务

BASE_DIR = (
    Path(__file__).resolve().parents[1]
)  # 获取项目根目录，也就是当前 scripts 文件夹的上一级目录

sys.path.append(
    str(BASE_DIR)
)  # 把项目根目录加入 Python 搜索路径，避免 Worker 找不到 services 模块


from services.rq_queue import agent_task_queue  # 导入 RQ 队列对象

from services.rq_queue import redis_connection  # 导入 Redis 连接对象

worker = SimpleWorker(  # 创建一个简单 Worker
    [agent_task_queue],  # 传入要监听的队列列表，这里只监听 agent_tasks 队列
    connection=redis_connection,  # 指定 Worker 使用的 Redis 连接
)  # SimpleWorker 创建结束


print("SimpleWorker 已启动，开始监听 agent_tasks 队列...")  # 打印 Worker 启动提示


worker.work(  # 启动 Worker，开始从队列中取任务执行
    burst=False  # False 表示持续监听队列，不要因为当前没任务就退出
)  # Worker 执行结束
