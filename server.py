import http.server
import json
import os
import urllib.parse
from src.tools.market import MarketDataTool
from src.tools.stock_resolver import StockResolver

PORT = int(os.environ.get('STATIC_SERVER_PORT', '8080'))
DIRECTORY = os.path.join(os.path.dirname(__file__), 'frontend')


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/market':
            params = urllib.parse.parse_qs(parsed.query)
            query = params.get('code', [''])[0].strip() or params.get('query', [''])[0].strip()

            try:
                resolved_code = None
                resolved_name = None
                if query:
                    resolved = StockResolver.resolve_from_text(query)
                    if resolved:
                        resolved_code, resolved_name = resolved
                    elif query.isdigit() and len(query) == 6:
                        resolved_code = query
                        resolved_name = StockResolver.search_name_by_code(query) or f"标的 {query}"

                if not resolved_code:
                    resolved_code = '600584'
                    resolved_name = '长电科技'

                tool = MarketDataTool()
                snapshot = tool.fetch_snapshot(resolved_code)

                data = {
                    "stock_code": snapshot.stock_code,
                    "stock_name": resolved_name or snapshot.stock_name,
                    "current_price": snapshot.current_price,
                    "change_percent": snapshot.change_percent,
                    "turnover_amount_yi": snapshot.turnover_amount_yi,
                    "pre_close": snapshot.pre_close,
                    "is_trading": snapshot.is_trading,
                }
            except Exception as e:
                data = {
                    "stock_code": query or "600584",
                    "stock_name": "行情获取异常",
                    "current_price": 0.0,
                    "change_percent": 0.0,
                    "turnover_amount_yi": 0.0,
                    "pre_close": 0.0,
                    "is_trading": False,
                    "error": str(e),
                }

            payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        super().do_GET()


def run_server():
    # 多线程 HTTP 服务：单个慢连接不再阻塞其余请求；
    # 仅绑定本地回环地址，避免局域网内其他设备访问本地演示服务
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    print('>>> 前端静态服务已启动:')
    print(f'    - ALPHA-SENSE 落地页:      http://localhost:{PORT}/landing.html')
    print(f'    - Gemini 交互版 (免构建):  http://localhost:{PORT}/index.html')
    print(f'    - 实时行情接口:           http://localhost:{PORT}/api/market?code=600584')
    with http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler) as httpd:
        httpd.serve_forever()


if __name__ == '__main__':
    run_server()

