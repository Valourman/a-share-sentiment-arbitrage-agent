import urllib.request
import re
from src.core.market_schema import MarketSnapshot

class MarketDataTool:
    """从公开や情通咓获取个股盘面量价数据（确定性事实源）"""
    @staticmethod
    def _format_secid(code: str) -> str:
        if code.startswith('6') or code.startswith('9'):
            return f'sh{code}'
        elif code.startswith('0') or code.startswith('5'):
            return f'sz{code}'
        elif code.startswith('4') or code.startswith('8'):
            return f'bj{code}'
        return f'sh{code}'
    def fetch_snapshot(self, stock_code: str) -> MarketSnapshot:
        secid = self._format_secid(stock_code)
        url = f'https://hq.sinajs.cn/list={secid}'
        headers = default_headers = {
            'Referer': 'https://finance.sina.com.cn',
            'User-Agent': 'Mozilla/5.0'
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                content = resp.read().decode('gbk', errors='ignore')
            if '"' not in content:
                raise ValueError('invalid response')
            raw_data = content.split('"')[1]
            parts = raw_data.split(',')
            if len(parts) < 10:
                raise ValueError('incomplete quote')
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
                turnover_amount_yi=round(amount_yuan / 1e8, 2)
            )
        except Exception:
            return MarketSnapshot(
                stock_code=stock_code,
                stock_name='unknown',
                current_price=0.0,
                pre_close=0.0,
                change_percent=0.0,
                turnover_amount_yi=0.0,
                is_trading=False
            )
