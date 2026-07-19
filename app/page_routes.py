"""
页面路由 - 渲染前端页面
"""
from flask import Blueprint, render_template

page_bp = Blueprint('pages', __name__)


@page_bp.route('/')
def index():
    """主仪表盘页面"""
    return render_template('dashboard.html')


@page_bp.route('/servers')
def servers():
    """服务器管理页面"""
    return render_template('servers.html')
