import http.server
import os

PORT = int(os.environ.get('STATIC_SERVER_PORT', '8080'))
DIRECTORY = os.path.join(os.path.dirname(__file__), 'frontend')


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)


def run_server():
    # 多线程 HTTP 服务：单个慢连接不再阻塞其余请求；
    # 仅绑定本地回环地址，避免局域网内其他设备访问本地演示服务
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    print('>>> 前端静态服务已启动:')
    print(f'    - ALPHA-SENSE 落地页:      http://localhost:{PORT}/landing.html')
    print(f'    - Gemini 交互版 (免构建):  http://localhost:{PORT}/index.html')
    with http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as httpd:
        httpd.serve_forever()


if __name__ == '__main__':
    run_server()
