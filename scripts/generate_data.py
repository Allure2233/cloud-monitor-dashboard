"""
数据模拟生成器
为所有已注册服务器生成模拟监控数据
提供可复用的函数供独立脚本和容器内脚本调用
"""
import random
import time
import math
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()


SERVER_PROFILES = {
    'Web-Server-01':   {'cpu_base': 40, 'cpu_amp': 25, 'mem_base': 50, 'mem_amp': 12, 'disk_base': 45},
    'DB-Server-01':    {'cpu_base': 35, 'cpu_amp': 20, 'mem_base': 65, 'mem_amp': 8,  'disk_base': 70},
    'App-Server-01':   {'cpu_base': 55, 'cpu_amp': 30, 'mem_base': 55, 'mem_amp': 15, 'disk_base': 40},
    'Cache-Server-01': {'cpu_base': 20, 'cpu_amp': 15, 'mem_base': 75, 'mem_amp': 5,  'disk_base': 30},
}

DEFAULT_PROFILE = {'cpu_base': 30, 'cpu_amp': 20, 'mem_base': 45, 'mem_amp': 10, 'disk_base': 50}


def get_db_connection_from_env():
    """根据环境变量创建数据库连接"""
    return pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', 3306)),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'cloud_monitor'),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )


def get_db_connection_direct(host, port, user, password, database):
    """直接使用参数创建数据库连接（供容器内脚本使用）"""
    return pymysql.connect(
        host=host, port=port, user=user, password=password, database=database,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )


def get_servers(conn):
    """获取所有服务器及其配置"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, name, status, cpu_cores, total_memory, total_disk FROM servers")
        return cursor.fetchall()


def generate_realistic_metric(server, base_values, t=None):
    """
    基于正弦波 + 噪声生成逼真的监控数据
    模拟真实的负载波动模式。t 为时间戳，不传则使用当前时间。
    """
    if t is None:
        t = time.time()

    cpu_base = base_values.get('cpu_base', DEFAULT_PROFILE['cpu_base'])
    cpu_amp = base_values.get('cpu_amp', DEFAULT_PROFILE['cpu_amp'])
    cpu = cpu_base + cpu_amp * math.sin(t / 300) + random.uniform(-8, 8)
    cpu = max(0.0, min(100.0, cpu))

    mem_base = base_values.get('mem_base', DEFAULT_PROFILE['mem_base'])
    mem_amp = base_values.get('mem_amp', DEFAULT_PROFILE['mem_amp'])
    memory = mem_base + mem_amp * math.sin(t / 600) + random.uniform(-3, 3)
    memory = max(0.0, min(100.0, memory))

    disk_base = base_values.get('disk_base', DEFAULT_PROFILE['disk_base'])
    disk = disk_base + random.uniform(-0.5, 0.5)
    disk = max(0.0, min(100.0, disk))

    memory_used = int(server['total_memory'] * (memory / 100) * 1024 * 1024)
    disk_used = int(server['total_disk'] * (disk / 100) * 1024 * 1024)

    net_in = random.randint(100, 10000) + int(3000 * abs(math.sin(t / 120)))
    net_out = random.randint(50, 5000) + int(1500 * abs(math.sin(t / 180)))

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
        'recorded_at_ts': t,
    }


def _determine_status(cpu, memory):
    if cpu > 80 or memory > 85:
        return 'warning'
    return 'online'


def insert_single_metric(conn, server, metric, recorded_at_str=None):
    """插入一条监控指标并更新服务器状态。返回新指标 ID。"""
    if recorded_at_str is None:
        recorded_at_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(metric['recorded_at_ts']))

    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO metrics
            (server_id, cpu_usage, memory_usage, memory_used, disk_usage,
             disk_used, disk_total, network_in, network_out, process_count, recorded_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            metric['server_id'], metric['cpu_usage'], metric['memory_usage'],
            metric['memory_used'], metric['disk_usage'], metric['disk_used'],
            metric['disk_total'], metric['network_in'], metric['network_out'],
            metric['process_count'], recorded_at_str
        ))
        new_id = cursor.lastrowid

        new_status = _determine_status(metric['cpu_usage'], metric['memory_usage'])
        cursor.execute(
            "UPDATE servers SET status = %s WHERE id = %s",
            (new_status, server['id'])
        )
    conn.commit()
    return new_id


def generate_current_snapshot(conn, servers=None, profiles=None):
    """为所有服务器生成并插入一条当前时刻的模拟数据"""
    if servers is None:
        servers = get_servers(conn)
    if profiles is None:
        profiles = SERVER_PROFILES

    for server in servers:
        profile = profiles.get(server['name'], DEFAULT_PROFILE)
        metric = generate_realistic_metric(server, profile)
        insert_single_metric(conn, server, metric)


def generate_batch(conn, count=100, interval_seconds=30, servers=None, profiles=None):
    """
    批量生成历史数据（用于初始化仪表盘）
    count: 每台服务器生成的记录数
    interval_seconds: 相邻记录之间的时间间隔（秒）
    """
    if servers is None:
        servers = get_servers(conn)
    if profiles is None:
        profiles = SERVER_PROFILES

    n_servers = len(servers)
    print(f"开始为 {n_servers} 台服务器生成 {count} 条历史数据...")

    total_inserted = 0
    for i in range(count):
        t = time.time() - (count - i) * interval_seconds
        recorded_at_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t))
        with conn.cursor() as cursor:
            for server in servers:
                profile = profiles.get(server['name'], DEFAULT_PROFILE)
                metric = generate_realistic_metric(server, profile, t=t)
                cursor.execute("""
                    INSERT INTO metrics
                    (server_id, cpu_usage, memory_usage, memory_used, disk_usage,
                     disk_used, disk_total, network_in, network_out, process_count, recorded_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    metric['server_id'], metric['cpu_usage'], metric['memory_usage'],
                    metric['memory_used'], metric['disk_usage'], metric['disk_used'],
                    metric['disk_total'], metric['network_in'], metric['network_out'],
                    metric['process_count'], recorded_at_str
                ))
                total_inserted += 1

            if i == count - 1:
                for server in servers:
                    profile = profiles.get(server['name'], DEFAULT_PROFILE)
                    metric = generate_realistic_metric(server, profile, t=t)
                    cursor.execute(
                        "UPDATE servers SET status = %s WHERE id = %s",
                        (_determine_status(metric['cpu_usage'], metric['memory_usage']), server['id'])
                    )
        conn.commit()
        if (i + 1) % 50 == 0:
            print(f"  已生成 {i + 1}/{count} 批...")
        time.sleep(0.01)

    print(f"[OK] 历史数据生成完成，共 {total_inserted} 条记录")
    return total_inserted


def generate_metrics_once(conn):
    """兼容旧接口：为所有服务器生成一条当前数据"""
    generate_current_snapshot(conn)


if __name__ == '__main__':
    conn = get_db_connection_from_env()
    try:
        generate_batch(conn, 200)
    finally:
        conn.close()
