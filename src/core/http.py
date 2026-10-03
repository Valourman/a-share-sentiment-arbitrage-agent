"""统一 HTTP 会话与连接池管理模块

集中收敛工程内的 HTTP 客户端栈至 httpx，提供高并发连接池复用、统一超时策略、
线程安全单例获取以及显式生命周期释放机制，彻底杜绝资源与文件句柄泄漏。
"""

import atexit
import logging
import threading
from typing import Dict, Optional
import httpx

logger = logging.getLogger(__name__)

# 统一默认请求头
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

_shared_client_lock = threading.Lock()
_shared_client: Optional[httpx.Client] = None


def create_http_client(
    timeout: float = 10.0,
    max_keepalive_connections: int = 20,
    max_connections: int = 50,
    headers: Optional[Dict[str, str]] = None,
    follow_redirects: bool = True,
) -> httpx.Client:
    """创建具备独立连接池的高性能 HTTP 客户端实例。

    参数:
        timeout: 超时时间（秒）
        max_keepalive_connections: 最大长连接保持数
        max_connections: 最大并发连接总数
        headers: 自定义请求头
        follow_redirects: 是否跟随重定向

    返回:
        配置好的 httpx.Client 实例
    """
    merged_headers = dict(DEFAULT_HEADERS)
    if headers:
        merged_headers.update(headers)

    limits = httpx.Limits(
        max_keepalive_connections=max_keepalive_connections,
        max_connections=max_connections,
        keepalive_expiry=30.0,
    )

    return httpx.Client(
        timeout=httpx.Timeout(timeout),
        limits=limits,
        headers=merged_headers,
        follow_redirects=follow_redirects,
    )


def get_shared_http_client() -> httpx.Client:
    """获取全局共享的线程安全 HTTP 客户端与连接池单例。

    适用于生命周期与进程绑定的只读爬取与 API 访问，自动进行连接复用。
    """
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        with _shared_client_lock:
            if _shared_client is None or _shared_client.is_closed:
                _shared_client = create_http_client(
                    timeout=10.0,
                    max_keepalive_connections=30,
                    max_connections=100,
                )
    return _shared_client


def close_shared_http_client() -> None:
    """显式关闭全局共享客户端并释放连接池资源。"""
    global _shared_client
    with _shared_client_lock:
        if _shared_client is not None and not _shared_client.is_closed:
            try:
                _shared_client.close()
                logger.debug("已安全释放全局共享 HTTP 客户端连接池")
            except Exception as e:
                logger.warning(f"关闭全局 HTTP 客户端连接池异常: {e}")
            finally:
                _shared_client = None


# 注册退出钩子，确保解释器退出时关闭连接池无资源泄漏
atexit.register(close_shared_http_client)
