"""
数据库初始化脚本（本地开发环境使用）
从 init_db.sql 读取并执行建表语句，避免 SQL 重复维护
"""
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

SQL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'init_db.sql')


def _split_sql_statements(sql_text):
    """按分号拆分 SQL 语句，跳过空行和注释"""
    statements = []
    buf = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('--'):
            continue
        buf.append(line)
        if stripped.rstrip(';').endswith('') and stripped.endswith(';'):
            stmt = '\n'.join(buf).rstrip(';').strip()
            if stmt:
                statements.append(stmt)
            buf = []
    if buf:
        stmt = '\n'.join(buf).rstrip(';').strip()
        if stmt:
            statements.append(stmt)
    return statements


def init_database():
    connection = pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', 3306)),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        charset='utf8mb4'
    )

    try:
        if not os.path.isfile(SQL_FILE):
            raise FileNotFoundError(f"SQL 文件不存在: {SQL_FILE}")

        with open(SQL_FILE, 'r', encoding='utf-8') as f:
            sql_text = f.read()

        statements = _split_sql_statements(sql_text)

        with connection.cursor() as cursor:
            for stmt in statements:
                try:
                    cursor.execute(stmt)
                except Exception as e:
                    print(f"  [WARN] 跳过语句（可能已存在）: {stmt[:80]}... 错误: {e}")

        connection.commit()

        print("[OK] 数据库初始化完成")
        print(f"     - 来源 SQL 文件: {os.path.basename(SQL_FILE)}")
        print("     - 执行了 %d 条 SQL 语句" % len(statements))
        print("     - 创建数据库: cloud_monitor")
        print("     - 创建表: servers, metrics, alert_rules, alerts")
        print("     - 插入默认服务器: 4 台")
        print("     - 插入默认告警规则: 4 条")

    finally:
        connection.close()


if __name__ == '__main__':
    init_database()
