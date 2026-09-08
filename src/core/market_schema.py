from pydantic import BaseModel, Field
from typing import Optional

class MarketSnapshot(BaseModel):
    stock_code: str = Field(description='6位股票代码')
    stock_name: str = Field(description='股票名称')
    current_price: float = Field(description='当前现价')
    pre_close: float = Field(description='昨日收盘价')
    change_percent: float = Field(description='今日涨跌幅百分比')
    turnover_amount_yi: float = Field(description='今日成交金额(亿元)')
    is_trading: bool = Field(default=True, description='是否处于交易状态')
