import json
import sqlite3
from typing import Dict, Any, List

import redis
from langchain_core.messages import HumanMessage, AIMessage

class MemoryFactory:
    """记忆工厂，支持 Redis 和 SQLite 存储"""
    
    def __init__(self):
        self.redis_client = None
        self.sqlite_connected = False
        self._init_connections()
    
    def _init_connections(self):
        """初始化连接"""
        # 尝试连接 Redis
        try:
            self.redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
            self.redis_client.ping()
        except Exception:
            self.redis_client = None
        
        # 确保 SQLite 连接
        try:
            conn = sqlite3.connect('memory.db')
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversation_history (
                    session_id TEXT PRIMARY KEY,
                    history TEXT
                )
            ''')
            conn.commit()
            conn.close()
            self.sqlite_connected = True
        except Exception:
            self.sqlite_connected = False
    
    def get_memory(self, session_id: str, k: int = 10):
        """获取记忆实例"""
        if self.redis_client:
            return RedisMemory(session_id, self.redis_client, k)
        elif self.sqlite_connected:
            return SQLiteMemory(session_id, k)
        else:
            # 如果都不可用，使用内存记忆
            return InMemoryMemory(k)
    
    def clear_memory(self, session_id: str):
        """清空记忆"""
        if self.redis_client:
            try:
                self.redis_client.delete(f"memory:{session_id}")
            except Exception:
                pass
        
        if self.sqlite_connected:
            try:
                conn = sqlite3.connect('memory.db')
                cursor = conn.cursor()
                cursor.execute('DELETE FROM conversation_history WHERE session_id = ?', (session_id,))
                conn.commit()
                conn.close()
            except Exception:
                pass

class BaseMemory:
    """基础记忆类"""
    
    def __init__(self, k: int = 10):
        self.k = k
        self.messages = []
    
    def add_message(self, message):
        """添加消息"""
        self.messages.append(message)
        # 保持消息数量不超过 k
        if len(self.messages) > self.k:
            self.messages = self.messages[-self.k:]
    
    def get_messages(self):
        """获取消息"""
        return self.messages
    
    def clear(self):
        """清空消息"""
        self.messages = []

class InMemoryMemory(BaseMemory):
    """内存记忆实现"""
    pass

class RedisMemory(BaseMemory):
    """基于 Redis 的记忆实现"""
    
    def __init__(self, session_id: str, redis_client: redis.Redis, k: int = 10):
        super().__init__(k)
        self.session_id = session_id
        self.redis_client = redis_client
        self.key = f"memory:{session_id}"
        self._load_memory()
    
    def _load_memory(self):
        """从 Redis 加载记忆"""
        try:
            data = self.redis_client.get(self.key)
            if data:
                history = json.loads(data)
                # 转换为消息对象
                messages = []
                for msg_data in history:
                    if msg_data['type'] == 'HumanMessage':
                        messages.append(HumanMessage(content=msg_data['content']))
                    elif msg_data['type'] == 'AIMessage':
                        messages.append(AIMessage(content=msg_data['content']))
                self.messages = messages
        except Exception:
            pass
    
    def add_message(self, message):
        """添加消息"""
        super().add_message(message)
        self._save_memory()
    
    def clear(self):
        """清空消息"""
        super().clear()
        self._save_memory()
    
    def _save_memory(self):
        """保存记忆到 Redis"""
        try:
            # 只保存消息内容
            messages_data = []
            for msg in self.messages:
                messages_data.append({
                    'type': msg.__class__.__name__,
                    'content': msg.content
                })
            self.redis_client.set(self.key, json.dumps(messages_data))
        except Exception:
            pass

class SQLiteMemory(BaseMemory):
    """基于 SQLite 的记忆实现"""
    
    def __init__(self, session_id: str, k: int = 10):
        super().__init__(k)
        self.session_id = session_id
        self._load_memory()
    
    def _load_memory(self):
        """从 SQLite 加载记忆"""
        try:
            conn = sqlite3.connect('memory.db')
            cursor = conn.cursor()
            cursor.execute('SELECT history FROM conversation_history WHERE session_id = ?', (self.session_id,))
            result = cursor.fetchone()
            if result:
                history = json.loads(result[0])
                # 转换为消息对象
                messages = []
                for msg_data in history:
                    if msg_data['type'] == 'HumanMessage':
                        messages.append(HumanMessage(content=msg_data['content']))
                    elif msg_data['type'] == 'AIMessage':
                        messages.append(AIMessage(content=msg_data['content']))
                self.messages = messages
            conn.close()
        except Exception:
            pass
    
    def add_message(self, message):
        """添加消息"""
        super().add_message(message)
        self._save_memory()
    
    def clear(self):
        """清空消息"""
        super().clear()
        self._save_memory()
    
    def _save_memory(self):
        """保存记忆到 SQLite"""
        try:
            # 只保存消息内容
            messages_data = []
            for msg in self.messages:
                messages_data.append({
                    'type': msg.__class__.__name__,
                    'content': msg.content
                })
            
            conn = sqlite3.connect('memory.db')
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO conversation_history (session_id, history)
                VALUES (?, ?)
            ''', (self.session_id, json.dumps(messages_data)))
            conn.commit()
            conn.close()
        except Exception:
            pass

# 创建全局记忆工厂实例
memory_factory = MemoryFactory()