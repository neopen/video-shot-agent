"""
@FileName: __init__.py.py
@Description: Penshot - 智能分镜视频生成
@Author: HiPeng
@Time: 2026/3/6 22:34
"""

"""
使用方式：

1. Python 智能体调用（Function Call）：
    from penshot import PenshotFunction
    agent = PenshotFunction()
    result = agent.breakdown_script("剧本内容")

2. MCP 协议调用：
    python -m penshot.mcp_server

3. REST API 调用：
    POST /api/storyboard
"""
from penshot.api.function_calls import PenshotFunction, PenshotResult
from penshot.api.function_calls import create_penshot_agent

__version__ = "0.1.0"
__author__ = "HiPeng"

__all__ = [
    "PenshotFunction",
    "PenshotResult",
    "create_penshot_agent",
]