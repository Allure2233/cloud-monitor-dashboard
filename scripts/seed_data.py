"""
容器内初始化数据脚本
在 Docker Compose 启动时被 start.bat 调用，直接复用 generate_data 模块
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from generate_data import (
    get_db_connection_direct,
    get_servers,
    generate_batch,
)

DB_CONFIG = {
    'host': 'mysql',
    'port': 3306,
    'user': 'root',
    'password': 'cloud_monitor_2026',
    'database': 'cloud_monitor',
}

BATCH_COUNT = 150
INTERVAL_SECONDS = 30


def main():
    conn = get_db_connection_direct(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) as cnt FROM metrics')
            cnt = cur.fetchone()['cnt']

        if cnt > 0:
            print('[OK] already have %d records, skip.' % cnt)
            return 0

        servers = get_servers(conn)
        total = generate_batch(conn, BATCH_COUNT, INTERVAL_SECONDS, servers=servers)
        print('[OK] done! %d records created.' % total)
        return 0
    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())
