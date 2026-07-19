"""
数据模拟生成器
为所有已注册服务器生成模拟监控数据
"""
import random
import time
import math
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    return pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', 3306)),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'cloud_monitor'),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )


def get_servers():
    """获取所有服务器及其配置"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, name, status, cpu_cores, total_memory, total_disk FROM servers")
            return cursor.fetchall()
    finally:
        conn.close()


def generate_realistic_metric(server, base_values):
    """
    基于正弦波 + 噪声生成逼真的监控数据
    模拟真实的负载波动模式
    """
    t = time.time()

    # CPU 使用率：基础值 + 正弦波动 + 随机噪声
    cpu_base = base_values.get('cpu_base', 30)
    cpu_amp = base_values.get('cpu_amp', 20)
    cpu = cpu_base + cpu_amp * math.sin(t / 300) + random.uniform(-8, 8)
    cpu = max(0, min(100, cpu))

    # 内存使用率：较稳定的基线，缓慢漂移
    mem_base = base_values.get('mem_base', 45)
    mem_amp = base_values.get('mem_amp', 10)
    memory = mem_base + mem_amp * math.sin(t / 600) + random.uniform(-3, 3)
    memory = max(0, min(100, memory))

    # 磁盘使用率：非常缓慢增长
    disk_base = base_values.get('disk_base', 50)
    disk = disk_base + random.uniform(-0.5, 0.5)
    disk = max(0, min(100, disk))

    # 内存实际用量（字节）
    memory_used = int(server['total_memory'] * (memory / 100) * 1024 * 1024)

    # 磁盘实际用量（字节）
    disk_used = int(server['total_disk'] * (disk / 100) * 1024 * 1024)

    # 网络流量（KB/s 模拟）
    net_in = random.randint(100, 10000) + int(3000 * abs(math.sin(t / 120)))
    net_out = random.randint(50, 5000) + int(1500 * abs(math.sin(t / 180)))

    # 进程数
    process_count = random.randint(80, 300)

    return {
        'server_id': server['id'],
        'cpu_usage': round(cpu, 2),
        'memory_usage': round(memory, 2),
        'memory_used': memory_used,
        'disk_usage': round(disk, 2),
        'disk_used': disk_used,
        'disk_total': server['total_disk'] * 1024 * 1024,
        'network_in': net_in,
        'network_out': net_out,
        'process_count': process_count,
    }


def generate_metrics():
    """为每台服务器生成模拟数据并插入数据库"""
    # 每台服务器有不同的负载特征
    server_profiles = {
        'Web-Server-01': {'cpu_base': 40, 'cpu_amp': 25, 'mem_base': 50, 'mem_amp': 12, 'disk_base': 45},
        'DB-Server-01':  {'cpu_base': 35, 'cpu_amp': 20, 'mem_base': 65, 'mem_amp': 8,  'disk_base': 70},
        'App-Server-01': {'cpu_base': 55, 'cpu_amp': 30, 'mem_base': 55, 'mem_amp': 15, 'disk_base': 40},
        'Cache-Server-01': {'cpu_base': 20, 'cpu_amp': 15, 'mem_base': 75, 'mem_amp': 5, 'disk_base': 30},
    }

    servers = get_servers()
    conn = get_db_connection()

    try:
        with conn.cursor() as cursor:
            for server in servers:
                profile = server_profiles.get(server['name'], {
                    'cpu_base': 30, 'cpu_amp': 20, 'mem_base': 45, 'mem_amp': 10, 'disk_base': 50
                })
                metric = generate_realistic_metric(server, profile)

                cursor.execute("""
                    INSERT INTO metrics
                    (server_id, cpu_usage, memory_usage, memory_used, disk_usage,
                     disk_used, disk_total, network_in, network_out, process_count)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    metric['server_id'], metric['cpu_usage'], metric['memory_usage'],
                    metric['memory_used'], metric['disk_usage'], metric['disk_used'],
                    metric['disk_total'], metric['network_in'], metric['network_out'],
                    metric['process_count']
                ))

                # 更新服务器状态（模拟）
                status = 'online'
                if metric['cpu_usage'] > 80 or metric['memory_usage'] > 85:
                    status = 'warning'
                cursor.execute(
                    "UPDATE servers SET status = %s WHERE id = %s",
                    (status, server['id'])
                )

        conn.commit()
    finally:
        conn.close()


def generate_batch(count=100):
    """批量生成历史数据，用于初始化仪表盘"""
    servers = get_servers()
    print(f"开始为 {len(servers)} 台服务器生成 {count} 条历史数据...")

    for i in range(count):
        generate_metrics()
        if (i + 1) % 20 == 0:
            print(f"  已生成 {i + 1}/{count} 条...")
        time.sleep(0.02)  # 稍微间隔，让时间戳有差异

    print(f"[OK] 历史数据生成完成，共 {count * len(servers)} 条记录")


if __name__ == '__main__':
    generate_batch(200)
