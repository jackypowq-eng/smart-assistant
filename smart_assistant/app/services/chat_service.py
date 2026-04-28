from app.agent.core import SmartAgent
from fastapi.responses import HTMLResponse
from typing import Any, Dict, Optional

class ChatService:
    def __init__(self):
        self.agent = SmartAgent()

    def render_chat_page(self) -> HTMLResponse:
        # 假设模板渲染逻辑在此
        with open("templates/chat.html", "r", encoding="utf-8") as f:
            html = f.read()
        return HTMLResponse(content=html)

    async def handle_chat(self, user_input: str, session_id: Optional[str]) -> Dict[str, Any]:
        # 处理与 Agent 的对话
        response = await self.agent.chat(user_input, session_id)
        return {"response": response}

    async def clear_memory(self, session_id: Optional[str]) -> bool:
        # 清除会话记忆
        return await self.agent.clear_memory(session_id)
