import logging  # 导入 Python 内置 logging 模块，用来记录日志
import os  # 导入 os 模块，用来创建日志目录
from logging.handlers import (
    RotatingFileHandler,
)  # 导入轮转文件日志处理器，避免日志文件无限变大

LOG_DIR = "logs"  # 定义日志目录名称，所有日志文件都会放到 logs 文件夹里

LOG_FILE = os.path.join(  # 拼接日志文件完整路径
    LOG_DIR,  # 日志目录
    "app.log",  # 日志文件名
)  # 日志文件路径拼接结束


def setup_logging() -> None:  # 定义初始化日志配置的函数
    os.makedirs(  # 创建日志目录
        LOG_DIR,  # 要创建的目录是 logs
        exist_ok=True,  # 如果 logs 已经存在，就不报错
    )  # 日志目录创建结束

    log_format = (  # 定义日志输出格式
        "%(asctime)s "  # 日志时间
        "[%(levelname)s] "  # 日志级别，例如 INFO、WARNING、ERROR
        "%(name)s "  # logger 名称，通常是模块名
        "%(filename)s:%(lineno)d "  # 出错文件名和行号
        "- %(message)s"  # 日志正文
    )  # 日志格式定义结束

    formatter = logging.Formatter(  # 创建日志格式化器
        log_format  # 使用上面定义的日志格式
    )  # 日志格式化器创建结束

    file_handler = RotatingFileHandler(  # 创建文件日志处理器
        LOG_FILE,  # 日志写入 logs/app.log
        maxBytes=5 * 1024 * 1024,  # 单个日志文件最大 5MB
        backupCount=5,  # 最多保留 5 个历史日志文件
        encoding="utf-8",  # 日志文件使用 UTF-8 编码，避免中文乱码
    )  # 文件日志处理器创建结束

    file_handler.setFormatter(  # 给文件日志处理器设置格式
        formatter  # 使用上面创建的日志格式化器
    )  # 文件日志格式设置结束

    file_handler.setLevel(  # 设置文件日志级别
        logging.INFO  # INFO 及以上级别都会写入文件
    )  # 文件日志级别设置结束

    console_handler = (
        logging.StreamHandler()
    )  # 创建控制台日志处理器，用来在终端显示日志

    console_handler.setFormatter(  # 给控制台日志处理器设置格式
        formatter  # 使用同一个日志格式
    )  # 控制台日志格式设置结束

    console_handler.setLevel(  # 设置控制台日志级别
        logging.INFO  # INFO 及以上级别都会显示到终端
    )  # 控制台日志级别设置结束

    root_logger = logging.getLogger()  # 获取根 logger，整个项目默认都会使用它

    root_logger.setLevel(  # 设置根 logger 级别
        logging.INFO  # 记录 INFO 及以上级别日志
    )  # 根 logger 级别设置结束

    root_logger.handlers.clear()  # 清空旧的日志处理器，避免 uvicorn reload 时重复打印日志

    root_logger.addHandler(  # 添加控制台日志处理器
        console_handler  # 控制台日志处理器
    )  # 控制台日志处理器添加结束

    root_logger.addHandler(  # 添加文件日志处理器
        file_handler  # 文件日志处理器
    )  # 文件日志处理器添加结束
