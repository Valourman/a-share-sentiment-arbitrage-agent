import http.server
import socketserver
import os
import webbrowser

PORT = 8080
DIRECTORY = os.path.join(os.path.dirname(__file__), 'frontend')


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)


def run_server():
    socketserver.TCPServer.allow_reuse_address = True
    print(f'>>> 前端静态服务已启动:')
    print(f'    - ALPHA-SENSE 落地页:      http://localhost:{PORT}/landing.html')
    print(f'    - Gemini 交互版 (免构建):  http://localhost:{PORT}/index.html')
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()


if __name__ == '__main__':
    run_server()
