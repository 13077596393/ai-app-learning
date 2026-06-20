import logging  # 导入 logging 模块，用来获取 logger 并记录错误日志

from fastapi import FastAPI, Request  # 导入 FastAPI 应用类和 Request 请求对象
from fastapi.responses import JSONResponse  # 导入 JSONResponse，用来自定义异常返回 JSON

from logging_config import (
    setup_logging,
)  # 导入日志初始化函数，用来配置控制台日志和文件日志
from routers import users  # 导入用户相关路由模块
from routers import chat  # 导入聊天相关路由模块
from routers import knowledge_bases  # 导入知识库相关路由模块
from routers import documents  # 导入文档路由模块
from routers import retrieval  # 导入知识库检索路由模块
from routers import rag  # 导入 RAG 问答路由模块
from routers import eval  # 导入 RAG 评测路由模块
from routers import agent  # 导入 Agent 路由模块
from database import create_db_and_tables  # 导入创建数据库表的函数
from fastapi.staticfiles import (
    StaticFiles,
)  # 导入 FastAPI 的静态文件服务，用来访问前端 HTML、CSS、JS 文件
from routers import project_spaces  # 导入项目空间路由
from routers import project_members  # 导入项目成员管理路由
from routers import admin_dashboard  # 导入管理后台路由模块


setup_logging()  # 初始化项目日志配置，让日志可以输出到控制台和 logs/app.log 文件


logger = logging.getLogger(
    __name__
)  # 创建当前 main.py 模块的 logger，用来记录未处理异常
app = FastAPI(title="week04")  # 创建 FastAPI 应用实例

@app.exception_handler(
    Exception
)  # 注册全局异常处理器，用来捕获项目里没有被单独处理的程序异常
async def global_exception_handler(  # 定义全局异常处理函数
    request: Request,  # 当前请求对象，可以拿到请求方法、URL 等信息
    exc: Exception,  # 捕获到的异常对象
):  # 函数参数定义结束
    logger.exception(  # 记录完整异常日志，包含错误堆栈 traceback
        "未处理异常：%s %s",  # 日志模板，记录请求方法和请求地址
        request.method,  # 请求方法，例如 GET、POST、DELETE
        request.url,  # 请求完整 URL
    )  # 异常日志记录结束

    return JSONResponse(  # 返回统一的 JSON 错误响应
        status_code=500,  # 500 表示服务器内部错误
        content={  # 返回给前端的 JSON 内容
            "detail": "服务器内部错误，请稍后再试"  # 不暴露真实错误细节，只返回统一提示
        },  # JSON 内容结束
    )  # JSONResponse 返回结束

app.mount(  # 把一个本地文件夹挂载成浏览器可以访问的路径
    "/frontend",  # 浏览器访问路径前缀，比如 /frontend/agent-task-detail.html
    StaticFiles(directory="frontend"),  # 指定本地 frontend 文件夹作为静态文件目录
    name="frontend",  # 给这个静态文件挂载起一个名字
)  # 静态文件挂载结束

@app.on_event("startup")  # FastAPI 启动时自动执行
def on_startup():  # 定义启动事件函数
    create_db_and_tables()  # 创建数据库表


app.include_router(users.router)  # 注册用户路由，让用户注册、登录、users/me 等接口生效
app.include_router(chat.router)  # 注册聊天路由，让普通聊天和流式聊天接口生效
app.include_router(knowledge_bases.router)  # 注册知识库路由，让创建知识库接口生效
app.include_router(documents.router)  # 注册文档路由
app.include_router(retrieval.router)  # 注册知识库检索路由
app.include_router(
    rag.router
)  # 注册 RAG 问答路由，让 /knowledge-bases/{id}/rag/chat 接口生效
app.include_router(eval.router)  # 注册 RAG 评测相关接口
app.include_router(agent.router)  # 把 Agent 路由注册到 FastAPI 应用里
app.include_router(project_spaces.router)  # 注册项目空间接口到 FastAPI 应用
app.include_router(project_members.router)  # 注册项目成员管理接口到 FastAPI 应用
app.include_router(admin_dashboard.router)  # 注册管理后台接口路由

