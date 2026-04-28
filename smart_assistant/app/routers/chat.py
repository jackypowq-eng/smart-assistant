from fastapi import APIRouter, Depends, Request
from app.services.chat_service import ChatService
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()

chat_service = ChatService()

@router.get("/chat-page", response_class=HTMLResponse)
async def chat_page():
    """返回聊天页面"""
    return chat_service.render_chat_page()

@router.post("/chat")
async def chat(request: Request):
    """处理聊天请求"""
    data = await request.json()
    user_input = data.get("message", "")
    session_id = data.get("session_id", None)
    response = await chat_service.handle_chat(user_input, session_id)
    return JSONResponse(response)

@router.post("/clear_memory")
async def clear_memory(request: Request):
    """清除会话记忆"""
    data = await request.json()
    session_id = data.get("session_id", None)
    result = await chat_service.clear_memory(session_id)
    return JSONResponse({"success": result})
