from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama

from app.utils.config import config
from app.memory.factory import memory_factory


class SmartAgent:
    def __init__(self, provider: str = "aliyun", session_id: str = None):
        self.provider = provider
        self.session_id = session_id
        self.llm = self._create_llm()
        self.memory = self._create_memory()
        self.document_processor = None
    
    def set_document_processor(self, processor):
        """设置文档处理器"""
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
        """创建记忆实例"""
        if self.session_id:
            return memory_factory.get_memory(self.session_id)
        return None

    async def run(self, query: str) -> str:
        try:
            # 构建消息列表
            messages = []
            
            # 如果有记忆，从记忆中加载历史
            if self.memory:
                messages.extend(self.memory.get_messages())
            
            # RAG 检索
            context = ""
            if self.document_processor:
                relevant_docs = self.document_processor.retrieve(query)
                if relevant_docs:
                    context = "\n\n".join([doc.page_content for doc in relevant_docs[:3]])
                    messages.append(HumanMessage(content=f"参考资料:\n{context}"))
            
            # 添加当前查询
            user_message = HumanMessage(content=query)
            messages.append(user_message)
            
            # 调用 LLM
            result = await self.llm.ainvoke(messages)
            response = result.content if hasattr(result, 'content') else str(result)
            
            # 保存到记忆
            if self.memory:
                self.memory.add_message(user_message)
                self.memory.add_message(AIMessage(content=response))
            
            return response
        except Exception as e:
            return f"错误：{str(e)}"
