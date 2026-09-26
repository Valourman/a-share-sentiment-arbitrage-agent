"""东方财富公开全市场快照；只负责完整分页，不推断交易日期。"""

from dataclasses import dataclass
import math
import time
from typing import Any

import httpx


API_URL = "https://push2.eastmoney.com/api/qt/clist/get"
# 深圳主板、创业板、上海主板、科创板、北交所；不包含 B 股、基金、指数。
A_SHARE_FILTER = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048"
FIELDS = "f12,f13,f14,f100,f2,f17,f15,f16,f18,f5,f6,f124"


class SourceError(RuntimeError):
    """网络、接口或分页不完整；不应写入任何当日证券数据。"""


@dataclass(frozen=True)
class Universe:
    total: int
    rows: tuple[dict[str, Any], ...]


class EastmoneySource:
    """低频逐页拉取；服务端总量、每页条数和唯一代码必须全部匹配。"""

    def __init__(
        self,
        client: httpx.Client | None = None,
        *,
        page_size: int = 100,
        interval: float = 1.5,
        attempts: int = 4,
    ) -> None:
        if not 1 <= page_size <= 100:
            raise ValueError("page_size 必须在 1..100 之间")
        if interval < 0 or attempts < 1:
            raise ValueError("interval 必须非负，attempts 必须大于零")
        self.page_size = page_size
        self.interval = interval
        self.attempts = attempts
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=httpx.Timeout(15.0),
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; AShareDailySync/1.0)",
                "Referer": "https://quote.eastmoney.com/",
            },
        )

    def __enter__(self) -> "EastmoneySource":
        return self

    def __exit__(self, *_: object) -> None:
        if self._owns_client:
            self.client.close()

    def _get_page(self, page: int) -> tuple[int, list[dict[str, Any]]]:
        params = {
            "pn": page,
            "pz": self.page_size,
            "po": 1,
            "np": 1,
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": A_SHARE_FILTER,
            "fields": FIELDS,
        }
        for attempt in range(self.attempts):
            try:
                response = self.client.get(API_URL, params=params)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or payload.get("rc") != 0:
                    raise SourceError(f"第 {page} 页接口 rc 异常")
                data = payload.get("data")
                if not isinstance(data, dict):
                    raise SourceError(f"第 {page} 页缺少 data")
                total, rows = data.get("total"), data.get("diff")
                if isinstance(total, bool) or not isinstance(total, int) or total <= 0:
                    raise SourceError(f"第 {page} 页 total 无效: {total!r}")
                if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
                    raise SourceError(f"第 {page} 页 diff 不是证券列表")
                return total, rows
            except (httpx.HTTPError, ValueError, SourceError) as exc:
                # 4xx（429 除外）通常是请求格式错误，不应反复请求。
                retryable = not isinstance(exc, httpx.HTTPStatusError) or (
                    exc.response.status_code in (429, 500, 502, 503, 504)
                )
                if not retryable or attempt + 1 == self.attempts:
                    raise SourceError(f"获取第 {page} 页失败: {exc}") from exc
                time.sleep(max(self.interval, 0.5) * (2**attempt))
        raise AssertionError("重试循环未按预期结束")

    def fetch_all(self) -> Universe:
        total, first = self._get_page(1)
        pages = math.ceil(total / self.page_size)
        rows: list[dict[str, Any]] = []
        seen: set[tuple[object, object]] = set()
        for page in range(1, pages + 1):
            if page == 1:
                current_total, batch = total, first
            else:
                if self.interval:
                    time.sleep(self.interval)
                current_total, batch = self._get_page(page)
            expected = min(self.page_size, total - (page - 1) * self.page_size)
            if current_total != total or len(batch) != expected:
                raise SourceError(
                    f"第 {page}/{pages} 页不完整：total={current_total}/{total}, "
                    f"条数={len(batch)}/{expected}"
                )
            for row in batch:
                key = (row.get("f13"), row.get("f12"))
                if key in seen:
                    raise SourceError(f"跨页重复证券: {key!r}；可能正在刷新分页")
                seen.add(key)
                rows.append(row)
        if len(rows) != total or len(seen) != total:
            raise SourceError(f"证券数量不一致：{len(rows)}/{total}")
        return Universe(total=total, rows=tuple(rows))
