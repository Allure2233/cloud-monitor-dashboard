/**
 * PRTS MONITOR SYSTEM v2.0 // RHODES ISLAND
 * 前端 JavaScript - 鹰角网络风格 (Hypergryph Style)
 *
 * 负责：数据获取、图表渲染、本机监控、页面交互
 */

// ==================== 全局变量 ====================
let selectedServer = null;
let refreshTimer = null;
const REFRESH_INTERVAL = 10000; // 10秒自动刷新

// 鹰角风格配色常量
const COLORS = {
    blue: '#00b8ff',
    cyan: '#00e5ff',
    red: '#ff4d4a',
    green: '#00c853',
    yellow: '#ffd600',
    bgDark: '#0d0d0d',
    bgCard: '#141414',
    border: '#2a2a2a',
    borderLight: '#333333',
    textBright: '#e0e0e0',
    textNeutral: '#888888',
    textDim: '#555555',
};

// ECharts 实例集合
const charts = {
    gaugeCpu: null,
    gaugeMemory: null,
    gaugeDisk: null,
    gaugeNetwork: null,
    gaugeLocalCpu: null,
    gaugeLocalMem: null,
    cpu: null,
    memory: null,
    disk: null,
    network: null,
};

// ==================== 工具函数 ====================

/** 格式化时间字符串 */
function formatTime(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

/** 格式化字节数 */
function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i];
}

/** 格式化运行时间（秒 -> 可读） */
function formatUptime(seconds) {
    if (!seconds || seconds <= 0) return '--:--';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (h > 0) return h + 'h ' + m + 'm';
    return m + 'm';
}

/** 获取状态对应的 CSS 类名 */
function getStatusClass(status) {
    const map = { online: 'online', offline: 'offline', warning: 'warning' };
    return map[status] || 'offline';
}

/** 获取状态显示文本 */
function getStatusText(status) {
    const map = { online: 'ONLINE', offline: 'OFFLINE', warning: 'WARNING' };
    return map[status] || status;
}

/** 根据数值获取进度条颜色级别 */
function getLevelClass(value) {
    if (value < 60) return 'level-low';
    if (value < 85) return 'level-mid';
    return 'level-high';
}

/** 根据数值获取表格进度条填充类名 */
function getFillClass(value) {
    if (value < 60) return 'fill-low';
    if (value < 85) return 'fill-mid';
    return 'fill-high';
}

/** JSON 请求封装 */
async function fetchJSON(url) {
    try {
        const resp = await fetch(url);
        return await resp.json();
    } catch (e) {
        console.error('[PRTS] API 请求失败:', url, e);
        return null;
    }
}

// ==================== 时钟 ====================

/** 更新右上角时钟显示 */
function updateClock() {
    const el = document.getElementById('current-time');
    if (el) {
        const now = new Date();
        const h = String(now.getHours()).padStart(2, '0');
        const m = String(now.getMinutes()).padStart(2, '0');
        const s = String(now.getSeconds()).padStart(2, '0');
        el.textContent = h + ':' + m + ':' + s;
    }
}

// ==================== 分段进度条渲染 ====================

/**
 * 更新分段式进度条
 * @param {string} barId - 进度条容器的 DOM id
 * @param {number} value - 0-100 的百分比值
 */
function updateSegmentedBar(barId, value) {
    const container = document.getElementById(barId);
    if (!container) return;
    const fill = container.querySelector('.progress-segments');
    if (!fill) return;
    fill.style.width = value.toFixed(1) + '%';
    // 更新颜色级别
    fill.className = 'progress-segments ' + getLevelClass(value);
}

// ==================== 本机状态 ====================

/** 加载本机系统静态信息 */
async function loadLocalStatus() {
    const res = await fetchJSON('/api/local/status');
    if (!res) return;

    const data = res.code !== undefined ? res.data : res;
    if (!data) return;

    // 更新主机名显示
    const hostEl = document.getElementById('local-hostname');
    if (hostEl) hostEl.textContent = (data.hostname || 'UNKNOWN') + ' // ' + (data.system || '-');

    const coresEl = document.getElementById('local-cores');
    if (coresEl) coresEl.textContent = (data.cpu_cores || '-') + ' CORES // ' + (data.total_memory_gb || '-') + 'GB RAM';
}

/** 加载本机实时指标 */
async function loadLocalMetrics() {
    const res = await fetchJSON('/api/local/metrics');
    if (!res) return;

    const data = res.code !== undefined ? res.data : res;
    if (!data) return;

    // 更新进度条 - 使用正确的字段名
    const cpuVal = data.cpu_usage || 0;
    const memVal = data.memory_usage || 0;
    const diskVal = data.disk_usage || 0;

    updateSegmentedBar('local-cpu-bar', cpuVal);
    updateSegmentedBar('local-mem-bar', memVal);
    updateSegmentedBar('local-disk-bar', diskVal);

    // 更新数值文本
    document.getElementById('local-cpu-value').textContent = cpuVal.toFixed(1) + ' %';
    document.getElementById('local-mem-value').textContent = memVal.toFixed(1) + ' %';
    document.getElementById('local-disk-value').textContent = diskVal.toFixed(1) + ' %';
    document.getElementById('local-proc-value').textContent = data.process_count || '---';

    // 运行时间
    const uptimeEl = document.getElementById('local-uptime-value');
    if (uptimeEl && data.uptime_hours !== undefined) {
        const hrs = data.uptime_hours;
        if (hrs >= 24) {
            uptimeEl.textContent = Math.floor(hrs / 24) + 'D ' + Math.floor(hrs % 24) + 'H';
        } else {
            uptimeEl.textContent = hrs.toFixed(1) + ' HR';
        }
    }

    // 网络流量 (MB)
    const netEl = document.getElementById('local-net-value');
    if (netEl && data.network_sent_mb !== undefined) {
        netEl.textContent = '\u2191' + data.network_sent_mb.toFixed(1) + 'MB \u2193' + data.network_recv_mb.toFixed(1) + 'MB';
    }

    // 更新本机环形图
    if (charts.gaugeLocalCpu) {
        charts.gaugeLocalCpu.setOption({
            series: [{ data: [{ value: cpuVal, name: 'LOCAL CPU' }] }]
        });
    }
    if (charts.gaugeLocalMem) {
        charts.gaugeLocalMem.setOption({
            series: [{ data: [{ value: memVal, name: 'LOCAL MEM' }] }]
        });
    }
}

/** 加载本机进程列表 */
async function loadLocalProcesses() {
    const res = await fetchJSON('/api/local/processes');
    if (!res) return;

    let processes = [];
    if (res.code !== undefined) {
        processes = res.data || [];
    } else {
        processes = Array.isArray(res) ? res : [];
    }

    const tbody = document.getElementById('local-process-body');
    if (!tbody) return;

    if (processes.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="cell-loading">NO DATA // 无进程数据</td></tr>';
        return;
    }

    // 只显示前 15 个进程（按 CPU 排序）
    const sorted = processes
        .sort((a, b) => (b.cpu || 0) - (a.cpu || 0))
        .slice(0, 15);

    tbody.innerHTML = sorted.map(p => {
        const pid = p.pid || '-';
        const name = p.name || '-';
        const cpu = (p.cpu || 0).toFixed(1) + '%';
        const mem = p.memory_mb ? p.memory_mb.toFixed(1) + ' MB' : '-';
        const memPct = mem;

        return '<tr>' +
            '<td>' + pid + '</td>' +
            '<td>' + name + '</td>' +
            '<td>' + cpu + '</td>' +
            '<td>' + memPct + '</td>' +
            '<td><span class="proc-status running">ACTIVE</span></td>' +
            '</tr>';
    }).join('');
}

// ==================== 概览数据 ====================

/** 加载概览统计 */
async function loadOverview() {
    const res = await fetchJSON('/api/overview');
    if (!res || res.code !== 200) return;

    const data = res.data;
    document.getElementById('total-servers').textContent = data.servers?.total || 0;
    document.getElementById('online-count').textContent = (data.servers?.online || 0) + ' ONLINE';
    document.getElementById('warning-count').textContent = (data.servers?.warning || 0) + ' WARNING';
    document.getElementById('avg-cpu').textContent = (data.avg_metrics?.avg_cpu || 0) + '%';
    document.getElementById('avg-memory').textContent = (data.avg_metrics?.avg_memory || 0) + '%';
    document.getElementById('alert-count').textContent = data.unresolved_alerts || 0;
}

// ==================== 服务器列表与迷你卡片 ====================

/** 加载服务器数据，渲染表格和迷你卡片 */
async function loadServers() {
    const res = await fetchJSON('/api/servers');
    if (!res || res.code !== 200) return;

    const servers = res.data;

    // 更新下拉选择器
    const select = document.getElementById('server-select');
    select.innerHTML = '';
    servers.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = s.name + ' // ' + s.ip_address;
        select.appendChild(opt);
    });

    // 默认选中第一台
    if (servers.length > 0 && !selectedServer) {
        selectedServer = servers[0].id;
        select.value = selectedServer;
    }

    // ---- 渲染迷你卡片 ----
    renderMiniCards(servers);

    // ---- 渲染服务器表格 ----
    renderServerTable(servers);
}

/** 渲染服务器迷你卡片 */
function renderMiniCards(servers) {
    const grid = document.getElementById('server-cards-grid');
    if (!grid) return;

    if (servers.length === 0) {
        grid.innerHTML = '<div class="mini-card mini-card-placeholder"><span class="placeholder-text">NO DATA</span></div>';
        return;
    }

    grid.innerHTML = servers.map(s => {
        const status = s.status || 'offline';
        const statusClass = getStatusClass(status);
        const statusText = getStatusText(status);
        const cpu = s.latest_cpu || 0;
        const mem = s.latest_memory || 0;
        const disk = s.latest_disk || 0;

        return '<div class="mini-card">' +
            '<div class="mini-card-header">' +
                '<span class="mini-card-name">\u25C6 ' + s.name + '</span>' +
                '<span class="mini-card-status">' +
                    '<span class="dot ' + statusClass + '"></span>' +
                    '<span class="status-text ' + statusClass + '">' + statusText + '</span>' +
                '</span>' +
            '</div>' +
            '<span class="mini-card-ip">' + s.ip_address + '</span>' +
            '<div class="mini-card-metrics">' +
                '<span class="mini-card-metric">CPU: <span class="val">' + cpu.toFixed(1) + '%</span></span>' +
                '<span class="mini-card-metric">MEM: <span class="val">' + mem.toFixed(1) + '%</span></span>' +
                '<span class="mini-card-metric">DISK: <span class="val">' + disk.toFixed(1) + '%</span></span>' +
            '</div>' +
        '</div>';
    }).join('');
}

/** 渲染服务器状态表格 */
function renderServerTable(servers) {
    const tbody = document.getElementById('server-table-body');
    if (!tbody) return;

    tbody.innerHTML = servers.map(s => {
        const status = s.status || 'offline';
        const cpu = s.latest_cpu || 0;
        const mem = s.latest_memory || 0;
        const disk = s.latest_disk || 0;

        return '<tr>' +
            '<td>\u25A0 ' + s.name + '</td>' +
            '<td>' + s.ip_address + '</td>' +
            '<td><span class="status-badge ' + getStatusClass(status) + '">' + getStatusText(status) + '</span></td>' +
            '<td>' + buildTableProgress(cpu) + '</td>' +
            '<td>' + buildTableProgress(mem) + '</td>' +
            '<td>' + buildTableProgress(disk) + '</td>' +
            '<td>' + (s.os_info || '-') + '</td>' +
            '</tr>';
    }).join('');
}

/** 构建表格内的小进度条 HTML */
function buildTableProgress(value) {
    const fillClass = getFillClass(value);
    return '<div class="table-progress">' +
        '<div class="table-progress-bar">' +
            '<div class="table-progress-fill ' + fillClass + '" style="width:' + value.toFixed(1) + '%"></div>' +
        '</div>' +
        '<span class="table-progress-val">' + value.toFixed(1) + '%</span>' +
    '</div>';
}

// ==================== ECharts 主题配置（鹰角风格） ====================

/** 鹰角风格的环形图配置 */
function createGaugeOption(value, color) {
    return {
        series: [{
            type: 'gauge',
            startAngle: 220,
            endAngle: -40,
            min: 0,
            max: 100,
            radius: '90%',
            progress: {
                show: true,
                width: 10,
                itemStyle: {
                    color: color,
                    // 无圆角端头
                    cap: 'butt',
                }
            },
            axisLine: {
                lineStyle: {
                    width: 10,
                    color: [[1, COLORS.border]]
                }
            },
            axisTick: { show: false },
            splitLine: { show: false },
            axisLabel: { show: false },
            pointer: { show: false },
            title: { show: false },
            detail: {
                valueAnimation: true,
                fontSize: 20,
                fontFamily: 'Share Tech Mono, Consolas, monospace',
                fontWeight: 400,
                color: color,
                formatter: '{value}%',
                offsetCenter: [0, '10%']
            },
            data: [{ value: value, name: '' }]
        }]
    };
}

/** 鹰角风格的网络仪表盘 */
function createNetworkGaugeOption(inVal, outVal) {
    return {
        series: [{
            type: 'gauge',
            startAngle: 220,
            endAngle: -40,
            min: 0,
            max: 100,
            radius: '90%',
            progress: {
                show: true,
                width: 10,
                itemStyle: { color: COLORS.blue, cap: 'butt' }
            },
            axisLine: {
                lineStyle: { width: 10, color: [[1, COLORS.border]] }
            },
            axisTick: { show: false },
            splitLine: { show: false },
            axisLabel: { show: false },
            pointer: { show: false },
            title: { show: false },
            detail: {
                valueAnimation: true,
                fontSize: 13,
                fontFamily: 'Share Tech Mono, Consolas, monospace',
                fontWeight: 400,
                color: COLORS.blue,
                formatter: function () {
                    return '\u2191 ' + inVal + '\n\u2193 ' + outVal;
                },
                offsetCenter: [0, '10%']
            },
            data: [{ value: 50 }]
        }]
    };
}

/** 初始化所有环形图 */
function initGauges() {
    charts.gaugeCpu = echarts.init(document.getElementById('gauge-cpu'));
    charts.gaugeMemory = echarts.init(document.getElementById('gauge-memory'));
    charts.gaugeDisk = echarts.init(document.getElementById('gauge-disk'));
    charts.gaugeNetwork = echarts.init(document.getElementById('gauge-network'));
    charts.gaugeLocalCpu = echarts.init(document.getElementById('gauge-local-cpu'));
    charts.gaugeLocalMem = echarts.init(document.getElementById('gauge-local-mem'));

    // 服务器指标环形图
    charts.gaugeCpu.setOption(createGaugeOption(0, COLORS.green));
    charts.gaugeMemory.setOption(createGaugeOption(0, COLORS.yellow));
    charts.gaugeDisk.setOption(createGaugeOption(0, COLORS.blue));
    charts.gaugeNetwork.setOption(createNetworkGaugeOption(0, 0));

    // 本机环形图
    charts.gaugeLocalCpu.setOption(createGaugeOption(0, COLORS.cyan));
    charts.gaugeLocalMem.setOption(createGaugeOption(0, COLORS.cyan));
}

/** 更新服务器指标环形图 */
function updateGauges(cpu, memory, disk, netIn, netOut) {
    charts.gaugeCpu.setOption({ series: [{ data: [{ value: cpu, name: '' }] }] });
    charts.gaugeMemory.setOption({ series: [{ data: [{ value: memory, name: '' }] }] });
    charts.gaugeDisk.setOption({ series: [{ data: [{ value: disk, name: '' }] }] });
    charts.gaugeNetwork.setOption({
        series: [{
            detail: {
                formatter: function () { return '\u2191 ' + netIn + '\n\u2193 ' + netOut; }
            }
        }]
    });
}

// ==================== 趋势图表 ====================

/** 鹰角风格的折线图配置 */
function createLineOption(title, times, values, color, areaColor) {
    return {
        tooltip: {
            trigger: 'axis',
            backgroundColor: COLORS.bgCard,
            borderColor: COLORS.borderLight,
            borderWidth: 1,
            textStyle: {
                color: COLORS.textBright,
                fontFamily: 'Share Tech Mono, Consolas, monospace',
                fontSize: 12,
            },
            formatter: function (params) {
                const p = params[0];
                return title + '<br/>' + p.name + ' // ' + p.value + '%';
            }
        },
        grid: { top: 20, right: 16, bottom: 28, left: 48 },
        xAxis: {
            type: 'category',
            data: times,
            axisLabel: {
                color: COLORS.textDim,
                fontSize: 10,
                fontFamily: 'Share Tech Mono, Consolas, monospace',
                interval: 'auto',
                rotate: 30,
            },
            axisLine: { lineStyle: { color: COLORS.border } },
            axisTick: { show: false },
        },
        yAxis: {
            type: 'value',
            min: 0,
            max: 100,
            axisLabel: {
                color: COLORS.textDim,
                fontSize: 10,
                fontFamily: 'Share Tech Mono, Consolas, monospace',
                formatter: '{value}%'
            },
            splitLine: { lineStyle: { color: COLORS.border, type: 'dashed' } },
            axisLine: { show: false },
            axisTick: { show: false },
        },
        series: [{
            type: 'line',
            data: values,
            smooth: false,  // 鹰角风格：不用平滑曲线，用折线
            symbol: 'none',
            lineStyle: {
                color: color,
                width: 1.5,
                // 微弱的发光效果
                shadowColor: color,
                shadowBlur: 4,
            },
            areaStyle: {
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    { offset: 0, color: areaColor },
                    { offset: 1, color: 'rgba(0,0,0,0)' }
                ])
            },
            // 告警线
            markLine: {
                silent: true,
                symbol: 'none',
                data: [{ yAxis: 85 }],
                lineStyle: {
                    color: COLORS.red,
                    type: 'dashed',
                    width: 1,
                },
                label: {
                    show: true,
                    position: 'insideEndTop',
                    color: COLORS.red,
                    fontSize: 9,
                    fontFamily: 'Share Tech Mono, Consolas, monospace',
                    formatter: 'ALERT // 85%',
                }
            }
        }]
    };
}

/** 初始化趋势图表 */
function initCharts() {
    charts.cpu = echarts.init(document.getElementById('chart-cpu'));
    charts.memory = echarts.init(document.getElementById('chart-memory'));
    charts.disk = echarts.init(document.getElementById('chart-disk'));
    charts.network = echarts.init(document.getElementById('chart-network'));

    // 空数据初始化（鹰角风格配色）
    const emptyOption = {
        grid: { top: 20, right: 16, bottom: 28, left: 48 },
        xAxis: {
            type: 'category',
            data: [],
            axisLabel: { color: COLORS.textDim, fontSize: 10 },
            axisLine: { lineStyle: { color: COLORS.border } },
            axisTick: { show: false },
        },
        yAxis: {
            type: 'value',
            axisLabel: { color: COLORS.textDim, fontSize: 10 },
            splitLine: { lineStyle: { color: COLORS.border, type: 'dashed' } },
            axisLine: { show: false },
            axisTick: { show: false },
        },
        series: [{ type: 'line', data: [] }]
    };

    charts.cpu.setOption(emptyOption);
    charts.memory.setOption(emptyOption);
    charts.disk.setOption(emptyOption);
    charts.network.setOption(emptyOption);
}

/** 更新趋势图表数据 */
function updateCharts(metrics) {
    if (!metrics || metrics.length === 0) return;

    // 数据采样：如果数据点过多，进行降采样
    let sampled = metrics;
    if (metrics.length > 120) {
        const step = Math.ceil(metrics.length / 120);
        sampled = metrics.filter(function (_, i) { return i % step === 0; });
    }

    const times = sampled.map(function (m) { return formatTime(m.recorded_at); });
    const cpuValues = sampled.map(function (m) { return m.cpu_usage; });
    const memValues = sampled.map(function (m) { return m.memory_usage; });
    const diskValues = sampled.map(function (m) { return m.disk_usage; });
    const netInValues = sampled.map(function (m) { return m.network_in; });
    const netOutValues = sampled.map(function (m) { return m.network_out; });

    // CPU 趋势 —— 绿色线条
    charts.cpu.setOption(createLineOption(
        'CPU // 处理器', times, cpuValues,
        COLORS.green, 'rgba(0,200,83,0.1)'
    ));

    // 内存趋势 —— 黄色线条
    charts.memory.setOption(createLineOption(
        'MEMORY // 内存', times, memValues,
        COLORS.yellow, 'rgba(255,214,0,0.1)'
    ));

    // 磁盘趋势 —— 蓝色线条
    charts.disk.setOption(createLineOption(
        'DISK // 磁盘', times, diskValues,
        COLORS.blue, 'rgba(0,184,255,0.1)'
    ));

    // 网络趋势 —— 双线（入站蓝色 + 出站青色）
    charts.network.setOption({
        tooltip: {
            trigger: 'axis',
            backgroundColor: COLORS.bgCard,
            borderColor: COLORS.borderLight,
            borderWidth: 1,
            textStyle: {
                color: COLORS.textBright,
                fontFamily: 'Share Tech Mono, Consolas, monospace',
                fontSize: 12,
            }
        },
        legend: {
            data: ['IN // 入站', 'OUT // 出站'],
            textStyle: {
                color: COLORS.textNeutral,
                fontFamily: 'Share Tech Mono, Consolas, monospace',
                fontSize: 10,
            },
            top: 0,
            itemWidth: 16,
            itemHeight: 1,
        },
        grid: { top: 30, right: 16, bottom: 28, left: 56 },
        xAxis: {
            type: 'category',
            data: times,
            axisLabel: {
                color: COLORS.textDim,
                fontSize: 10,
                fontFamily: 'Share Tech Mono, Consolas, monospace',
                interval: 'auto',
                rotate: 30,
            },
            axisLine: { lineStyle: { color: COLORS.border } },
            axisTick: { show: false },
        },
        yAxis: {
            type: 'value',
            axisLabel: {
                color: COLORS.textDim,
                fontSize: 10,
                fontFamily: 'Share Tech Mono, Consolas, monospace',
            },
            splitLine: { lineStyle: { color: COLORS.border, type: 'dashed' } },
            axisLine: { show: false },
            axisTick: { show: false },
        },
        series: [
            {
                name: 'IN // 入站',
                type: 'line',
                data: netInValues,
                smooth: false,
                symbol: 'none',
                lineStyle: {
                    color: COLORS.blue,
                    width: 1.5,
                    shadowColor: COLORS.blue,
                    shadowBlur: 3,
                },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(0,184,255,0.1)' },
                        { offset: 1, color: 'rgba(0,0,0,0)' }
                    ])
                }
            },
            {
                name: 'OUT // 出站',
                type: 'line',
                data: netOutValues,
                smooth: false,
                symbol: 'none',
                lineStyle: {
                    color: COLORS.cyan,
                    width: 1.5,
                    shadowColor: COLORS.cyan,
                    shadowBlur: 3,
                },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(0,229,255,0.08)' },
                        { offset: 1, color: 'rgba(0,0,0,0)' }
                    ])
                }
            }
        ]
    });
}

// ==================== 告警列表 ====================

/** 加载告警数据 */
async function loadAlerts() {
    const res = await fetchJSON('/api/alerts?limit=10');
    if (!res || res.code !== 200) return;

    const alerts = res.data;
    const container = document.getElementById('alert-list');

    if (!alerts || alerts.length === 0) {
        container.innerHTML = '<p class="no-data">NO ACTIVE ALERTS // 暂无告警，系统运行正常</p>';
        return;
    }

    container.innerHTML = alerts.map(function (a) {
        const resolvedClass = a.is_resolved ? ' resolved' : '';
        const serverName = a.server_name || 'UNKNOWN // 未知';
        const metricType = (a.metric_type || 'UNKNOWN').toUpperCase();
        const time = a.created_at ? formatTime(a.created_at) : '';

        return '<div class="alert-item' + resolvedClass + '">' +
            '<div class="alert-info">' +
                '<span class="alert-server">\u25C6 ' + serverName + ' // ' + metricType + ' ALERT</span>' +
                '<span class="alert-detail">VALUE: ' + (a.current_value || '-') + '% | THRESHOLD: ' + (a.threshold_value || '-') + '% // ' + (a.message || '') + '</span>' +
            '</div>' +
            '<span class="alert-time">' + time + '</span>' +
        '</div>';
    }).join('');
}

// ==================== 加载服务器指标数据 ====================

/** 加载选中服务器的历史指标 */
async function loadServerMetrics() {
    if (!selectedServer) return;

    const minutes = document.getElementById('time-range').value;
    const res = await fetchJSON('/api/metrics/' + selectedServer + '?minutes=' + minutes);
    if (!res || res.code !== 200) return;

    const metrics = res.data;

    // 更新环形图（取最新一条数据）
    if (metrics && metrics.length > 0) {
        const latest = metrics[metrics.length - 1];
        updateGauges(
            latest.cpu_usage,
            latest.memory_usage,
            latest.disk_usage,
            latest.network_in,
            latest.network_out
        );
    }

    // 更新趋势图
    updateCharts(metrics);
}

// ==================== 全量刷新 ====================

/** 一次性刷新所有数据模块 */
async function refreshAll() {
    await Promise.all([
        loadLocalStatus(),
        loadLocalMetrics(),
        loadLocalProcesses(),
        loadOverview(),
        loadServers(),
        loadServerMetrics(),
        loadAlerts()
    ]);
}

// ==================== 事件绑定 ====================

/** 绑定所有 UI 交互事件 */
function bindEvents() {
    // 服务器选择变更
    document.getElementById('server-select').addEventListener('change', function () {
        selectedServer = parseInt(this.value);
        loadServerMetrics();
    });

    // 时间范围变更
    document.getElementById('time-range').addEventListener('change', function () {
        loadServerMetrics();
    });

    // 手动刷新按钮
    document.getElementById('btn-refresh').addEventListener('click', function () {
        const btn = this;
        btn.disabled = true;
        btn.textContent = 'REFRESHING...';
        refreshAll().finally(function () {
            btn.disabled = false;
            btn.textContent = '\u21BB REFRESH // 刷新';
        });
    });

    // 窗口缩放时重绘所有 ECharts 实例
    window.addEventListener('resize', function () {
        Object.keys(charts).forEach(function (key) {
            var c = charts[key];
            if (c && typeof c.resize === 'function') {
                c.resize();
            }
        });
    });
}

// ==================== 初始化入口 ====================

document.addEventListener('DOMContentLoaded', function () {
    // 启动时钟
    updateClock();
    setInterval(updateClock, 1000);

    // 初始化 ECharts 图表
    initGauges();
    initCharts();

    // 绑定交互事件
    bindEvents();

    // 首次全量加载
    refreshAll();

    // 定时自动刷新（10秒间隔）
    refreshTimer = setInterval(refreshAll, REFRESH_INTERVAL);

    console.log('[PRTS] Monitor System v2.0 initialized // 罗德岛监控系统已启动');
});