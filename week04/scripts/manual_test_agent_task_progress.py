import sys  # 导入 sys 模块，用来修改 Python 模块搜索路径
from pathlib import Path  # 导入 Path，用来处理项目路径

BASE_DIR = (
    Path(__file__).resolve().parents[1]
)  # 获取项目根目录，也就是 scripts 文件夹的上一级目录
sys.path.append(
    str(BASE_DIR)
)  # 把项目根目录加入 Python 搜索路径，避免找不到 services、models、database 等模块


from services.agent_task_service import (
    create_agent_task,
)  # 导入创建 AgentTask 任务的服务函数
from services.agent_task_service import (
    get_agent_task,
)  # 导入根据任务 ID 查询 AgentTask 的服务函数
from services.agent_task_service import (
    update_agent_task_job_id,
)  # 导入更新 RQ Job ID 的服务函数
from services.agent_task_service import (
    update_agent_task_progress,
)  # 导入更新任务进度的服务函数


def print_task_info(task_id: int):  # 定义打印任务信息的辅助函数
    task = get_agent_task(task_id)  # 根据任务 ID 查询最新任务数据

    if task is None:  # 判断任务是否不存在
        print("任务不存在")  # 打印任务不存在提示
        return  # 结束函数执行

    print("-" * 60)  # 打印分隔线，方便观察输出
    print("task_id =", task.id)  # 打印任务 ID
    print("status =", task.status)  # 打印任务状态
    print("progress =", task.progress)  # 打印任务进度
    print("current_step =", task.current_step)  # 打印当前步骤说明
    print("job_id =", task.job_id)  # 打印 RQ Job ID
    print("queued_at =", task.queued_at)  # 打印入队时间
    print("started_at =", task.started_at)  # 打印开始执行时间
    print("finished_at =", task.finished_at)  # 打印结束时间
    print("error =", task.error)  # 打印错误信息
    print("-" * 60)  # 打印分隔线，方便观察输出


def main():  # 定义测试脚本主函数
    task = create_agent_task(  # 创建一个模拟后台 Agent 任务
        task_type="report",  # 设置任务类型为 report，表示报告生成任务
        user_input="请根据知识库生成一份 Redis 学习报告",  # 设置用户原始输入
        status="created",  # 初始状态设置为 created，表示任务刚创建
        knowledge_base_id=1,  # 设置知识库 ID
        session_id=1,  # 设置会话 ID
        context="Redis 是一个基于内存的键值数据库，常用于缓存、会话存储和任务队列。",  # 设置模拟检索上下文
        citations=[  # 设置模拟引用来源列表
            {  # 第一条引用来源
                "document_id": 1,  # 模拟文档 ID
                "chunk_id": 101,  # 模拟文本块 ID
                "source": "Redis学习笔记.txt",  # 模拟来源文件名
                "content": "Redis 是一个基于内存的键值数据库。",  # 模拟引用内容
            }  # 第一条引用来源结束
        ],  # 引用来源列表结束
    )  # 创建任务结束

    print("第一步：创建任务成功")  # 打印当前测试步骤说明
    print_task_info(task.id)  # 打印任务当前信息

    update_agent_task_progress(  # 模拟任务加入队列
        task_id=task.id,  # 传入任务 ID
        status="queued",  # 把任务状态改成 queued
        progress=0,  # 设置任务进度为 0
        current_step="已加入队列，等待执行",  # 设置当前步骤说明
    )  # 入队状态更新结束

    print("第二步：任务已加入队列")  # 打印当前测试步骤说明
    print_task_info(task.id)  # 打印任务当前信息

    update_agent_task_job_id(  # 模拟保存 RQ Job ID
        task_id=task.id,  # 传入任务 ID
        job_id="mock-rq-job-id-001",  # 传入模拟的 RQ Job ID
    )  # Job ID 更新结束

    print("第三步：保存 RQ Job ID")  # 打印当前测试步骤说明
    print_task_info(task.id)  # 打印任务当前信息

    update_agent_task_progress(  # 模拟 Worker 开始执行任务
        task_id=task.id,  # 传入任务 ID
        status="running",  # 把任务状态改成 running
        progress=10,  # 设置任务进度为 10
        current_step="开始执行任务",  # 设置当前步骤说明
    )  # running 状态更新结束

    print("第四步：Worker 开始执行任务")  # 打印当前测试步骤说明
    print_task_info(task.id)  # 打印任务当前信息

    update_agent_task_progress(  # 模拟知识库检索阶段
        task_id=task.id,  # 传入任务 ID
        progress=30,  # 设置任务进度为 30
        current_step="正在检索知识库",  # 设置当前步骤说明
    )  # 知识库检索进度更新结束

    print("第五步：正在检索知识库")  # 打印当前测试步骤说明
    print_task_info(task.id)  # 打印任务当前信息

    update_agent_task_progress(  # 模拟报告生成阶段
        task_id=task.id,  # 传入任务 ID
        progress=60,  # 设置任务进度为 60
        current_step="正在生成报告内容",  # 设置当前步骤说明
    )  # 报告生成进度更新结束

    print("第六步：正在生成报告内容")  # 打印当前测试步骤说明
    print_task_info(task.id)  # 打印任务当前信息

    update_agent_task_progress(  # 模拟保存报告阶段
        task_id=task.id,  # 传入任务 ID
        progress=80,  # 设置任务进度为 80
        current_step="正在保存报告",  # 设置当前步骤说明
    )  # 保存报告进度更新结束

    print("第七步：正在保存报告")  # 打印当前测试步骤说明
    print_task_info(task.id)  # 打印任务当前信息

    update_agent_task_progress(  # 模拟导出 Markdown 阶段
        task_id=task.id,  # 传入任务 ID
        progress=90,  # 设置任务进度为 90
        current_step="正在导出 Markdown 文件",  # 设置当前步骤说明
    )  # 导出 Markdown 进度更新结束

    print("第八步：正在导出 Markdown 文件")  # 打印当前测试步骤说明
    print_task_info(task.id)  # 打印任务当前信息

    update_agent_task_progress(  # 模拟任务成功完成
        task_id=task.id,  # 传入任务 ID
        status="success",  # 把任务状态改成 success
        progress=100,  # 设置任务进度为 100
        current_step="任务完成",  # 设置当前步骤说明
        answer="# Redis 学习报告\n\nRedis 是一个基于内存的键值数据库。",  # 保存模拟报告正文
        report_id=999,  # 保存模拟报告 ID
        markdown_file_path="exports\\report_999_Redis学习报告.md",  # 保存模拟 Markdown 文件路径
    )  # success 状态更新结束

    print("第九步：任务执行成功")  # 打印当前测试步骤说明
    print_task_info(task.id)  # 打印任务当前信息


if __name__ == "__main__":  # 判断当前脚本是否是直接运行
    main()  # 如果是直接运行，就执行 main 函数
