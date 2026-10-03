import os
import time
import logging
from typing import Any, Dict, Optional
import httpx
from dotenv import load_dotenv
from src.core.http import create_http_client
from src.core.schema import RawPost, SentimentAnalysisResult, SentimentStance
from src.core.parser import RobustAgentParser
from src.core.llm import HelloAgentsLLM
from src.tools.base import Tool, ToolParameter

load_dotenv()
logger = logging.getLogger(__name__)


class FinancialSentimentAnalyzer(Tool):
    """
    语义与反讽判定工具
    集成 A 股黑话字典与大模型自愈解析器，精准识别正话反说与隐晦情绪
    """
    name = "sentiment_analyzer"
    description = "分析 A 股散户发帖的真实情绪、多空立场与反讽意图"
    parameters = [
        ToolParameter(
            name="title",
            type="string",
            description="待研判的帖子标题或文本语料",
            required=True,
        )
    ]

    BULLISH_SLANG = ['主升浪', '起飞', '吸筹', '加仓', '地天板', '连板', '牛初', '看多', '反转', '涨停', '抢筹', '突破']
    BEARISH_SLANG = ['吃面', '关灯', '割肉', '出货', '跳水', '跌停', '天地板', '保卫战', '诱多', '套牢', '跌破']

    # 反讽/正话反说模式识别关键词
    SARCASTIC_PRAISE_WORDS = ('好耶', '太棒了', '感谢主力', '送钱', '良心', '稳得')
    SARCASTIC_LOSS_WORDS = ('跌', '套', '亏', '面', '跳水', '哭')

    def __init__(
        self,
        llm: Optional[HelloAgentsLLM] = None,
        http_client: Optional[httpx.Client] = None,
    ):
        super().__init__()
        self.llm = llm or HelloAgentsLLM()
        self.api_key = self.llm.config.openai_api_key
        self.base_url = self.llm.config.openai_base_url
        self.model_name = self.llm.config.default_model
        self.client = self.llm.client

        # 统一 HTTP 会话与连接池管理
        self._custom_http_client = http_client
        self._owned_http_client: Optional[httpx.Client] = None

        # TypeSafe AI Jev (System 1 非自回归单步决策引擎)
        self.typesafe_api_key = os.getenv('TYPESAFE_API_KEY')
        self.typesafe_base_url = os.getenv('TYPESAFE_BASE_URL', 'https://api.typesafe.ai/v1/systemone')
        self.typesafe_model = os.getenv('TYPESAFE_MODEL', 'jev-latest')
        self.default_engine = os.getenv('DEFAULT_SENTIMENT_ENGINE', 'auto')

    def _get_http_client(self) -> httpx.Client:
        """获取或创建复用的 HTTP 连接池客户端"""
        if self._custom_http_client is not None:
            return self._custom_http_client
        if self._owned_http_client is None or self._owned_http_client.is_closed:
            self._owned_http_client = create_http_client(timeout=10.0)
        return self._owned_http_client

    def close(self) -> None:
        """显式释放自身创建的连接池客户端"""
        if self._owned_http_client is not None and not self._owned_http_client.is_closed:
            try:
                self._owned_http_client.close()
            finally:
                self._owned_http_client = None

    def __enter__(self) -> "FinancialSentimentAnalyzer":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Tool 标准执行入口"""
        title = kwargs.get("title", "")
        post = RawPost(title=title)
        res = self.analyze(post)
        return res.model_dump()

    def _check_sarcasm(self, text: str):
        if any(w in text for w in self.SARCASTIC_PRAISE_WORDS) and any(w in text for w in self.SARCASTIC_LOSS_WORDS):
            return True, '表扬词与实质亏损下跌词并存，符合反向讽刺模式'
        return False, ''

    def analyze_with_jev(self, post: RawPost, timeout: float = 10.0) -> SentimentAnalysisResult:
        """调用 TypeSafe Jev 非自回归单步决策模型，毫秒级提取多空倾向、反讽概率与情绪等级"""
        title = post.title
        detected_bullish = [s for s in self.BULLISH_SLANG if s in title]
        detected_bearish = [s for s in self.BEARISH_SLANG if s in title]
        all_slang = detected_bullish + detected_bearish

        if not self.typesafe_api_key:
            logger.warning('TYPESAFE_API_KEY not configured, falling back to mock.')
            return self.analyze_mock(post)

        headers = {
            'Authorization': f'Bearer {self.typesafe_api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            'model': self.typesafe_model,
            'state': f'A股散户发帖标题：{title}',
            'questions': {
                'is_sarcasm': {
                    'type': 'noul',
                    'instructions': (
                        '该发帖是否属于反向讽刺、阴阳怪气、正话反说或说反话？'
                        '例如表面说送钱、太棒了、稳得让人想哭，实际因持续下跌大亏割肉而说反话。'
                        '如果是反讽或气话返回 True，如果是真实客观表达返回 False。'
                    )
                },
                'stance': {
                    'type': 'choice',
                    'instructions': '识别散户真实的市场投资态度倾向：',
                    'criteria': {
                        'bullish': '看多/看涨/乐观期待/主升浪',
                        'bearish': '看空/悲观绝望/割肉止损/套牢抱怨',
                        'neutral': '中性客观资讯/公司公告/无明显情绪'
                    }
                },
                'sentiment_level': {
                    'type': 'score',
                    'instructions': '散户情绪量化等级（从极度绝望恐慌到极度亢奋狂热）',
                    'criteria': [
                        '极度绝望恐慌，严重割肉亏损',
                        '悲观被套或轻微看空',
                        '中性客观平淡',
                        '积极乐观或看好反弹',
                        '极度狂热亢奋，盲目看多'
                    ]
                }
            }
        }

        t0 = time.perf_counter()
        try:
            client = self._get_http_client()
            resp = client.post(self.typesafe_base_url, headers=headers, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)

            answers = data.get('answers', {})

            # 1. 解析反讽概率
            sarcasm_obj = answers.get('is_sarcasm', {})
            sarcasm_prob = float(sarcasm_obj.get('noul', 0.0))
            is_sarcasm = sarcasm_prob >= 0.5

            # 2. 解析立场与概率分布
            stance_obj = answers.get('stance', {})
            raw_choice = str(stance_obj.get('choice', 'neutral')).lower()
            confidence = float(stance_obj.get('confidence', 0.85))
            probabilities = stance_obj.get('probabilities', {})

            # 3. 解析情绪分级 (0~4分 -> 归一化至 [-1.0, 1.0])
            score_obj = answers.get('sentiment_level', {})
            raw_score = float(score_obj.get('score', 2.0))
            normalized_score = round(max(-1.0, min(1.0, (raw_score - 2.0) / 2.0)), 2)

            # 4. 反讽常识校准：若命中高置信度反讽且带有下跌/亏损表征，纠偏表层 choice
            final_stance = SentimentStance.NEUTRAL
            rule_sarcasm, _ = self._check_sarcasm(title)
            if is_sarcasm or rule_sarcasm:
                is_sarcasm = True
                final_stance = SentimentStance.BEARISH
                if normalized_score > -0.3:
                    normalized_score = -0.75
                reasoning = (
                    f'TypeSafe Jev识别出高反讽概率({sarcasm_prob:.0%})，触发语义反转消歧：'
                    f'表面用语具迷惑性，实则为严重被套/割肉反语抱怨。'
                )
            else:
                if raw_choice == 'bullish':
                    final_stance = SentimentStance.BULLISH
                elif raw_choice == 'bearish':
                    final_stance = SentimentStance.BEARISH
                else:
                    final_stance = SentimentStance.NEUTRAL
                reasoning = (
                    f'TypeSafe Jev非自回归研判：判定为[{final_stance.value}] (置信度:{confidence:.0%})，'
                    f'情绪量化分 {normalized_score:+.2f}。'
                )

            return SentimentAnalysisResult(
                raw_title=title,
                stance=final_stance,
                sentiment_score=normalized_score,
                is_sarcasm=is_sarcasm,
                confidence=confidence,
                slang_detected=all_slang,
                reasoning=reasoning,
                engine_used='jev',
                probabilities=probabilities,
                sarcasm_probability=sarcasm_prob,
                latency_ms=latency_ms,
            )

        except Exception as e:
            logger.warning(f'Jev API invocation error: {e}, falling back to llm/mock')
            if self.llm.is_available:
                return self.analyze_with_llm(post)
            return self.analyze_mock(post)

    def analyze_with_llm(self, post: RawPost, max_retries: int = 2) -> SentimentAnalysisResult:
        if not self.llm.is_available:
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

        t0 = time.perf_counter()
        for attempt in range(max_retries + 1):
            try:
                raw_content = self.llm.chat(
                    messages=messages,
                    model=self.model_name,
                    temperature=0.1,
                )
                parsed, feedback = RobustAgentParser.parse_or_build_feedback(
                    raw_content, SentimentAnalysisResult
                )
                if parsed:
                    parsed.raw_title = post.title
                    parsed.engine_used = 'llm'
                    parsed.latency_ms = round((time.perf_counter() - t0) * 1000, 2)
                    return parsed
                messages.append({'role': 'assistant', 'content': raw_content})
                messages.append({'role': 'user', 'content': feedback})
            except Exception as e:
                logger.warning(f'LLM call error: {e}')

        # LLM 重试耗尽后的全量降级：显式记录，避免研判质量劣化对调用方不可见
        logger.warning(f"LLM 消歧失败，语料 [{post.title[:30]}...] 降级为规则引擎结果")
        return self.analyze_mock(post)

    def analyze_mock(self, post: RawPost) -> SentimentAnalysisResult:
        t0 = time.perf_counter()
        title = post.title
        is_sarcasm, sarcasm_reason = self._check_sarcasm(title)
        detected_bullish = [s for s in self.BULLISH_SLANG if s in title]
        detected_bearish = [s for s in self.BEARISH_SLANG if s in title]
        all_slang = detected_bullish + detected_bearish
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        if is_sarcasm:
            return SentimentAnalysisResult(
                raw_title=title,
                stance=SentimentStance.BEARISH,
                sentiment_score=-0.75,
                is_sarcasm=True,
                confidence=0.85,
                slang_detected=all_slang,
                reasoning=f'命中反讽模式: {sarcasm_reason}，表面欢呼实则绝望割肉。',
                engine_used='mock',
                latency_ms=latency_ms,
            )

        if len(detected_bullish) > len(detected_bearish):
            return SentimentAnalysisResult(
                raw_title=title,
                stance=SentimentStance.BULLISH,
                sentiment_score=0.65,
                is_sarcasm=False,
                confidence=0.80,
                slang_detected=detected_bullish,
                reasoning='命中典型多头黑话词汇，散户看涨情绪强烈。',
                engine_used='mock',
                latency_ms=latency_ms,
            )
        elif len(detected_bearish) > len(detected_bullish):
            return SentimentAnalysisResult(
                raw_title=title,
                stance=SentimentStance.BEARISH,
                sentiment_score=-0.65,
                is_sarcasm=False,
                confidence=0.80,
                slang_detected=detected_bearish,
                reasoning='命中典型空头黑话词汇，散户看空或止损。',
                engine_used='mock',
                latency_ms=latency_ms,
            )
        else:
            return SentimentAnalysisResult(
                raw_title=title,
                stance=SentimentStance.NEUTRAL,
                sentiment_score=0.0,
                is_sarcasm=False,
                confidence=0.60,
                slang_detected=all_slang,
                reasoning='未触发明显多空词汇，判定为中性讨论或客观资讯。',
                engine_used='mock',
                latency_ms=latency_ms,
            )

    def analyze(self, post: RawPost, engine_mode: Optional[str] = None, use_llm: bool = True) -> SentimentAnalysisResult:
        """
        统一研判分发门面:
        - engine_mode: 'jev' | 'llm' | 'mock' | 'auto' (默认读取 DEFAULT_SENTIMENT_ENGINE 或 auto)
        - use_llm: 保持对旧签名的兼容性 (显式传 False 且未指定 engine_mode 时降级到 mock)
        """
        mode = engine_mode or self.default_engine

        if not use_llm and engine_mode is None:
            mode = 'mock'

        if mode == 'jev':
            return self.analyze_with_jev(post)
        elif mode == 'llm':
            return self.analyze_with_llm(post)
        elif mode == 'mock':
            return self.analyze_mock(post)
        elif mode == 'auto':
            if self.typesafe_api_key:
                return self.analyze_with_jev(post)
            elif use_llm and self.llm.is_available:
                return self.analyze_with_llm(post)
            return self.analyze_mock(post)

        return self.analyze_mock(post)
