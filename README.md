# Smart Assistant - 智能助手

基于 FastAPI 和 LangChain 构建的智能 AI 助手，支持阿里云 DashScope 和本地 Ollama 模型。

## 功能特性

- 🤖 支持多模型切换（阿里云 / Ollama 本地）
- 🌐 RESTful API 接口
- � Web 聊天界面，可实时切换模型
- ⚙️ 配置化管理

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

在项目根目录创建 `.env` 文件：

```env
# 阿里云配置
ALIYUN_API_KEY=你的阿里云API密钥
ALIYUN_MODEL_NAME=qwen-turbo
ALIYUN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# Ollama 本地模型配置
OLLAMA_MODEL_NAME=llama3.2
OLLAMA_BASE_URL=http://localhost:11434

# 默认模型提供商 (aliyun/ollama)
DEFAULT_PROVIDER=aliyun
```

### 3. 启动服务

```bash
uvicorn app.main:app --reload
```

## 使用说明

### Web 界面

访问 `http://localhost:8000/chat-page`

- 在页面上方可以选择使用 **阿里云** 或 **Ollama 本地模型**
- 每次对话会显示使用的模型来源

### API 接口

#### 聊天接口

```bash
POST /chat
Content-Type: application/json

{
  "message": "你好",
  "provider": "aliyun"  // 可选，默认 aliyun，可选值: aliyun, ollama
}
```

#### 获取服务信息

```bash
GET /
```

返回当前支持的模型列表和默认配置。

## Ollama 本地模型设置

1. 安装 Ollama：[https://ollama.com](https://ollama.com)

2. 拉取模型：

```bash
ollama pull llama3.2
```

3. 确保 Ollama 服务运行在默认端口 11434

## 项目结构

```
smart_assistant/
├── app/
│   ├── main.py          # FastAPI 应用入口
│   ├── agent/           # AI Agent 核心逻辑
│   │   ├── core.py      # SmartAgent 实现
│   │   ├── prompts.py   # 提示词模板
│   │   └── tools.py     # 工具函数
│   └── utils/
│       └── config.py    # 配置管理
├── templates/
│   └── chat.html        # 聊天页面
├── requirements.txt     # 依赖
└── README.md           # 说明文档
```

## 配置说明

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `ALIYUN_API_KEY` | 阿里云 DashScope API 密钥 | - |
| `ALIYUN_MODEL_NAME` | 阿里云模型名称 | qwen-turbo |
| `ALIYUN_BASE_URL` | 阿里云 API 地址 | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| `OLLAMA_MODEL_NAME` | Ollama 本地模型名称 | qwen3.5:4b |
| `OLLAMA_BASE_URL` | Ollama 服务地址 | http://localhost:11434 |
| `DEFAULT_PROVIDER` | 默认模型提供商 | aliyun |
