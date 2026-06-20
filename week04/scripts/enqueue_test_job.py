import sys  # 导入 sys 模块，用来修改 Python 模块搜索路径

from pathlib import Path  # 导入 Path，用来处理项目路径

BASE_DIR = (
    Path(__file__).resolve().parents[1]
)  # 获取项目根目录，也就是当前 scripts 文件夹的上一级目录

sys.path.append(
    str(BASE_DIR)
)  # 把项目根目录加入 Python 搜索路径，避免找不到 services 模块


from services.rq_queue import agent_task_queue  # 导入我们创建好的 RQ 队列对象

from services.rq_test_tasks import say_hello_task  # 导入测试后台任务函数

job = agent_task_queue.enqueue(  # 把测试任务放入 RQ 队列
    say_hello_task,  # 传入要后台执行的函数
    "宇祥",  # 传入函数参数，相当于以后执行 say_hello_task("宇祥")
)  # 入队操作结束


print("任务已放入队列")  # 打印提示，说明入队成功

print("job_id =", job.id)  # 打印 RQ 自动生成的 Job ID

print("job_status =", job.get_status())  # 打印当前 Job 状态，正常刚入队应该是 queued
