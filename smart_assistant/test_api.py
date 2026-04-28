import requests

try:
    response = requests.get('http://127.0.0.1:8000/get_documents')
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")
except Exception as e:
    print(f"错误: {e}")
