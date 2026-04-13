from langchain_core.tools import tool
import math
from datetime import datetime

@tool
async def search_tool(query: str) -> str:
    """模拟网络搜索工具"""
    # 模拟搜索结果，实际项目中可以替换为真实的搜索引擎API
    return f"搜索结果：关于 '{query}' 的信息，这是一个模拟的搜索结果。"

@tool
async def calculator(expression: str) -> str:
    """数学计算工具，支持基本的数学表达式计算"""
    try:
        # 安全计算数学表达式
        result = eval(expression, {
            'math': math,
            'abs': abs,
            'pow': pow,
            'sqrt': math.sqrt,
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan
        })
        return f"计算结果：{expression} = {result}"
    except Exception as e:
        return f"计算错误：{str(e)}"

@tool
async def current_time() -> str:
    """获取当前时间"""
    now = datetime.now()
    return f"当前时间：{now.strftime('%Y-%m-%d %H:%M:%S')}"
