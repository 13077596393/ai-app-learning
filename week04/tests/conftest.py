import sys  # 导入 sys 模块，用来修改 Python 的模块搜索路径

from pathlib import Path  # 导入 Path，用来安全地处理项目路径

PROJECT_ROOT = (
    Path(__file__).resolve().parents[1]
)  # 获取 week04 项目根目录，也就是 tests 的上一级目录

if str(PROJECT_ROOT) not in sys.path:  # 如果 week04 根目录还没有加入 Python 搜索路径
    sys.path.insert(
        0, str(PROJECT_ROOT)
    )  # 把 week04 根目录加入搜索路径最前面，让测试可以导入 services、routers 等模块
