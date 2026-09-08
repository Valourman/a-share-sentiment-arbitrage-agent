import os
import logging
from dotenv import load_dotenv
from openai import OpenAI
from src.core.schema import RawPost, SentimentAnalysisResult, SentimentStance
from src.core.parser import RobustAgentParser

load_dotenv()
logger = logging.getLogger(__name__)

class FinancialSentimentAnalyzer:
    BULLISH_SLANG = ['主升浪', '起飞', '吸筹', '加仓', '地天板', '连板', '牛初', '看多', '反转', '涨停']
    BEARISH_SLANG = ['吃面', '关灯', '割肉', '出货', '跳水', '跌停', '天地板', '保卫战', '诱多', '套牢']

    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.base_url = os.getenv('OPENAI_BASE_URL')
        self.model_name = os.getenv('MODEL_NAME', 'gemini-3.8-flash-tiered')
        self.client = None
        if self.api_key and self.base_url:
            try:
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            except Exception as e:
                logger.warning(f'OpenAI init error: {e}')

    def _check_sarcasm(self, text: str):
        if any(w in text for w in ['好耶', '太棒了', '感谢主力', '送钱']) and any(w in text for w in ['跌', '套', '亏', '面']):
            return True, '表扬词与实质亏损下跌词并存，符合反向讽刺模式'
        return False, ''

    def analyze_with_llm(self, post: RawPost, max_retries: int = 2) -> SentimentAnalysisResult:
        if not self.client:
            return self.analyze_mock(post)

        system_prompt = (
            '你是一位精通 A 股散户心理学与量化金融的资深分析专家。\n'
            '你的任务是分析散户股民的单条发帖，识别其真实情绪、多空立场，并特别警惕反讽、阴阳怪气与股市黑话。\n'
            '请务必且仅返回严格合法的 JSON 对象，不要输出任何其他文本。\n'
            'JSON 字段要求：\n'
            '- stance: bullish / bearish / neutral\n'
            '- sentiment_score: 浮点数 [-1.0, 1.0]\n'
            '- is_sarcasm: true / false\n'
            '- confidence: 浮点数 [0.0, 1.0]\n'
            '- slang_detected: 识别出的黑话列表\n'
            '- reasoning: 50字以内的专业分析推导依据'
        )

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': f'待分析发帖标题：{post.title}'}
        ]

        for attempt in range(max_retries + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=0.1,
                )
                raw_content = resp.choices[0].message.content
                parsed, feedback = RobustAgentParser.parse_or_build_feedback(
                    raw_content, SentimentAnalysisResult
                )
                if parsed:
                    return parsed
                messages.append({'role': 'assistant', 'content': raw_content})
                messages.append({'role': 'user', 'content': feedback})
            except Exception as e:
                logger.warning(f'LLM call error: {e}')

        return self.analyze_mock(post)

    def analyze_mock(self, post: RawPost) -> SentimentAnalysisResult:
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
                reasoning=f'命中反讽模式: {sarcasm_reason}，表面欢呼实则绝望割肉。',
            )

        if len(detected_bullish) > len(detected_bearish):
            return SentimentAnalysisResult(
                stance=SentimentStance.BULLISH,
                sentiment_score=0.65,
                is_sarcasm=False,
                confidence=0.80,
                slang_detected=detected_bullish,
                reasoning='命中典型多头黑话词汇，散户看涨情绪强烈。',
            )
        elif len(detected_bearish) > len(detected_bullish):
            return SentimentAnalysisResult(
                stance=SentimentStance.BEARISH,
                sentiment_score=-0.65,
                is_sarcasm=False,
                confidence=0.80,
                slang_detected=detected_bearish,
                reasoning='命中典型空头黑话词汇，散户看空或止损。',
            )
        else:
            return SentimentAnalysisResult(
                stance=SentimentStance.NEUTRAL,
                sentiment_score=0.0,
                is_sarcasm=False,
                confidence=0.60,
                slang_detected=all_slang,
                reasoning='未触发明显多空词汇，判定为中性讨论或客观资讯。',
            )

    def analyze(self, post: RawPost, use_llm: bool = True) -> SentimentAnalysisResult:
        if use_llm and self.client:
            return self.analyze_with_llm(post)
        return self.analyze_mock(post)
