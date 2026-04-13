import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Config:
    # 应用配置
    APP_NAME = os.getenv("APP_NAME", "Smart Assistant")
    APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
    
    # 模型配置 - 阿里云百炼模型名（不是端点ID）
    MODEL_NAME = os.getenv("MODEL_NAME", "qwen-turbo")
    
    # API Keys - 注意大小写一致
    ALIYUN_API_KEY = os.getenv("ALIYUN_API_KEY")  # 修正：全大写
    
    # 阿里云百炼 base_url
    BASE_URL = os.getenv("BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    
    # 模型选择逻辑
    @staticmethod
    def get_model_provider():
        """根据环境变量选择模型提供商"""
        if Config.ALIYUN_API_KEY:
            return "aliyun"
        else:
            raise ValueError("No Aliyun API key provided")


config = Config()
