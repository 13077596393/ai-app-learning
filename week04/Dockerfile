# 使用 Python 3.11 的轻量版镜像作为基础环境
FROM python:3.11-slim

# 设置容器内部的工作目录为 /app
WORKDIR /app

# 设置 Python 不生成 .pyc 缓存文件，减少无用文件
ENV PYTHONDONTWRITEBYTECODE=1

# 设置 Python 日志直接输出，不做缓冲，方便 Docker 查看实时日志
ENV PYTHONUNBUFFERED=1

# 复制依赖文件到容器的 /app 目录
COPY requirements.txt .

# 安装 Python 项目依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制当前目录下的项目代码到容器的 /app 目录
COPY . .

# 声明容器内部 FastAPI 服务使用 8000 端口
EXPOSE 8000

# 容器启动时运行 FastAPI 服务
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]