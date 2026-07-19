-- Cloud Monitor Dashboard 数据库初始化 SQL
-- 用于 Docker 环境的自动初始化

CREATE DATABASE IF NOT EXISTS cloud_monitor
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE cloud_monitor;

-- 服务器信息表
CREATE TABLE IF NOT EXISTS servers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    ip_address VARCHAR(45) NOT NULL,
    status ENUM('online', 'offline', 'warning') DEFAULT 'online',
    os_info VARCHAR(200) DEFAULT '',
    cpu_cores INT DEFAULT 0,
    total_memory BIGINT DEFAULT 0,
    total_disk BIGINT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 监控指标记录表
CREATE TABLE IF NOT EXISTS metrics (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    server_id INT NOT NULL,
    cpu_usage FLOAT NOT NULL,
    memory_usage FLOAT NOT NULL,
    memory_used BIGINT NOT NULL,
    disk_usage FLOAT NOT NULL,
    disk_used BIGINT NOT NULL,
    disk_total BIGINT NOT NULL,
    network_in BIGINT DEFAULT 0,
    network_out BIGINT DEFAULT 0,
    process_count INT DEFAULT 0,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE,
    INDEX idx_server_time (server_id, recorded_at),
    INDEX idx_recorded_at (recorded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 告警规则表
CREATE TABLE IF NOT EXISTS alert_rules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    server_id INT,
    metric_type ENUM('cpu', 'memory', 'disk', 'process') NOT NULL,
    threshold FLOAT NOT NULL,
    operator ENUM('gt', 'lt', 'eq') DEFAULT 'gt',
    is_active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 告警记录表
CREATE TABLE IF NOT EXISTS alerts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    server_id INT NOT NULL,
    rule_id INT,
    metric_type VARCHAR(20) NOT NULL,
    current_value FLOAT NOT NULL,
    threshold_value FLOAT NOT NULL,
    message TEXT,
    is_resolved TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE,
    FOREIGN KEY (rule_id) REFERENCES alert_rules(id) ON DELETE SET NULL,
    INDEX idx_resolved (is_resolved),
    INDEX idx_server_alerts (server_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 插入默认服务器
INSERT IGNORE INTO servers (name, ip_address, status, os_info, cpu_cores, total_memory, total_disk)
VALUES
    ('Web-Server-01', '192.168.1.101', 'online', 'Ubuntu 22.04 LTS', 8, 16384, 512000),
    ('DB-Server-01', '192.168.1.102', 'online', 'CentOS 8 Stream', 16, 32768, 1024000),
    ('App-Server-01', '192.168.1.103', 'warning', 'Debian 12', 4, 8192, 256000),
    ('Cache-Server-01', '192.168.1.104', 'online', 'Alpine Linux 3.18', 4, 8192, 128000);

-- 插入默认告警规则
INSERT IGNORE INTO alert_rules (server_id, metric_type, threshold, operator)
VALUES
    (NULL, 'cpu', 85.0, 'gt'),
    (NULL, 'memory', 90.0, 'gt'),
    (NULL, 'disk', 90.0, 'gt'),
    (NULL, 'process', 500, 'gt');
