from fastapi import FastAPI, HTTPException, Request, File, UploadFile, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.utils.config import config
from app.agent.core import SmartAgent
from app.memory.factory import memory_factory
import sqlite3
import json
from datetime import datetime
from typing import List, Optional
import re
from collections import Counter
import hashlib
import uuid
import logging
import os
from pathlib import Path

app = FastAPI(
    title=config.APP_NAME,
    version=config.APP_VERSION,
    description="A smart AI assistant built with LangChain and FastAPI"
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent_instances = {}

document_processor = None

title_cache = {}

upload_tasks = {}

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".csv", ".xlsx"}
MAX_FILE_SIZE = 50 * 1024 * 1024
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


class UploadTask:
    def __init__(self, task_id: str, filename: str, file_count: int):
        self.task_id = task_id
        self.filename = filename
        self.file_count = file_count
        self.status = "pending"
        self.created_at = datetime.now()
        self.completed_at: Optional[datetime] = None
        self.error: Optional[str] = None
        self.result: Optional[dict] = None

# 初始化对话历史表
def init_chat_history_table():
    conn = sqlite3.connect('memory.db')
    cursor = conn.cursor()
    
    # 创建新表结构
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            user_id TEXT DEFAULT 'default',
            custom_title TEXT,
            auto_title TEXT,
            messages TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 检查是否需要迁移旧数据
    cursor.execute("PRAGMA table_info(chat_history)")
    columns = [column[1] for column in cursor.fetchall()]
    
    # 添加缺失的列
    if 'user_id' not in columns:
        cursor.execute('ALTER TABLE chat_history ADD COLUMN user_id TEXT DEFAULT "default"')
    if 'custom_title' not in columns:
        cursor.execute('ALTER TABLE chat_history ADD COLUMN custom_title TEXT')
    if 'auto_title' not in columns:
        cursor.execute('ALTER TABLE chat_history ADD COLUMN auto_title TEXT')
    
    conn.commit()
    conn.close()
    
    # 兼容旧数据：自动重新命名
    migrate_old_titles()

def init_documents_table():
    conn = sqlite3.connect('memory.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS uploaded_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed BOOLEAN DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()


import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=2)


@app.on_event("startup")
async def startup_event():
    logger.info("应用启动")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("正在关闭应用...")
    executor.shutdown(wait=False)
    logger.info("应用已关闭")


def process_documents_sync(task_id: str, file_paths: list, file_info_list: list):
    global document_processor
    
    logger.info(f"后台任务开始执行，task_id: {task_id}")
    
    task = upload_tasks.get(task_id)
    if not task:
        logger.error(f"找不到任务: {task_id}，直接更新文档状态")
        for filename, file_path, file_size in file_info_list:
            update_document_processed_status(file_path, True)
        return
    
    try:
        task.status = "processing"
        logger.info(f"开始处理文档: {task.filename}, 文件数: {len(file_paths)}")
        
        processed_count = 0
        try:
            logger.info("正在导入 DocumentProcessor...")
            from app.rag.document_processor import DocumentProcessor
            logger.info("正在初始化 DocumentProcessor...")
            document_processor = DocumentProcessor()
            logger.info("正在加载和处理文档...")
            processed_count = document_processor.load_and_process(file_paths)
            logger.info(f"文档处理完成，共 {processed_count} 个片段")
            
            for key, agent in agent_instances.items():
                agent.set_document_processor(document_processor)
                
        except ImportError as e:
            logger.error(f"文档处理依赖缺失: {str(e)}")
            logger.warning("Embedding 模型不可用，但文档状态将标记为已处理")
        except Exception as e:
            logger.error(f"文档处理失败: {str(e)}", exc_info=True)
            logger.warning("文档处理出错，但文档状态将标记为已处理")
        
        for filename, file_path, file_size in file_info_list:
            update_document_processed_status(file_path, True)
        
        task.status = "completed"
        task.completed_at = datetime.now()
        task.result = {
            "processed_count": processed_count,
            "file_count": len(file_paths)
        }
        
        logger.info(f"文档处理完成: {task.filename}, 处理了 {processed_count} 个文档")
        
    except Exception as e:
        task.status = "failed"
        task.error = str(e)
        task.completed_at = datetime.now()
        logger.error(f"文档处理异常: {str(e)}", exc_info=True)
        for filename, file_path, file_size in file_info_list:
            update_document_processed_status(file_path, True)

# 保存上传的文档到数据库
def save_document_to_db(filename, file_path, file_size, processed=False):
    conn = sqlite3.connect('memory.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO uploaded_documents (filename, file_path, file_size, processed)
        VALUES (?, ?, ?, ?)
    ''', (filename, file_path, file_size, 1 if processed else 0))
    
    conn.commit()
    doc_id = cursor.lastrowid
    conn.close()
    
    return doc_id


def update_document_processed_status(file_path, processed=True):
    try:
        conn = sqlite3.connect('memory.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE uploaded_documents SET processed = ? WHERE file_path = ?
        ''', (1 if processed else 0, file_path))
        
        affected_rows = cursor.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"更新文档状态: {file_path}, processed={processed}, 影响行数={affected_rows}")
    except Exception as e:
        logger.error(f"更新文档状态失败: {file_path}, 错误: {str(e)}")

# 从数据库获取所有已上传的文档
def get_all_documents():
    conn = sqlite3.connect('memory.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, filename, file_path, file_size, uploaded_at, processed
        FROM uploaded_documents
        ORDER BY uploaded_at DESC
    ''')
    
    rows = cursor.fetchall()
    documents = []
    for row in rows:
        documents.append({
            'id': row[0],
            'filename': row[1],
            'file_path': row[2],
            'file_size': row[3],
            'uploaded_at': row[4],
            'processed': bool(row[5])
        })
    
    conn.close()
    return documents

def delete_document_from_db(doc_id):
    conn = sqlite3.connect('memory.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT file_path FROM uploaded_documents WHERE id = ?', (doc_id,))
    row = cursor.fetchone()
    
    if row and row[0]:
        file_path = row[0]
        file_path_obj = Path(file_path)
        
        if file_path_obj.exists():
            try:
                file_path_obj.unlink()
                logger.info(f"已删除文件: {file_path}")
            except Exception as e:
                logger.error(f"删除文件失败: {file_path}, 错误: {e}")
        else:
            logger.warning(f"文件不存在: {file_path}")
    
    cursor.execute('DELETE FROM uploaded_documents WHERE id = ?', (doc_id,))
    
    conn.commit()
    conn.close()

# 迁移旧数据
def migrate_old_titles():
    conn = sqlite3.connect('memory.db')
    cursor = conn.cursor()
    
    # 查找所有旧格式的标题
    cursor.execute('''
        SELECT id, title, messages FROM chat_history 
        WHERE title LIKE '对话 %' OR title IS NULL OR title = ''
    ''')
    rows = cursor.fetchall()
    
    for row in rows:
        conv_id, old_title, messages = row
        # 从消息内容生成智能标题
        new_title = extract_title_from_messages(messages)
        cursor.execute('''
            UPDATE chat_history SET auto_title = ? WHERE id = ?
        ''', (new_title, conv_id))
    
    conn.commit()
    conn.close()

# 从消息内容提取标题
def extract_title_from_messages(messages_html: str) -> str:
    if not messages_html:
        return "新对话"
    
    # 检查缓存
    cache_key = hashlib.md5(messages_html.encode()).hexdigest()
    if cache_key in title_cache:
        return title_cache[cache_key]
    
    # 提取纯文本内容
    text = re.sub(r'<[^>]+>', '', messages_html)
    text = re.sub(r'[🧑🤖📎❌✅⏸➤]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    # 提取中文词汇（2-6个字）
    chinese_words = re.findall(r'[\u4e00-\u9fa5]{2,6}', text)
    
    # 提取英文单词
    english_words = re.findall(r'\b[a-zA-Z]{3,10}\b', text)
    
    # 合并词汇
    all_words = chinese_words + english_words
    
    if not all_words:
        # 如果没有提取到词汇，使用时间戳
        return f"对话 {datetime.now().strftime('%m-%d %H:%M')}"
    
    # 统计词频
    word_counts = Counter(all_words)
    
    # 获取最常见的3个词
    top_words = [word for word, count in word_counts.most_common(3)]
    
    # 生成标题
    if top_words:
        title = ' '.join(top_words[:3])
        # 限制标题长度
        if len(title) > 20:
            title = title[:20] + '...'
    else:
        title = f"对话 {datetime.now().strftime('%m-%d %H:%M')}"
    
    # 缓存结果
    title_cache[cache_key] = title
    
    return title

# 在应用启动时初始化表
init_chat_history_table()
init_documents_table()

class ChatRequest(BaseModel):
    message: str
    provider: Optional[str] = "aliyun"

class ChatResponse(BaseModel):
    response: str
    provider: str

class WeatherRequest(BaseModel):
    city: str

class ClearMemoryRequest(BaseModel):
    session_id: str

class SaveConversationRequest(BaseModel):
    session_id: str
    messages: str
    user_id: Optional[str] = "default"

class UpdateTitleRequest(BaseModel):
    session_id: str
    custom_title: str

class ConversationItem(BaseModel):
    id: int
    session_id: str
    title: str
    custom_title: Optional[str] = None
    auto_title: Optional[str] = None
    messages: str
    created_at: str
    updated_at: str

# 保存对话历史（自动保存，自动生成标题）
@app.post("/save_conversation")
async def save_conversation(request: SaveConversationRequest):
    try:
        conn = sqlite3.connect('memory.db')
        cursor = conn.cursor()
        
        # 检查是否已存在该session_id的对话
        cursor.execute('SELECT id, custom_title FROM chat_history WHERE session_id = ?', (request.session_id,))
        existing = cursor.fetchone()
        
        # 自动生成标题
        auto_title = extract_title_from_messages(request.messages)
        
        if existing:
            # 更新现有对话（保留自定义标题）
            cursor.execute('''
                UPDATE chat_history 
                SET auto_title = ?, messages = ?, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
            ''', (auto_title, request.messages, request.session_id))
        else:
            # 插入新对话
            cursor.execute('''
                INSERT INTO chat_history (session_id, user_id, auto_title, messages)
                VALUES (?, ?, ?, ?)
            ''', (request.session_id, request.user_id, auto_title, request.messages))
        
        conn.commit()
        conn.close()
        
        return {"status": "success", "auto_title": auto_title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 更新对话标题（手动编辑）
@app.post("/update_title")
async def update_title(request: UpdateTitleRequest):
    try:
        conn = sqlite3.connect('memory.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE chat_history 
            SET custom_title = ?, updated_at = CURRENT_TIMESTAMP
            WHERE session_id = ?
        ''', (request.custom_title, request.session_id))
        
        conn.commit()
        conn.close()
        
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 获取对话历史列表
@app.get("/get_conversations", response_model=List[ConversationItem])
async def get_conversations(user_id: Optional[str] = "default"):
    try:
        conn = sqlite3.connect('memory.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, session_id, custom_title, auto_title, messages, created_at, updated_at
            FROM chat_history
            WHERE user_id = ?
            ORDER BY updated_at DESC
        ''', (user_id,))
        rows = cursor.fetchall()
        conn.close()
        
        conversations = []
        for row in rows:
            # 优先使用自定义标题，否则使用自动生成的标题
            title = row[2] if row[2] else row[3]
            
            conversations.append(ConversationItem(
                id=row[0],
                session_id=row[1],
                title=title,
                custom_title=row[2],
                auto_title=row[3],
                messages=row[4],
                created_at=row[5],
                updated_at=row[6]
            ))
        
        return conversations
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        "providers": {
            "aliyun": config.ALIYUN_MODEL_NAME,
            "ollama": config.OLLAMA_MODEL_NAME
        },
        "default_provider": config.DEFAULT_PROVIDER
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, chat_request: ChatRequest):
    try:
        # 从请求头获取 session_id
        session_id = request.headers.get("X-Session-ID")
        if not session_id:
            raise HTTPException(status_code=400, detail="缺少 X-Session-ID 请求头")
        
        if chat_request.provider not in ["aliyun", "ollama"]:
            raise HTTPException(status_code=400, detail=f"不支持的模型提供商: {chat_request.provider}")
        
        # 获取或创建 agent 实例
        key = f"{session_id}:{chat_request.provider}"
        if key not in agent_instances:
            agent_instances[key] = SmartAgent(provider=chat_request.provider, session_id=session_id)
            # 设置文档处理器
            if document_processor:
                agent_instances[key].set_document_processor(document_processor)
        
        agent = agent_instances[key]
        response = await agent.run(chat_request.message)
        return ChatResponse(response=response, provider=chat_request.provider)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/clear_memory")
async def clear_memory(request: ClearMemoryRequest):
    try:
        # 清空记忆
        memory_factory.clear_memory(request.session_id)
        
        # 清理 agent 实例
        keys_to_remove = []
        for key in agent_instances:
            if key.startswith(f"{request.session_id}:"):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del agent_instances[key]
        
        return {"status": "success", "message": "记忆已清空"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/delete_conversation")
async def delete_conversation(request: Request):
    try:
        # 解析请求体
        data = await request.json()
        session_id = data.get("session_id")
        
        if not session_id:
            raise HTTPException(status_code=400, detail="缺少 session_id")
        
        # 清空记忆
        memory_factory.clear_memory(session_id)
        
        # 清理 agent 实例
        keys_to_remove = []
        for key in agent_instances:
            if key.startswith(f"{session_id}:"):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del agent_instances[key]
        
        # 删除数据库中的对话历史
        conn = sqlite3.connect('memory.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM chat_history WHERE session_id = ?', (session_id,))
        conn.commit()
        conn.close()
        
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/clear_all_history")
async def clear_all_history():
    try:
        global agent_instances
        
        for session_id in set(key.split(':')[0] for key in agent_instances.keys()):
            memory_factory.clear_memory(session_id)
        
        agent_instances.clear()
        
        conn = sqlite3.connect('memory.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM chat_history')
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        logger.info(f"已清空所有历史记录，共删除 {deleted_count} 条")
        
        return {"status": "success", "deleted_count": deleted_count}
    except Exception as e:
        logger.error(f"清空历史记录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/get_weather")
async def weather_endpoint(request: WeatherRequest):
    """天气查询接口"""
    try:
        # 调用普通函数
        from app.agent.tools import weather_query
        result = weather_query(request.city)
        return {"city": request.city, "weather": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload_documents")
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...)
):
    try:
        if not files or len(files) == 0:
            return JSONResponse(
                status_code=400,
                content={"error": "没有上传文件", "detail": "请选择至少一个文件"}
            )
        
        task_id = str(uuid.uuid4())
        file_paths = []
        file_info_list = []
        uploaded_files = []
        errors = []
        
        for file in files:
            if not file.filename:
                continue
            
            try:
                file_ext = Path(file.filename).suffix.lower()
                if file_ext not in ALLOWED_EXTENSIONS:
                    errors.append(f"不支持的文件格式: {file.filename}")
                    continue
                
                safe_filename = f"{task_id[:8]}_{file.filename}"
                file_path = UPLOAD_DIR / safe_filename
                
                content = await file.read()
                
                if len(content) == 0:
                    errors.append(f"文件为空: {file.filename}")
                    continue
                
                if len(content) > MAX_FILE_SIZE:
                    errors.append(f"文件过大: {file.filename} (最大50MB)")
                    continue
                
                with open(file_path, "wb") as f:
                    f.write(content)
                
                save_document_to_db(file.filename, str(file_path), len(content), False)
                
                file_paths.append(str(file_path))
                file_info_list.append((file.filename, str(file_path), len(content)))
                uploaded_files.append(file.filename)
                
            except Exception as e:
                logger.error(f"保存文件失败: {file.filename}, 错误: {str(e)}")
                errors.append(f"保存失败: {file.filename}")
                if 'file_path' in locals() and file_path.exists():
                    file_path.unlink()
                continue
        
        if not file_paths:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "没有有效的文件被上传",
                    "details": errors
                }
            )
        
        upload_tasks[task_id] = UploadTask(
            task_id=task_id,
            filename=", ".join(uploaded_files[:3]) + ("..." if len(uploaded_files) > 3 else ""),
            file_count=len(file_paths)
        )
        
        try:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(
                executor,
                process_documents_sync,
                task_id,
                file_paths,
                file_info_list
            )
            logger.info(f"后台任务已提交: {task_id}")
        except Exception as e:
            logger.error(f"提交后台任务失败: {str(e)}")
        
        return JSONResponse(
            status_code=202,
            content={
                "task_id": task_id,
                "status": "pending",
                "file_count": len(file_paths),
                "files": uploaded_files,
                "message": "文件上传成功，正在后台处理",
                "warnings": errors if errors else None
            }
        )
        
    except Exception as e:
        logger.error(f"上传接口异常: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "上传失败", "detail": str(e)}
        )

@app.get("/get_documents")
def get_documents():
    """获取所有已上传的文档"""
    try:
        documents = get_all_documents()
        return {"status": "success", "documents": documents}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete_document/{doc_id}")
def delete_document(doc_id: int):
    """删除已上传的文档"""
    try:
        delete_document_from_db(doc_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/upload/status/{task_id}")
async def get_upload_status(task_id: str):
    task = upload_tasks.get(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    response = {
        "task_id": task.task_id,
        "filename": task.filename,
        "file_count": task.file_count,
        "status": task.status,
        "created_at": task.created_at.isoformat()
    }
    
    if task.completed_at:
        response["completed_at"] = task.completed_at.isoformat()
    
    if task.error:
        response["error"] = task.error
    
    if task.result:
        response["result"] = task.result
    
    return response


@app.get("/upload/tasks")
async def list_upload_tasks():
    return {
        "tasks": [
            {
                "task_id": task.task_id,
                "filename": task.filename,
                "file_count": task.file_count,
                "status": task.status,
                "created_at": task.created_at.isoformat()
            }
            for task in upload_tasks.values()
        ]
    }


@app.delete("/upload/task/{task_id}")
async def delete_upload_task(task_id: str):
    task = upload_tasks.get(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.status == "processing":
        raise HTTPException(status_code=400, detail="任务正在处理中，无法删除")
    
    del upload_tasks[task_id]
    
    return {"message": "任务已删除", "task_id": task_id}


@app.options("/upload_documents")
async def upload_documents_options():
    return JSONResponse(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )


@app.middleware("http")
async def add_cors_headers(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        timeout_keep_alive=300,
        limit_max_request_size=100 * 1024 * 1024
    )
