"""
数据采集模块
使用 psutil 采集当前服务器的系统指标
"""
import platform
import psutil


def get_disk_usage():
    """
    跨平台获取磁盘使用情况，兼容 Windows 和 Linux
    返回 psutil.disk_usage 的结果对象，失败则返回构造的默认对象
    """
    paths = ['/', 'C:\\', 'D:\\']
    for path in paths:
        try:
            return psutil.disk_usage(path)
        except Exception:
            continue
    class _DefaultDisk:
        percent = 0.0
        used = 0
        total = 1
        free = 0
    return _DefaultDisk()


def get_system_info():
    """获取当前服务器的系统信息"""
    return {
        'hostname': platform.node(),
        'os_name': platform.system(),
        'os_version': platform.version(),
        'os_release': platform.release(),
        'cpu_cores': psutil.cpu_count(logical=True),
        'cpu_cores_physical': psutil.cpu_count(logical=False),
        'total_memory': psutil.virtual_memory().total,
    }


def get_current_metrics():
    """
    采集当前服务器的实时指标
    返回标准化的指标字典
    """
    cpu_percent = psutil.cpu_percent(interval=1)

    mem = psutil.virtual_memory()
    disk = get_disk_usage()

    net = psutil.net_io_counters()
    process_count = len(psutil.pids())

    return {
        'cpu_usage': round(cpu_percent, 2),
        'memory_usage': round(mem.percent, 2),
        'memory_used': mem.used,
        'disk_usage': round(disk.percent, 2),
        'disk_used': disk.used,
        'disk_total': disk.total,
        'network_in': net.bytes_recv,
        'network_out': net.bytes_sent,
        'process_count': process_count,
    }
