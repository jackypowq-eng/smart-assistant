from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse  # 新增导入
from pydantic import BaseModel
from app.utils.config import config
from app.agent.core import SmartAgent

app = FastAPI(
    title=config.APP_NAME,
    version=config.APP_VERSION,
    description="A smart AI assistant built with LangChain and FastAPI"
)

agent = SmartAgent()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

# 聊天页面路由（直接返回 HTML 文件内容）
@app.get("/chat-page", response_class=HTMLResponse)
async def chat_page():
    try:
        with open("templates/chat.html", "r", encoding="utf-8") as f:
            html_content = f.read()
        return html_content
    except FileNotFoundError:
        return HTMLResponse(content="<h1>chat.html 文件未找到，请确保 templates/chat.html 存在</h1>", status_code=404)

# 其他路由保持不变
@app.get("/")
def read_root():
    return {
        "name": config.APP_NAME,
        "version": config.APP_VERSION,
        "model": config.MODEL_NAME
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        response = await agent.run(request.message)
        return ChatResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "healthy"}
