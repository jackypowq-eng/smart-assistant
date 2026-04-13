🚀 启动项目
1️⃣ 安装依赖

pip install -r requirements.txt
2️⃣ 配置 API 密钥
在项目根目录创建 .env 文件，填入：

ALIYUN_API_KEY=你的阿里云API密钥
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_NAME=qwen-plus

3️⃣ 启动服务
uvicorn app.main:app --reload