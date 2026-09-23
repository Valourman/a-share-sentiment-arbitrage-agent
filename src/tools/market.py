import logging
import urllib.request
from typing import Any, Dict
from src.core.market_schema import MarketSnapshot
from src.tools.base import Tool, ToolParameter

logger = logging.getLogger(__name__)


class MarketDataTool(Tool):
    """从公开行情通道获取个股盘面量价数据（确定性事实源）"""
    name = "market_data"
    description = "获取 A 股标的真实客观的秒级 L1 盘面快照，包括现价、涨跌幅、前收价与成交额"
    parameters = [
        ToolParameter(
            name="stock_code",
            type="string",
            description="6位A股股票代码，例如 600519 或 002594",
            required=True,
        )
    ]

    @staticmethod
    def _format_secid(code: str) -> str:
        code_str = str(code).strip()
        if code_str.lower().startswith(('sh', 'sz', 'bj')):
            return code_str.lower()
        if code_str.startswith(('6', '9')):
            return f'sh{code_str}'
        elif code_str.startswith(('0', '3', '5')):
            return f'sz{code_str}'
        elif code_str.startswith(('4', '8')):
            return f'bj{code_str}'
        return f'sh{code_str}'

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Tool 标准执行入口"""
        stock_code = kwargs.get("stock_code", "")
        snapshot = self.fetch_snapshot(stock_code)
        return snapshot.model_dump()

    def fetch_snapshot(self, stock_code: str) -> MarketSnapshot:
        secid = self._format_secid(stock_code)
        url = f'https://hq.sinajs.cn/list={secid}'
        headers = {
            'Referer': 'https://finance.sina.com.cn',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                content = resp.read().decode('gbk', errors='ignore')
            if '"' not in content:
                raise ValueError(f'返回内容无效，未能提取行情数据: {content}')
            raw_data = content.split('"')[1]
            parts = raw_data.split(',')
            if len(parts) < 10:
                raise ValueError(f'行情切片字段不完整: {parts}')

            name = parts[0]
            pre_close = float(parts[2])
            curr_p = float(parts[3])
            amount_yuan = float(parts[9])
            chg_pct = 0.0
            if pre_close > 0:
                chg_pct = round(((curr_p - pre_close) / pre_close) * 100, 2)

            return MarketSnapshot(
                stock_code=stock_code,
                stock_name=name,
                current_price=curr_p,
                pre_close=pre_close,
                change_percent=chg_pct,
                turnover_amount_yi=round(amount_yuan / 1e8, 2),
                is_trading=True
            )
        except Exception as e:
            logger.warning(f"获取股票 [{stock_code}] 行情快照失败，启动降级保护: {e}")
            return MarketSnapshot(
                stock_code=stock_code,
                stock_name='未识别标的',
                current_price=0.0,
                pre_close=0.0,
                change_percent=0.0,
                turnover_amount_yi=0.0,
                is_trading=False
            )
