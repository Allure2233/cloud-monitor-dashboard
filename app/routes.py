"""
API 路由 - 提供监控数据的 RESTful 接口
"""
import platform
import time
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
import psutil
from app import db
from app.collector import get_disk_usage

api_bp = Blueprint('api', __name__, url_prefix='/api')


# ==================== 服务器管理 ====================

@api_bp.route('/servers', methods=['GET'])
def get_servers():
    """获取所有服务器列表及最新状态（优化版：一次JOIN代替3个子查询）"""
    servers = db.query_all("""
        SELECT s.*,
               m.cpu_usage AS latest_cpu,
               m.memory_usage AS latest_memory,
               m.disk_usage AS latest_disk
        FROM servers s
        LEFT JOIN metrics m ON m.id = (
            SELECT id FROM metrics
            WHERE server_id = s.id
            ORDER BY recorded_at DESC LIMIT 1
        )
        ORDER BY s.name
    """)
    return jsonify({'code': 200, 'data': servers})


@api_bp.route('/servers/<int:server_id>', methods=['GET'])
def get_server_detail(server_id):
    """获取单台服务器详情"""
    server = db.query_one(
        "SELECT * FROM servers WHERE id = %s", (server_id,)
    )
    if not server:
        return jsonify({'code': 404, 'message': '服务器不存在'}), 404
    return jsonify({'code': 200, 'data': server})


# ==================== 监控指标 ====================

@api_bp.route('/metrics/<int:server_id>', methods=['GET'])
def get_metrics(server_id):
    """
    获取指定服务器的监控指标
    参数:
      - minutes: 查询最近多少分钟的数据 (默认60)
    """
    minutes = request.args.get('minutes', 60, type=int)
    minutes = min(max(minutes, 1), 1440)

    since = datetime.now() - timedelta(minutes=minutes)
    metrics = db.query_all("""
        SELECT id, server_id, cpu_usage, memory_usage, memory_used,
               disk_usage, disk_used, disk_total,
               network_in, network_out, process_count,
               recorded_at
        FROM metrics
        WHERE server_id = %s AND recorded_at >= %s
        ORDER BY recorded_at ASC
    """, (server_id, since))

    return jsonify({'code': 200, 'data': metrics})


@api_bp.route('/metrics/<int:server_id>/latest', methods=['GET'])
def get_latest_metrics(server_id):
    """获取服务器最新一条指标"""
    metric = db.query_one("""
        SELECT * FROM metrics
        WHERE server_id = %s
        ORDER BY recorded_at DESC
        LIMIT 1
    """, (server_id,))
    return jsonify({'code': 200, 'data': metric or {}})


@api_bp.route('/metrics/<int:server_id>/summary', methods=['GET'])
def get_metrics_summary(server_id):
    """
    获取服务器指标的统计摘要（平均值、最大值、最小值）
    参数:
      - minutes: 统计区间 (默认60分钟)
    """
    minutes = request.args.get('minutes', 60, type=int)
    minutes = min(max(minutes, 1), 1440)

    since = datetime.now() - timedelta(minutes=minutes)
    summary = db.query_one("""
        SELECT
            ROUND(AVG(cpu_usage), 2) AS avg_cpu,
            ROUND(MAX(cpu_usage), 2) AS max_cpu,
            ROUND(MIN(cpu_usage), 2) AS min_cpu,
            ROUND(AVG(memory_usage), 2) AS avg_memory,
            ROUND(MAX(memory_usage), 2) AS max_memory,
            ROUND(MIN(memory_usage), 2) AS min_memory,
            ROUND(AVG(disk_usage), 2) AS avg_disk,
            ROUND(MAX(disk_usage), 2) AS max_disk,
            ROUND(MIN(disk_usage), 2) AS min_disk,
            ROUND(AVG(network_in), 0) AS avg_net_in,
            ROUND(AVG(network_out), 0) AS avg_net_out,
            COUNT(*) AS data_points
        FROM metrics
        WHERE server_id = %s AND recorded_at >= %s
    """, (server_id, since))

    return jsonify({'code': 200, 'data': summary or {}})


# ==================== 告警管理 ====================

@api_bp.route('/alerts', methods=['GET'])
def get_alerts():
    """
    获取告警记录
    参数:
      - resolved: 0 未解决, 1 已解决, 不传则全部
      - limit: 返回条数 (默认20)
    """
    resolved = request.args.get('resolved', type=int)
    limit = request.args.get('limit', 20, type=int)
    limit = min(limit, 100)

    if resolved is not None:
        alerts = db.query_all("""
            SELECT a.*, s.name AS server_name
            FROM alerts a
            LEFT JOIN servers s ON a.server_id = s.id
            WHERE a.is_resolved = %s
            ORDER BY a.created_at DESC
            LIMIT %s
        """, (resolved, limit))
    else:
        alerts = db.query_all("""
            SELECT a.*, s.name AS server_name
            FROM alerts a
            LEFT JOIN servers s ON a.server_id = s.id
            ORDER BY a.created_at DESC
            LIMIT %s
        """, (limit,))

    return jsonify({'code': 200, 'data': alerts})


@api_bp.route('/alerts', methods=['POST'])
def create_alert():
    """手动创建告警"""
    data = request.get_json() or {}
    required = ['server_id', 'metric_type', 'current_value', 'threshold_value']
    if not all(k in data for k in required):
        return jsonify({'code': 400, 'message': '缺少必要参数'}), 400

    try:
        server_id = int(data['server_id'])
        current_value = float(data['current_value'])
        threshold_value = float(data['threshold_value'])
    except (TypeError, ValueError):
        return jsonify({'code': 400, 'message': '参数类型错误'}), 400

    metric_type = str(data['metric_type'])[:20]
    message = str(data.get('message', ''))[:500]

    alert_id = db.insert_and_get_id("""
        INSERT INTO alerts (server_id, metric_type, current_value, threshold_value, message)
        VALUES (%s, %s, %s, %s, %s)
    """, (server_id, metric_type, current_value, threshold_value, message))

    return jsonify({'code': 201, 'data': {'id': alert_id}})


@api_bp.route('/alerts/<int:alert_id>/resolve', methods=['PUT'])
def resolve_alert(alert_id):
    """标记告警为已解决"""
    affected = db.execute(
        "UPDATE alerts SET is_resolved = 1, resolved_at = NOW() WHERE id = %s AND is_resolved = 0",
        (alert_id,)
    )
    if affected == 0:
        return jsonify({'code': 400, 'message': '告警不存在或已解决'})
    return jsonify({'code': 200, 'message': '告警已解决'})


@api_bp.route('/alerts/evaluate', methods=['POST'])
def evaluate_alerts():
    """
    根据告警规则检测所有服务器最新指标，超阈值自动生成告警
    返回新生成的告警数量
    """
    rules = db.query_all("SELECT * FROM alert_rules WHERE is_active = 1")
    if not rules:
        return jsonify({'code': 200, 'data': {'new_alerts': 0}})

    servers = db.query_all("""
        SELECT s.id AS server_id, s.name AS server_name,
               m.cpu_usage, m.memory_usage, m.disk_usage, m.process_count
        FROM servers s
        LEFT JOIN metrics m ON m.id = (
            SELECT id FROM metrics WHERE server_id = s.id ORDER BY recorded_at DESC LIMIT 1
        )
    """)

    new_alerts = 0
    for server in servers:
        sid = server['server_id']
        metric_map = {
            'cpu': server.get('cpu_usage'),
            'memory': server.get('memory_usage'),
            'disk': server.get('disk_usage'),
            'process': server.get('process_count'),
        }
        for rule in rules:
            if rule['server_id'] is not None and rule['server_id'] != sid:
                continue
            metric_type = rule['metric_type']
            value = metric_map.get(metric_type)
            if value is None:
                continue
            threshold = rule['threshold']
            op = rule['operator']
            triggered = (
                (op == 'gt' and value > threshold) or
                (op == 'lt' and value < threshold) or
                (op == 'eq' and abs(value - threshold) < 0.01)
            )
            if triggered:
                message = f"服务器[{server['server_name']}] {metric_type}={value} 超过阈值 {op} {threshold}"
                existing = db.query_one("""
                    SELECT id FROM alerts
                    WHERE server_id = %s AND metric_type = %s AND is_resolved = 0
                    ORDER BY created_at DESC LIMIT 1
                """, (sid, metric_type))
                if not existing:
                    db.insert_and_get_id("""
                        INSERT INTO alerts (server_id, rule_id, metric_type, current_value, threshold_value, message)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (sid, rule['id'], metric_type, value, threshold, message))
                    new_alerts += 1

    return jsonify({'code': 200, 'data': {'new_alerts': new_alerts}})


# ==================== 系统概览 ====================

@api_bp.route('/overview', methods=['GET'])
def get_overview():
    """获取系统总体概览数据"""
    server_stats = db.query_one("""
        SELECT
            COUNT(*) AS total,
            SUM(status = 'online') AS online,
            SUM(status = 'offline') AS offline,
            SUM(status = 'warning') AS warning
        FROM servers
    """)

    alert_count = db.query_one(
        "SELECT COUNT(*) AS count FROM alerts WHERE is_resolved = 0"
    )

    avg_metrics = db.query_one("""
        SELECT
            ROUND(AVG(m.cpu_usage), 2) AS avg_cpu,
            ROUND(AVG(m.memory_usage), 2) AS avg_memory,
            ROUND(AVG(m.disk_usage), 2) AS avg_disk
        FROM metrics m
        INNER JOIN (
            SELECT server_id, MAX(recorded_at) AS max_time
            FROM metrics GROUP BY server_id
        ) latest ON m.server_id = latest.server_id AND m.recorded_at = latest.max_time
    """)

    return jsonify({
        'code': 200,
        'data': {
            'servers': server_stats,
            'unresolved_alerts': alert_count['count'] if alert_count else 0,
            'avg_metrics': avg_metrics or {},
            'timestamp': datetime.now().isoformat()
        }
    })


# ==================== 健康检查 ====================

@api_bp.route('/health', methods=['GET'])
def health_check():
    """API 健康检查"""
    try:
        db.query_one("SELECT 1")
        db_status = 'ok'
    except Exception:
        db_status = 'error'

    return jsonify({
        'code': 200,
        'data': {
            'status': 'healthy' if db_status == 'ok' else 'degraded',
            'database': db_status,
            'timestamp': time.time()
        }
    })


# ==================== 本机真实数据采集 ====================

@api_bp.route('/local/status', methods=['GET'])
def get_local_status():
    """获取本机（运行 Flask 的机器）的真实系统信息"""
    mem = psutil.virtual_memory()
    disk = get_disk_usage()
    boot_time = datetime.fromtimestamp(psutil.boot_time()).isoformat()

    data = {
        'hostname': platform.node(),
        'system': platform.system(),
        'cpu_cores': psutil.cpu_count(logical=True) or 0,
        'cpu_cores_physical': psutil.cpu_count(logical=False) or 0,
        'total_memory_mb': round(mem.total / (1024 * 1024), 2),
        'total_memory_gb': round(mem.total / (1024 * 1024 * 1024), 2),
        'total_disk_gb': round(disk.total / (1024 * 1024 * 1024), 2) if disk.total > 1 else 0.0,
        'platform': platform.platform(),
        'boot_time': boot_time,
    }
    return jsonify({'code': 200, 'data': data})


@api_bp.route('/local/metrics', methods=['GET'])
def get_local_metrics():
    """获取本机实时监控指标（用 psutil 采集）"""
    cpu_usage = psutil.cpu_percent(interval=1)
    cpu_per_core = psutil.cpu_percent(interval=0, percpu=True)

    cpu_freq = None
    try:
        freq = psutil.cpu_freq()
        if freq:
            cpu_freq = {
                'current': round(freq.current, 0) if freq.current else 0,
                'min': round(freq.min, 0) if freq.min else 0,
                'max': round(freq.max, 0) if freq.max else 0,
            }
    except Exception:
        cpu_freq = None

    mem = psutil.virtual_memory()
    disk = get_disk_usage()
    net = psutil.net_io_counters()
    process_count = len(psutil.pids())

    boot_ts = psutil.boot_time()
    boot_time = datetime.fromtimestamp(boot_ts).isoformat()
    uptime_hours = round((time.time() - boot_ts) / 3600, 2)

    temperature = None
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            for name, entries in temps.items():
                if entries:
                    temperature = round(entries[0].current, 1)
                    break
    except Exception:
        temperature = None

    data = {
        'cpu_usage': round(cpu_usage, 2),
        'cpu_per_core': [round(c, 2) for c in cpu_per_core],
        'memory_usage': round(mem.percent, 2),
        'memory_total_gb': round(mem.total / (1024 ** 3), 2),
        'memory_used_gb': round(mem.used / (1024 ** 3), 2),
        'memory_available_gb': round(mem.available / (1024 ** 3), 2),
        'disk_usage': round(disk.percent, 2),
        'disk_total_gb': round(disk.total / (1024 ** 3), 2),
        'disk_used_gb': round(disk.used / (1024 ** 3), 2),
        'disk_free_gb': round(disk.free / (1024 ** 3), 2),
        'network_sent_mb': round(net.bytes_sent / (1024 ** 2), 2),
        'network_recv_mb': round(net.bytes_recv / (1024 ** 2), 2),
        'process_count': process_count,
        'boot_time': boot_time,
        'uptime_hours': uptime_hours,
        'cpu_freq': cpu_freq,
        'temperature': temperature,
    }
    return jsonify({'code': 200, 'data': data})


@api_bp.route('/local/processes', methods=['GET'])
def get_local_processes():
    """返回占用资源最多的 Top 10 进程"""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
        try:
            info = proc.info
            processes.append({
                'pid': info['pid'],
                'name': info['name'] or 'unknown',
                'cpu': info['cpu_percent'] or 0.0,
                'memory_mb': round(
                    (info['memory_info'].rss / (1024 * 1024)) if info['memory_info'] else 0, 2
                ),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    processes.sort(key=lambda p: (-p['cpu'], -p['memory_mb']))
    top10 = processes[:10]

    return jsonify({'code': 200, 'data': top10})


# ==================== 数据清理 ====================

@api_bp.route('/admin/cleanup', methods=['DELETE'])
def cleanup_old_data():
    """
    删除指定天数之前的历史指标数据（默认使用配置 DATA_RETENTION_DAYS=7）
    参数: days 可覆盖默认天数
    仅供管理用途，实际项目中应由定时任务调用
    """
    from app.config import Config
    days = request.args.get('days', Config.DATA_RETENTION_DAYS, type=int)
    days = max(days, 1)
    cutoff = datetime.now() - timedelta(days=days)

    metrics_deleted = db.execute(
        "DELETE FROM metrics WHERE recorded_at < %s", (cutoff,)
    )
    alerts_deleted = db.execute(
        "DELETE FROM alerts WHERE is_resolved = 1 AND created_at < %s", (cutoff,)
    )

    return jsonify({
        'code': 200,
        'data': {
            'deleted_metrics': metrics_deleted,
            'deleted_resolved_alerts': alerts_deleted,
            'cutoff_date': cutoff.isoformat()
        }
    })
