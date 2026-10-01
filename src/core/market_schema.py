"""
向后兼容模块：主数据契约已统一收敛至 src.core.schema
"""
from src.core.schema import MarketSnapshot

__all__ = ["MarketSnapshot"]

