from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.utils.config import config
from app.agent.core import SmartAgent

# 初始化FastAPI应用
app = FastAPI(
    title=config.APP_NAME,
    version=config.APP_VERSION,
    description="A smart AI assistant built with LangChain and FastAPI"
)

# 初始化SmartAgent
agent = SmartAgent()

# 定义输入输出模型
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

# 根路由
@app.get("/")
def read_root():
    return {
        "name": config.APP_NAME,
        "version": config.APP_VERSION,
        "model": config.MODEL_NAME
    }

# 聊天路由
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        # 使用SmartAgent处理消息
        response = await agent.run(request.message)
        return ChatResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 健康检查路由
@app.get("/health")
def health_check():
    return {"status": "healthy"}
