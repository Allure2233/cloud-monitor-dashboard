"""
应用入口文件
启动 Flask 开发服务器或生产服务器（gunicorn）
"""
from app import create_app

app = create_app()

if __name__ == '__main__':
    from app.config import Config
    app.run(host='0.0.0.0', port=5000, debug=Config.DEBUG)
