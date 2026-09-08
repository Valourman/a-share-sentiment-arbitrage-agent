import re
from typing import List, Tuple
from src.core.schema import RawPost, SentimentAnalysisResult, SentimentStance


class FinancialSentimentAnalyzer:
    """
    金融语义与情绪研判引擎（支持黑话挖掘、反讽检测与确定性规则兜底）
    """

    BULLISH_SLANG = ["吸筹", "主升浪", "起飞", "大长腿", "地天板", "洗盘", "格局", "加仓", "满仓", "吃肉"]
    BEARISH_SLANG = ["吃面", "关灯", "割肉", "跑路", "保卫战", "天地板", "诱多", "挂单", "踩踏", "崩盘"]

    SARCASM_RULES = [
        (r"好耶.*(?:又送钱|跌|亏)", "字面欢呼实质讽刺暴跌，表达强烈看空与不满"),
        (r"跌得好|接着跌|有本事跌停", "赌气反讽式发泄，属于恐慌/看空情绪"),
        (r"谢谢主力送我.*(离开|出局|深套)", "正话反说，嘲讽主力收割，属于极度悲观"),
    ]

    def analyze_mock(self, post: RawPost) -> SentimentAnalysisResult:
        """
        确定性启发式分析器（在不消耗 LLM Token 或网络断网时的本地自愈与验证逻辑）
        """
        title = post.title
        is_sarcasm, sarcasm_reason = self._check_sarcasm(title)

        detected_bullish = [s for s in self.BULLISH_SLANG if s in title]
        detected_bearish = [s for s in self.BEARISH_SLANG if s in title]
        all_slang = detected_bullish + detected_bearish

        if is_sarcasm:
            return SentimentAnalysisResult(
                stance=SentimentStance.BEARISH,
                sentiment_score=-0.75,
                is_sarcasm=True,
                confidence=0.85,
                slang_detected=all_slang,
                reasoning=f"命中反讽模式: {sarcasm_reason}，原表达通过字面正向词传达极度悲观立场。",
            )

        if len(detected_bullish) > len(detected_bearish):
            return SentimentAnalysisResult(
                stance=SentimentStance.BULLISH,
                sentiment_score=0.65,
                is_sarcasm=False,
                confidence=0.80,
                slang_detected=detected_bullish,
                reasoning=f"命中典型多头黑话词汇: {', '.join(detected_bullish)}，股民对后市存在上涨预期。",
            )
        elif len(detected_bearish) > len(detected_bullish):
            return SentimentAnalysisResult(
                stance=SentimentStance.BEARISH,
                sentiment_score=-0.65,
                is_sarcasm=False,
                confidence=0.80,
                slang_detected=detected_bearish,
                reasoning=f"命中典型空头/恐慌黑话词汇: {', '.join(detected_bearish)}，散户止损与逃跑意愿强烈。",
            )
        else:
            return SentimentAnalysisResult(
                stance=SentimentStance.NEUTRAL,
                sentiment_score=0.0,
                is_sarcasm=False,
                confidence=0.60,
                slang_detected=all_slang,
                reasoning="语句未出现明显极端多空词汇或正负抵消，研判为中性讨论或客观事实陈述。",
            )

    def _check_sarcasm(self, text: str) -> Tuple[bool, str]:
        for pattern, reason in self.SARCASM_RULES:
            if re.search(pattern, text):
                return True, reason
        return False, ""
