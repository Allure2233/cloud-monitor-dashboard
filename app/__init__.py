"""
Flask 应用工厂
"""
from flask import Flask
from flask_cors import CORS


def create_app():
    """应用工厂模式创建 Flask 应用"""
    app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static',
        static_url_path='/static'
    )
    app.config.from_object('app.config.Config')
    CORS(app)

    # 注册路由蓝图
    from app.routes import api_bp
    from app.page_routes import page_bp
    app.register_blueprint(api_bp)
    app.register_blueprint(page_bp)

    return app
