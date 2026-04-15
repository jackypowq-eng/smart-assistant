import sqlite3

conn = sqlite3.connect('memory.db')
cursor = conn.cursor()

print("--- 查询 uploaded_documents 表 ---")
cursor.execute('SELECT * FROM uploaded_documents')
rows = cursor.fetchall()
print(f"共有 {len(rows)} 条记录")
for row in rows:
    print(f"ID: {row[0]}, 文件名: {row[1]}, 路径: {row[2]}, 大小: {row[3]}, 上传时间: {row[4]}, 已处理: {bool(row[5])}")

conn.close()
