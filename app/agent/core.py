from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from app.utils.config import config
from app.agent.tools import search_tool, calculator, current_time


SYSTEM_PROMPT = """Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}"""


class SmartAgent:
    def __init__(self):
        self.llm = ChatOpenAI(
            api_key=config.ALIYUN_API_KEY,
            base_url=config.BASE_URL,  # 使用 config 里的地址
            model=config.MODEL_NAME,
            temperature=0.7
        )
        
        self.tools = [search_tool, calculator, current_time]
        
        self.prompt = ChatPromptTemplate.from_template(SYSTEM_PROMPT)
        
        self.agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.prompt
        )
        
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True
        )
    
    async def run(self, query: str) -> str:
        try:
            result = await self.agent_executor.ainvoke({"input": query})
            return result.get("output", "")
        except Exception as e:
            return f"错误：{str(e)}"