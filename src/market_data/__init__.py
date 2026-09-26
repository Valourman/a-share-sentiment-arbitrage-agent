"""沪深北 A 股全市场日行情的采集、校验和本地 SQLite 存储。"""

from .sync import sync_latest

__all__ = ["sync_latest"]
