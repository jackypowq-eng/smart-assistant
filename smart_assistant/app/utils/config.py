import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Config:
    # 应用配置
    APP_NAME = os.getenv("APP_NAME", "Smart Assistant")
    APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
    
    # 阿里云模型配置
    ALIYUN_MODEL_NAME = os.getenv("ALIYUN_MODEL_NAME", "qwen3-max")
    ALIYUN_API_KEY = os.getenv("ALIYUN_API_KEY")
    ALIYUN_BASE_URL = os.getenv("ALIYUN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    
    # Ollama 本地模型配置
    OLLAMA_MODEL_NAME = os.getenv("OLLAMA_MODEL_NAME", "qwen3.5:4b")
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    # 默认模型提供商
    DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "aliyun")


config = Config()
