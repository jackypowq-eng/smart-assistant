from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from app.utils.config import config
from app.memory.factory import memory_factory
from app.agent.tools import get_weather, get_current_time, calculate, web_search_tool


class SmartAgent:
    def __init__(self, provider: str = "aliyun", session_id: str = None):
        self.provider = provider
        self.session_id = session_id
        self.llm = self._create_llm()
        self.memory = self._create_memory()
        self.document_processor = None

    def set_document_processor(self, processor):
        self.document_processor = processor

    def _create_llm(self):
        if self.provider == "aliyun":
            return ChatOpenAI(
                api_key=config.ALIYUN_API_KEY,
                base_url=config.ALIYUN_BASE_URL,
                model=config.ALIYUN_MODEL_NAME,
                temperature=0.7
            )
        elif self.provider == "ollama":
            return ChatOllama(
                model=config.OLLAMA_MODEL_NAME,
                base_url=config.OLLAMA_BASE_URL,
                temperature=0.7
            )
        else:
            raise ValueError(f"不支持的模型提供商: {self.provider}")

    def _create_memory(self):
        if self.session_id:
            return memory_factory.get_memory(self.session_id)
        return None

    async def run(self, query: str) -> str:
        try:
            messages = []
            if self.memory:
                messages.extend(self.memory.get_messages())

            # RAG 参考资料
            context = ""
            if self.document_processor:
                relevant_docs = self.document_processor.retrieve(query)
                if relevant_docs:
                    context = "\n\n".join([doc.page_content for doc in relevant_docs[:3]])

            # 构建系统提示，包含工具描述
            system_prompt = """你是一个智能助手，可以帮助用户回答问题。你可以使用以下工具：

1. get_weather: 查询指定城市的实时天气信息，参数为城市名称（如"北京"、"上海"）
2. get_current_time: 获取当前系统时间，无需参数
3. calculate: 数学计算工具，参数为数学表达式（如"3+5*2"）
4. web_search_tool: 联网搜索工具，用于查询最新信息、新闻、事实等，参数为搜索关键词（如"2024年奥运会举办城市"）

当用户询问天气、时间、需要计算，或需要最新信息、新闻、事实等时，请调用相应的工具。调用工具时，请使用以下格式：
TOOL_CALL: 工具名称|参数

例如：
TOOL_CALL: get_weather|北京
TOOL_CALL: get_current_time|
TOOL_CALL: calculate|3+5*2
TOOL_CALL: web_search_tool|2024年奥运会举办城市

工具调用结果会返回给你，请根据结果生成自然、友好的回答。
"""

            # 构建用户消息
            if context:
                user_message = f"参考资料：\n{context}\n\n用户问题：{query}"
            else:
                user_message = query

            # 构建完整消息列表
            full_messages = [SystemMessage(content=system_prompt)]
            full_messages.extend(messages)
            full_messages.append(HumanMessage(content=user_message))

            # 让 LLM 决定是否需要调用工具
            llm_response = await self.llm.ainvoke(full_messages)
            response_text = llm_response.content

            # 检查是否需要调用工具
            tool_response = None
            if "TOOL_CALL:" in response_text:
                try:
                    # 提取工具调用
                    tool_call_line = [line for line in response_text.split('\n') if "TOOL_CALL:" in line][0]
                    tool_call_parts = tool_call_line.replace("TOOL_CALL:", "").strip().split("|", 1)
                    tool_name = tool_call_parts[0].strip()
                    tool_param = tool_call_parts[1].strip() if len(tool_call_parts) > 1 else ""

                    # 异步调用工具
                    if tool_name == "get_weather" and tool_param:
                        weather_result = await get_weather.ainvoke({"city": tool_param})
                        if weather_result.success:
                            tool_response = self._format_weather_response(weather_result)
                        else:
                            tool_response = f"抱歉，查询天气时遇到了问题：{weather_result.error}"

                    elif tool_name == "get_current_time":
                        time_result = await get_current_time.ainvoke({})
                        if time_result.success:
                            tool_response = f"现在是{time_result.current_time}，希望你今天过得愉快！"
                        else:
                            tool_response = f"抱歉，获取时间时遇到了问题：{time_result.error}"

                    elif tool_name == "calculate" and tool_param:
                        calc_result = await calculate.ainvoke({"expression": tool_param})
                        if calc_result.success:
                            tool_response = f"计算结果是{calc_result.result}，希望这个答案对你有帮助！"
                        else:
                            tool_response = f"计算时遇到了问题：{calc_result.error}，请检查输入的表达式是否正确。"

                    elif tool_name == "web_search_tool" and tool_param:
                        search_result = await web_search_tool.ainvoke({"query": tool_param})
                        if search_result.success:
                            if search_result.results:
                                search_response = "我为你找到了以下信息：\n"
                                for i, result in enumerate(search_result.results, 1):
                                    search_response += f"{i}. {result}\n"
                                tool_response = search_response
                            else:
                                tool_response = "抱歉，没有找到相关信息。"
                        else:
                            tool_response = f"抱歉，搜索时遇到了问题：{search_result.error}"

                    # 如果成功调用工具，使用工具响应作为最终答案
                    if tool_response:
                        response = tool_response
                    else:
                        # 工具调用失败，使用 LLM 原始响应
                        response = response_text.replace("TOOL_CALL:" + tool_call_line, "").strip()

                except Exception as e:
                    # 工具调用出错，降级为普通对话
                    response = response_text.replace("TOOL_CALL:", "").strip()

            else:
                # 普通对话，直接使用 LLM 响应
                response = response_text

            # 保存记忆
            if self.memory:
                self.memory.add_message(HumanMessage(content=query))
                self.memory.add_message(AIMessage(content=response))

            return response

        except Exception as e:
            return f"抱歉，处理您的请求时遇到了问题：{str(e)}"

    def _format_weather_response(self, weather_result) -> str:
        """格式化天气响应，生成自然的回答"""
        location = weather_result.location
        weather = weather_result.weather
        temperature = weather_result.temperature
        feels_like = weather_result.feels_like

        # 根据天气情况生成自然的回答
        if "晴" in weather:
            if "高温" in weather or "热" in weather:
                return f"{location}今天超晴朗☀️，温度{temperature}，体感{feels_like}，有点热哦～出门记得涂防晒、多补水，小心中暑呀😅"
            else:
                return f"{location}今天天气超棒！大晴天☀️，温度{temperature}，体感{feels_like}，超舒服～出门记得防晒哦😉"
        elif "雨" in weather:
            if "雷" in weather:
                return f"{location}今天有雷雨⛈️，温度{temperature}，体感{feels_like}，出门记得带伞，远离大树和电线杆哦⚡"
            elif "阵" in weather:
                return f"{location}今天有阵雨🌦️，温度{temperature}，体感{feels_like}，出门记得带伞，天气多变要注意哦☂️"
            else:
                return f"{location}今天有雨☔，温度{temperature}，体感{feels_like}，出门记得带伞，路滑小心哦👟"
        elif "雪" in weather:
            if "大" in weather:
                return f"{location}今天下大雪啦❄️，温度{temperature}，体感{feels_like}，超冷的～出门多穿点，注意保暖和防滑哦⛄"
            else:
                return f"{location}今天下雪啦❄️，温度{temperature}，体感{feels_like}，超浪漫～出门记得穿暖和点哦😊"
        elif "雾" in weather or "霾" in weather:
            if "霾" in weather:
                return f"{location}今天有雾霾😷，温度{temperature}，体感{feels_like}，出门记得戴口罩，开车注意安全哦🚗"
            else:
                return f"{location}今天有雾🌫️，温度{temperature}，体感{feels_like}，出门注意安全，开车慢一点哦🚗"
        elif "云" in weather:
            if "多" in weather:
                return f"{location}今天多云☁️，温度{temperature}，体感{feels_like}，天气还不错呢，蛮舒服的～😊"
            else:
                return f"{location}今天天气挺好的☁️，温度{temperature}，体感{feels_like}，适合出门溜达哦✨"
        elif "风" in weather:
            return f"{location}今天有风💨，温度{temperature}，体感{feels_like}，出门记得多穿点，小心吹感冒哦😷"
        else:
            return f"{location}今天天气是{weather}，温度{temperature}，体感{feels_like}，希望你今天过得开开心心的！😊"
