import sys, os, time, math, random

sys.path.insert(0, '/app')
os.chdir('/app')

import pymysql

conn = pymysql.connect(
    host='mysql', port=3306, user='root',
    password='cloud_monitor_2026', database='cloud_monitor',
    charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
)

with conn.cursor() as cur:
    cur.execute('SELECT id, name, total_memory, total_disk FROM servers')
    servers = cur.fetchall()
    cur.execute('SELECT COUNT(*) as cnt FROM metrics')
    cnt = cur.fetchone()['cnt']

if cnt > 0:
    print('[OK] already have %d records, skip.' % cnt)
    conn.close()
    sys.exit(0)

profiles = {
    'Web-Server-01': {'cpu_base': 40, 'cpu_amp': 25, 'mem_base': 50, 'mem_amp': 12, 'disk_base': 45},
    'DB-Server-01':  {'cpu_base': 35, 'cpu_amp': 20, 'mem_base': 65, 'mem_amp': 8,  'disk_base': 70},
    'App-Server-01': {'cpu_base': 55, 'cpu_amp': 30, 'mem_base': 55, 'mem_amp': 15, 'disk_base': 40},
    'Cache-Server-01': {'cpu_base': 20, 'cpu_amp': 15, 'mem_base': 75, 'mem_amp': 5,  'disk_base': 30},
}

count = 150
for i in range(count):
    t = time.time() - (count - i) * 30
    with conn.cursor() as cur:
        for s in servers:
            p = profiles.get(s['name'], {'cpu_base': 30, 'cpu_amp': 20, 'mem_base': 45, 'mem_amp': 10, 'disk_base': 50})
            cpu = p['cpu_base'] + p['cpu_amp'] * math.sin(t / 300) + random.uniform(-8, 8)
            cpu = max(0, min(100, cpu))
            mem = p['mem_base'] + p['mem_amp'] * math.sin(t / 600) + random.uniform(-3, 3)
            mem = max(0, min(100, mem))
            disk = p['disk_base'] + random.uniform(-0.5, 0.5)
            disk = max(0, min(100, disk))
            cur.execute(
                'INSERT INTO metrics (server_id, cpu_usage, memory_usage, memory_used, disk_usage, disk_used, disk_total, network_in, network_out, process_count, recorded_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (s['id'], round(cpu, 2), round(mem, 2), int(s['total_memory'] * mem / 100 * 1024 * 1024),
                 round(disk, 2), int(s['total_disk'] * disk / 100 * 1024 * 1024),
                 s['total_disk'] * 1024 * 1024,
                 random.randint(100, 10000) + int(3000 * abs(math.sin(t / 120))),
                 random.randint(50, 5000) + int(1500 * abs(math.sin(t / 180))),
                 random.randint(80, 300),
                 time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t)))
            )
    conn.commit()
    if (i + 1) % 50 == 0:
        print('  %d/%d' % (i + 1, count))
    time.sleep(0.01)

print('[OK] done! %d records created.' % (count * len(servers)))
conn.close()
