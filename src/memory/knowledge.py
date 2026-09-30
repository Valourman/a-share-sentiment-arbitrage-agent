from typing import List, Optional
from pydantic import BaseModel, Field


class KnowledgeItem(BaseModel):
    """金融知识与黑话条目"""
    term: str = Field(description="术语/黑话关键词")
    category: str = Field(description="分类: 多头黑话 / 空头黑话 / 反讽隐喻 / 量化特征")
    definition: str = Field(description="真实含义与散户心理动机解读")
    sentiment_bias: float = Field(ge=-1.0, le=1.0, description="内在情绪倾向评分")


class FinancialKnowledgeRetriever:
    """
    Hello Agents 长期知识与领域检索库 (RAG 基础组件)
    维护 A 股特色黑话、反讽心理模型与盘面特征，支持动态注册与精准语义检索
    """
    DEFAULT_KNOWLEDGE_BASE = [
        KnowledgeItem(term="主升浪", category="多头黑话", definition="股票最具爆发力、涨幅最大的拉升阶段，散户极度乐观看涨", sentiment_bias=0.8),
        KnowledgeItem(term="起飞", category="多头黑话", definition="形容个股即将或正在大幅拉升，散户亢奋追涨", sentiment_bias=0.7),
        KnowledgeItem(term="地天板", category="多头黑话", definition="从跌停板直接拉升至涨停板，日内日落重生极度狂热", sentiment_bias=0.9),
        KnowledgeItem(term="吃面", category="空头黑话", definition="源于重庆啤酒关灯吃面典故，形容遭受严重亏损极度凄凉", sentiment_bias=-0.8),
        KnowledgeItem(term="关灯", category="空头黑话", definition="指亏损严重到连灯都舍不得开，是绝望悲观的隐喻", sentiment_bias=-0.8),
        KnowledgeItem(term="天地板", category="空头黑话", definition="从涨停板直接砸到跌停板，主力诱多出货高位套牢", sentiment_bias=-0.9),
        KnowledgeItem(term="保卫战", category="空头黑话", definition="特定整数点位反复失守，散户普遍陷入无力绝望心态", sentiment_bias=-0.6),
        KnowledgeItem(term="感谢主力", category="反讽隐喻", definition="正话反说，表面向主力道谢，实际在亏损被套后进行宣泄讽刺", sentiment_bias=-0.75),
        KnowledgeItem(term="送钱", category="反讽隐喻", definition="若伴随暴跌亏损语境，实为讽刺主力割韭菜收割散户", sentiment_bias=-0.7),
        KnowledgeItem(term="好耶", category="反讽隐喻", definition="在下跌跳水场景下表示破防与自嘲讽刺", sentiment_bias=-0.7),
    ]

    def __init__(self, items: Optional[List[KnowledgeItem]] = None):
        self._items: List[KnowledgeItem] = list(items or self.DEFAULT_KNOWLEDGE_BASE)

    def add_item(self, item: KnowledgeItem) -> None:
        """追加一条领域知识条目"""
        self._items.append(item)

    def search(self, query: str, top_k: int = 3) -> List[KnowledgeItem]:
        """按关联度检索与输入文本命中的知识条目"""
        matched = []
        for item in self._items:
            if item.term in query or query in item.term:
                matched.append(item)
        return matched[:top_k]

    def format_as_context(self, matched_items: List[KnowledgeItem]) -> str:
        """将检索到的知识转化为注入 Prompt 的参考上下文"""
        if not matched_items:
            return ""
        lines = ["【A 股领域背景知识参考】"]
        for it in matched_items:
            lines.append(f"- 术语 [{it.term}] ({it.category}): {it.definition} (情绪倾向: {it.sentiment_bias})")
        return "\n".join(lines)
