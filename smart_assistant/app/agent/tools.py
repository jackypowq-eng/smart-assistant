from langchain_core.tools import tool
import math
from datetime import datetime
import requests
from pydantic import BaseModel, Field
from typing import Optional


class WeatherResult(BaseModel):
    location: str = Field(description="城市名称")
    weather: str = Field(description="天气状况")
    temperature: str = Field(description="温度")
    feels_like: str = Field(description="体感温度")
    humidity: str = Field(description="湿度")
    wind: str = Field(description="风向风力")
    success: bool = Field(description="查询是否成功")
    error: Optional[str] = Field(default=None, description="错误信息")


class TimeResult(BaseModel):
    current_time: str = Field(description="当前时间")
    success: bool = Field(description="查询是否成功")
    error: Optional[str] = Field(default=None, description="错误信息")


class CalculatorResult(BaseModel):
    expression: str = Field(description="原始表达式")
    result: float = Field(description="计算结果")
    success: bool = Field(description="计算是否成功")
    error: Optional[str] = Field(default=None, description="错误信息")


class SearchResult(BaseModel):
    query: str = Field(description="搜索查询")
    results: list[str] = Field(description="搜索结果列表")
    success: bool = Field(description="搜索是否成功")
    error: Optional[str] = Field(default=None, description="错误信息")


def web_search(query: str) -> SearchResult:
    """联网搜索功能，使用 Serper API"""
    try:
        # 这里使用 Serper API，需要设置 API Key
        # 可以在环境变量或配置文件中设置
        API_KEY = "81990b96cd682cf467b624932e6f7233b21ab65e"  # 替换为真实的 API Key
        
        if not API_KEY:
            return SearchResult(
                query=query,
                results=[],
                success=False,
                error="API Key 未配置，请设置 Serper API Key"
            )
        
        url = "https://google.serper.dev/search"
        headers = {
            "X-API-KEY": API_KEY,
            "Content-Type": "application/json"
        }
        data = {
            "q": query,
            "num": 5
        }
        
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        
        search_data = response.json()
        
        results = []
        if "organic" in search_data:
            for item in search_data["organic"]:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                link = item.get("link", "")
                if title and snippet:
                    results.append(f"{title}: {snippet} (链接: {link})")
        
        if not results:
            return SearchResult(
                query=query,
                results=["未找到相关信息"],
                success=True,
                error=None
            )
        
        return SearchResult(
            query=query,
            results=results[:3],  # 只返回前3个结果
            success=True,
            error=None
        )
        
    except requests.RequestException as e:
        return SearchResult(
            query=query,
            results=[],
            success=False,
            error=f"网络请求失败: {str(e)}"
        )
    except Exception as e:
        return SearchResult(
            query=query,
            results=[],
            success=False,
            error=f"搜索出错: {str(e)}"
        )


@tool
def search_tool(query: str) -> str:
    """模拟网络搜索工具, 用于查询各类信息"""
    return f"搜索结果: 关于 '{query}' 的信息, 这是一个模拟的搜索结果。"


@tool
def web_search_tool(query: str) -> SearchResult:
    """联网搜索工具，用于查询最新信息、新闻、事实等"""
    return web_search(query)

@tool
def calculator(expression: str) -> str:
    """数学计算工具, 支持基本的数学表达式计算, 输入如 '3+5*2'"""
    try:
        result = eval(expression, {
            "math": math,
            "abs": abs,
            "pow": pow,
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan
        })
        return f"计算结果: {expression} = {result}"
    except Exception as e:
        return f"计算错误: {str(e)}"

@tool
def current_time() -> str:
    """获取当前系统时间"""
    now = datetime.now()
    return f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}"

def weather_query(city: str) -> WeatherResult:
    """获取指定城市的实时天气信息"""
    try:
        API_KEY = "SSvxJEM2z8bfPW_PT"
        if not API_KEY:
            return WeatherResult(
                location=city,
                weather="未知",
                temperature="未知",
                feels_like="未知",
                humidity="未知",
                wind="未知",
                success=False,
                error="API Key 未配置"
            )
        
        clean_city = city.replace("今天", "").replace("天气", "").replace("现在", "").strip()
        if not clean_city:
            return WeatherResult(
                location=city,
                weather="未知",
                temperature="未知",
                feels_like="未知",
                humidity="未知",
                wind="未知",
                success=False,
                error="请提供有效的城市名称"
            )
        
        url = "https://api.seniverse.com/v3/weather/now.json"
        params = {
            "key": API_KEY,
            "location": clean_city,
            "language": "zh-Hans",
            "unit": "c"
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 404:
            return WeatherResult(
                location=clean_city,
                weather="未知",
                temperature="未知",
                feels_like="未知",
                humidity="未知",
                wind="未知",
                success=False,
                error=f"城市 '{clean_city}' 未找到"
            )
        
        response.raise_for_status()
        
        data = response.json()
        if "results" in data and len(data["results"]) > 0:
            weather_data = data["results"][0]
            location = weather_data["location"]["name"]
            now = weather_data["now"]
            text = now["text"]
            temperature = now["temperature"]
            feels_like = now.get("feels_like", temperature)
            humidity = now.get("humidity", "未知")
            wind = f"{now.get('wind_direction', '未知')}{now.get('wind_scale', '')}"
            
            return WeatherResult(
                location=location,
                weather=text,
                temperature=f"{temperature}°C",
                feels_like=f"{feels_like}°C",
                humidity=f"{humidity}%",
                wind=wind,
                success=True,
                error=None
            )
        else:
            return WeatherResult(
                location=clean_city,
                weather="未知",
                temperature="未知",
                feels_like="未知",
                humidity="未知",
                wind="未知",
                success=False,
                error=f"未找到城市 {clean_city} 的天气信息"
            )
            
    except requests.RequestException as e:
        return WeatherResult(
            location=city,
            weather="未知",
            temperature="未知",
            feels_like="未知",
            humidity="未知",
            wind="未知",
            success=False,
            error=f"网络请求失败: {str(e)}"
        )
    except Exception as e:
        return WeatherResult(
            location=city,
            weather="未知",
            temperature="未知",
            feels_like="未知",
            humidity="未知",
            wind="未知",
            success=False,
            error=f"查询出错: {str(e)}"
        )

@tool
def get_weather(city: str) -> WeatherResult:
    """获取指定城市的实时天气信息, 输入城市名如 '北京'、'上海'"""
    return weather_query(city)


@tool
def get_current_time() -> TimeResult:
    """获取当前系统时间"""
    try:
        now = datetime.now()
        return TimeResult(
            current_time=now.strftime('%Y-%m-%d %H:%M:%S'),
            success=True,
            error=None
        )
    except Exception as e:
        return TimeResult(
            current_time="未知",
            success=False,
            error=f"获取时间失败: {str(e)}"
        )


@tool
def calculate(expression: str) -> CalculatorResult:
    """数学计算工具, 支持基本的数学表达式计算, 输入如 '3+5*2'"""
    try:
        result = eval(expression, {
            "math": math,
            "abs": abs,
            "pow": pow,
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan
        })
        return CalculatorResult(
            expression=expression,
            result=float(result),
            success=True,
            error=None
        )
    except Exception as e:
        return CalculatorResult(
            expression=expression,
            result=0.0,
            success=False,
            error=str(e)
        )
