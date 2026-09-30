import os
import logging
from dataclasses import dataclass
from typing import List, Dict, Optional
from dotenv import load_dotenv
from openai import OpenAI
from src.agent.engine import SentimentArbitrageAgent
from src.agent.state import AgentState, DivergenceType
from src.tools.stock_resolver import StockResolver

load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class ConversationalResponse:
    reply_text: str
    intent: str
    analysis_state: Optional[AgentState] = None
    stock_code: Optional[str] = None
    stock_name: Optional[str] = None


class ConversationalArbitrageAgent:
    """
    全功能对话式金融套利智能体：
    摒弃死板机械模板，真正理解用户提问意图（买卖咨询/归因剖析/主力动向/盘面细节），
    结合 TypeSafe Jev 与 L1 盘面实时背离数据，针对性给出人类专家式金融解答。
    """

    def __init__(self):
        self.underlying_agent = SentimentArbitrageAgent()
        self.history: List[Dict[str, str]] = []
        self.current_stock_code: Optional[str] = None
        self.current_stock_name: Optional[str] = None
        self.last_analysis_state: Optional[AgentState] = None

        # 可选的自由对话大模型客户端（复用统一配置；仅配置 API Key 时同样生效，
        # 并携带超时与重试，避免网络挂起时 UI 线程无限阻塞）
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.base_url = os.getenv('OPENAI_BASE_URL')
        self.model_name = os.getenv('MODEL_NAME', 'gpt-4o')
        self.llm_timeout = float(os.getenv('TIMEOUT_SECONDS', '30'))
        self.client = None
        if self.api_key:
            try:
                client_kwargs = {
                    'api_key': self.api_key,
                    'timeout': self.llm_timeout,
                    'max_retries': 2,
                }
                if self.base_url:
                    client_kwargs['base_url'] = self.base_url
                self.client = OpenAI(**client_kwargs)
            except Exception as e:
                logger.warning(f'Conversational OpenAI init error: {e}')

    def clear_memory(self):
        """清空会话多轮记忆与焦点标的"""
        self.history.clear()
        self.current_stock_code = None
        self.current_stock_name = None
        self.last_analysis_state = None

    def chat(
        self,
        user_input: str,
        max_posts: int = 5,
        engine_mode: str = 'auto'
    ) -> ConversationalResponse:
        clean_input = user_input.strip()
        if not clean_input:
            return ConversationalResponse(
                reply_text='您好！请问有什么我可以协助您的？您可以直接输入股票名称（如“太极实业”、“长电科技”）或向我提问行情与散户情绪。',
                intent='GUIDE'
            )

        # 记录用户提问
        self.history.append({'role': 'user', 'content': clean_input})

        # 1. 意图 A: 询问自身身份、系统架构与技术底座
        identity_keywords = ['你是谁', '什么模型', '哪家模型', '自我介绍', '架构', '谁开发的', '什么原理', '技术原理']
        if any(kw in clean_input.lower() for kw in identity_keywords):
            reply_text = self._handle_identity_query()
            self.history.append({'role': 'assistant', 'content': reply_text})
            return ConversationalResponse(
                reply_text=reply_text,
                intent='SYSTEM_IDENTITY'
            )

        # 2. 意图 B: 针对上文焦点的多轮追问 (优先代词与特征词，防止把“成交额”误当新股票)
        follow_up_keywords = ['它', '这只', '刚才', '详细', '为什么', '帖子', '发帖', '成交', '反讽', '谁在说', '多空', '涨跌', '怎么看', '能买', '抄底', '出货', '割肉', '被套']
        if self.last_analysis_state is not None and any(kw in clean_input for kw in follow_up_keywords):
            stock_match = StockResolver.resolve_from_text(clean_input)
            # 如果没有提取到新的不同股票，直接作为追问处理
            if not stock_match or stock_match[0] == self.current_stock_code:
                reply_text = self._synthesize_stock_answer(clean_input, self.last_analysis_state)
                self.history.append({'role': 'assistant', 'content': reply_text})
                return ConversationalResponse(
                    reply_text=reply_text,
                    intent='FOLLOW_UP',
                    analysis_state=self.last_analysis_state,
                    stock_code=self.current_stock_code,
                    stock_name=self.current_stock_name
                )

        # 3. 意图 C: 用户在提问中指定了具体股票 -> 触发数据采集与全流程研判
        stock_match = StockResolver.resolve_from_text(clean_input)
        if stock_match:
            stock_code, stock_name = stock_match
            self.current_stock_code = stock_code
            self.current_stock_name = stock_name

            state = self.underlying_agent.run(
                stock_code=stock_code,
                max_posts=max_posts,
                engine_mode=engine_mode
            )
            self.last_analysis_state = state
            if state.stock_name:
                self.current_stock_name = state.stock_name

            # 结合用户具体的提问（如是问“能买吗”还是“看看如何”），针对性生成回答！
            reply_text = self._synthesize_stock_answer(clean_input, state)
            self.history.append({'role': 'assistant', 'content': reply_text})

            return ConversationalResponse(
                reply_text=reply_text,
                intent='ANALYZE_STOCK',
                analysis_state=state,
                stock_code=self.current_stock_code,
                stock_name=self.current_stock_name
            )

        # 4. 意图 D: 金融通识、策略机制与概念科普
        knowledge_keywords = ['诱多', '恐慌磨底', '背离', 'jev', 'typesafe', '散户情绪', '左侧', '右侧', '套利']
        if any(kw in clean_input.lower() for kw in knowledge_keywords):
            reply_text = self._handle_knowledge(clean_input)
            self.history.append({'role': 'assistant', 'content': reply_text})
            return ConversationalResponse(
                reply_text=reply_text,
                intent='FINANCIAL_KNOWLEDGE'
            )

        # 5. 意图 E: 自由金融问答 (优先调用真实 LLM，没有 LLM 则提供高情商投研回应)
        reply_text = self._handle_general_chat(clean_input)
        self.history.append({'role': 'assistant', 'content': reply_text})
        return ConversationalResponse(
            reply_text=reply_text,
            intent='GENERAL_CHAT'
        )

    def _synthesize_stock_answer(self, user_question: str, state: AgentState) -> str:
        """
        核心智能合成器：
        彻底告别死板模版！如果配置了 LLM，让 LLM 根据当前实时数据针对性直接回答；
        如果没有 LLM，根据用户的具体疑问类型（买卖建议/暴跌归因/主力出货/反讽剖析/盘面数据）直接命中要害！
        """
        stock_name = state.stock_name or state.stock_code
        stock_code = state.stock_code
        market = state.market_data
        ref = state.reflection
        if ref is None or ref.divergence_type == DivergenceType.INSUFFICIENT_DATA:
            # Do not pass zero-filled quotes to the LLM or turn absent evidence
            # into a buy/sell recommendation in the offline fallback.
            market_note = (
                f"已取得的行情成交额为 {market.turnover_amount_yi:.2f} 亿元，"
                "但舆情样本不足，无法研判背离。"
                if market is not None and market.is_trading and market.current_price > 0
                else "行情与成交额暂无有效数据。"
            )
            explanation = ref.reflection_narrative if ref else "研判尚未生成。"
            return (
                f"⚠️ **{stock_name}：数据不足，暂不提供买卖判断。**\n\n"
                f"{explanation}\n\n{market_note}请核对数据来源后再试。"
            )
        div_type_val = ref.divergence_type.value if hasattr(ref.divergence_type, 'value') else str(ref.divergence_type)

        sarcasm_posts = [p for p in state.sentiment_list if p.is_sarcasm]
        bull_posts = [p for p in state.sentiment_list if p.stance.value == 'bullish']
        bear_posts = [p for p in state.sentiment_list if p.stance.value == 'bearish']

        # 1. 如果有真实 LLM Client，直接由大模型进行情境化思考回答
        if self.client:
            try:
                system_prompt = (
                    "你是一位精通 A 股散户心理学与量化盘面背离研判的资深操盘风控专家。\n"
                    "请务必【直接针对用户的具体问题】给出深入透彻、有理有据、逻辑闭环的专业回答。\n"
                    "【严禁答非所问！严禁机械复读大段空洞模板！】\n"
                    "下方是系统为你刚刚实时提取的底层客观数据与反思研判结果：\n"
                    f"- 标的：{stock_name} ({stock_code})\n"
                    f"- 实时盘面事实：现价 {market.current_price:.2f} 元，今日涨跌幅 {market.change_percent:+.2f}%，成交额 {market.turnover_amount_yi:.2f} 亿元\n"
                    f"- 散户情绪指数：{state.average_sentiment:+.2f} (看多发帖 {len(bull_posts)} 条，看空发帖 {len(bear_posts)} 条，Jev 识别出 {len(sarcasm_posts)} 条反讽言论)\n"
                    f"- 核心背离结论：{div_type_val} (风险等级: {ref.risk_level})\n"
                    f"- 状态机反思推导：{ref.reflection_narrative}\n"
                    f"- 操作建议：{ref.action_suggestion}\n\n"
                    "回答要求：\n"
                    "1. 用户问‘能不能买/能不能抄底/该走还是留’：第一句必须给出直接、明确的多空倾向判断；\n"
                    "2. 用户问‘为什么跌/出货了吗’：结合散户情绪盲区与实际量价成交给出深度因果剖析；\n"
                    "3. 紧扣用户的问题细节，回答要干练、专业、有观点，字数在 150~300 字之间。"
                )
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"用户具体提问：{user_question}"}
                ]
                resp = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=0.3,
                )
                # content 可能为 None（如触发内容过滤），显式兜底保证 str 返回契约
                return resp.choices[0].message.content or ''
            except Exception as e:
                logger.warning(f"LLM synthesis error: {e}, falling back to targeted rule-based synthesizer")

        # 2. 离线精细化智能意图合成器 (真正针对问题，直接切中要害)
        q = user_question.lower()

        # 场景 1: 询问操作建议 (能买吗 / 抄底 / 割肉 / 买入 / 卖出 / 被套 / 适合进吗)
        if any(w in q for w in ['能买', '抄底', '买入', '建仓', '能进', '上车', '适合买', '割肉', '被套', '跑路', '卖不卖', '怎么操作']):
            if ref.divergence_type == DivergenceType.BULL_TRAP:
                return (
                    f"⚠️ **【明确建议：当前不宜盲目抄底，警惕诱多阴跌风险】**\n\n"
                    f"针对您问的 **{stock_name}** 能否介入的问题：\n"
                    f"1. **核心矛盾**：目前股吧散户情绪偏向乐观狂热（综合情绪指数 **+{state.average_sentiment:.2f}**），频繁出现期待反转与抄底的声音；但盘面客观实际表现为下挫走弱（今日 **{market.change_percent:+.2f}%**，现价 **{market.current_price:.2f} 元**）。\n"
                    f"2. **风控警示**：散户亢奋与价格下挫形成了典型的 **【多头诱多 (BULL_TRAP)】** 背离。主力往往借助散户不理性的抄底热情进行高位派发出货或顺势阴跌砸盘。\n"
                    f"3. **操作策略**：{ref.action_suggestion} 建议等待左侧恐慌充分出清，或等待右侧量价企稳再做决策。"
                )
            elif ref.divergence_type == DivergenceType.PANIC_BOTTOM:
                return (
                    f"💡 **【明确建议：左侧磨底阶段，不建议盲目杀跌，可关注企稳建仓机会】**\n\n"
                    f"针对您问的 **{stock_name}** 操作方向：\n"
                    f"1. **核心特征**：股吧散户目前充斥绝望悲观言论（情绪指数 **{state.average_sentiment:.2f}**），Jev 捕捉到多条被套割肉言论；但盘面实际抗跌甚至微幅翻红（今日 **{market.change_percent:+.2f}%**）。\n"
                    f"2. **研判结论**：触发 **【恐慌磨底 (PANIC_BOTTOM)】** 信号，表明非理性恐慌盘正逐步释放，筹码开始沉淀。\n"
                    f"3. **操作策略**：{ref.action_suggestion} 持股者不必在最悲观时割在低点；轻仓者可分批跟踪右侧放量信号。"
                )
            else:
                return (
                    f"📊 **【明确建议：趋势共振，按既有技术面与仓位策略执行】**\n\n"
                    f"针对 **{stock_name}** 的买卖判断：\n"
                    f"当前散户情绪指数（**{state.average_sentiment:+.2f}**）与盘面真实涨跌（**{market.change_percent:+.2f}%**）基本一致，市场处于理性博弈区间，未发生极端情绪背离。\n"
                    f"建议依据 5 日/20 日均线支撑与全天成交量能（当前成交 **{market.turnover_amount_yi:.2f} 亿元**）进行常规波段操作。"
                )

        # 场景 2: 询问暴跌/走势原因 (为什么跌 / 为什么涨 / 原因 / 主力在出货吗 / 怎么回事)
        if any(w in q for w in ['为什么', '为啥', '原因', '出货', '洗盘', '暴跌', '大跌', '怎么回事', '跳水']):
            if ref.divergence_type == DivergenceType.BULL_TRAP:
                return (
                    f"🔍 **【深度归因：散户盲目看多与主力派发形成背离】**\n\n"
                    f"关于 **{stock_name}** 为什么跌、主力是否在出货：\n"
                    f"1. **舆情与盘面严重错位**：抓取到的散户发帖中看多占多数，情绪指数达到 **+{state.average_sentiment:.2f}**；然而盘面客观成交 **{market.turnover_amount_yi:.2f} 亿元**，股价下挫 **{market.change_percent:+.2f}%**。\n"
                    f"2. **本质剖析**：这属于典型的诱多承接。散户误以为是‘倒车接人’或‘主力洗盘’，但实际上大单在趁反弹或横盘减持，导致买盘难以阻挡股价下移。\n"
                    f"3. **研判推导**：{ref.reflection_narrative}"
                )
            else:
                return (
                    f"🔍 **【走势归因：情绪与量价运行特征】**\n\n"
                    f"针对 **{stock_name}** 的走势成因：\n"
                    f"当前该股最新价 **{market.current_price:.2f} 元**，今日涨跌幅 **{market.change_percent:+.2f}%**，全天成交额 **{market.turnover_amount_yi:.2f} 亿元**。\n"
                    f"散户情绪面得分 **{state.average_sentiment:+.2f}**，整体情绪与资金量价趋势较为吻合，{ref.reflection_narrative}"
                )

        # 场景 3: 询问反讽言论或散户在讨论什么 (反讽 / 送钱 / 都在说什么 / 股吧 / 评论)
        if any(w in q for w in ['反讽', '送钱', '讽刺', '说什么', '在讨论', '发帖', '股吧']):
            if sarcasm_posts:
                lines = [f"🔥 **【Jev 识别出的散户反讽/阴阳怪气实况 ({stock_name})】**\n"]
                for i, p in enumerate(sarcasm_posts, 1):
                    prob = f" [置信概率: {p.sarcasm_probability:.0%}]" if p.sarcasm_probability else ""
                    lines.append(f"{i}. **原帖语义**：“{p.slang_detected if p.slang_detected else p.reasoning}”\n   ↳ **Jev 消歧分析**：{p.reasoning}{prob}")
                lines.append("\n💡 **专家点评**：这类言论字面上在说‘感谢主力送钱’、‘跌得太好了’，实际是散户被套牢后的破防反语。Jev 非自回归模型将其精准识别并纠正为看空态度。")
                return "\n".join(lines)
            else:
                return (
                    f"💬 **【散户社区讨论画像 ({stock_name})】**\n\n"
                    f"在针对 {stock_name} 抽取的发帖中，未发现强烈的反讽送钱言论，股民表达较为直截了当：\n"
                    f"- 看多言论 {len(bull_posts)} 条，看空言论 {len(bear_posts)} 条；\n"
                    f"- 散户综合情绪指数为 **{state.average_sentiment:+.2f}**。\n"
                    f"与盘面 **{market.change_percent:+.2f}%** 的走势结合，当前背离结论为【{div_type_val}】。"
                )

        # 场景 4: 询问具体量价事实 (成交量 / 成交额 / 价格 / 现价 / 涨跌)
        if any(w in q for w in ['成交', '量能', '价格', '现价', '多少钱', '盘面']):
            return (
                f"📊 **【{stock_name} 客观盘面量价清单】**\n\n"
                f"- **最新现价**：**{market.current_price:.2f} 元**\n"
                f"- **今日涨跌幅**：**{market.change_percent:+.2f}%**\n"
                f"- **全天成交额**：**{market.turnover_amount_yi:.2f} 亿元**\n"
                f"- **昨日收盘价**：**{market.pre_close:.2f} 元**\n\n"
                f"对比当前的散户情绪指数（**{state.average_sentiment:+.2f}**），我们得出的背离风控评级为：**【{div_type_val}】(风险等级: {ref.risk_level})**。"
            )

        # 场景 5: 综合概况诊断 (如“看看太极实业如何”、“长电科技怎么样”)
        alert_prefix = "🚨 **【触发背离警报：诱多风险 HIGH】**" if ref.divergence_type == DivergenceType.BULL_TRAP else ("💡 **【触发关注信号：恐慌磨底】**" if ref.divergence_type == DivergenceType.PANIC_BOTTOM else "✅ **【状态平稳：情绪与盘面共振】**")
        return (
            f"已为您深度研判 **{stock_name} ({stock_code})**：\n\n"
            f"{alert_prefix}\n\n"
            f"1. **客观盘面走势**：现价 **{market.current_price:.2f} 元**，今日涨跌 **{market.change_percent:+.2f}%**，全天成交 **{market.turnover_amount_yi:.2f} 亿元**。\n"
            f"2. **散户心理消歧**：综合情绪指数 **{state.average_sentiment:+.2f}** (区间 [-1.0 极度看空 ~ +1.0 极度看多])，检测到 {len(sarcasm_posts)} 条反向讽刺言论。\n"
            f"3. **反思研判依据**：{ref.reflection_narrative}\n"
            f"4. **操盘风控建议**：{ref.action_suggestion}\n\n"
            f"您可以针对这只股票直接向我提问，例如：“它现在能抄底吗？” 或 “为什么大家都在说送钱？”"
        )

    def _handle_identity_query(self) -> str:
        actual_engine = self.underlying_agent.analyzer.typesafe_model or 'TypeSafe Jev'
        return (
            f'我是专门面向 A 股市场的 **多源舆情反讽研判与盘面背离预警智能体 (Arbitrage Agent)**。\n\n'
            f'我的核心并不是单一的聊天模型，而是采用了先进的 **System 1 + System 2 双脑协同架构**：\n\n'
            f'1. ⚡ **微观决策引擎 (System 1 · {actual_engine})**：\n'
            f'   - 负责高并发散户发帖的毫秒级消歧（平均响应 <850ms）。\n'
            f'   - 采用非自回归（Non-autoregressive）技术，单步原生输出 `Noul` (反讽概率)、`Choice` (多空选择与置信度) 与 `Score` (情绪量化等级)，**Schema 损坏率为 0%**，专克散户“好耶主力又送钱了”这种反语。\n\n'
            f'2. 🧠 **宏观反思引擎 (System 2 · 深度推理模型)**：\n'
            f'   - 负责综合散户群体情绪指数，交叉比对新浪 L1 盘面实时量价，触发批判性反思 (Reflection Loop)，给出 `BULL_TRAP` (诱多陷阱) 或 `PANIC_BOTTOM` (恐慌磨底) 的风控建议。\n\n'
            f'3. 🌐 **真实数据基础设施**：\n'
            f'   - 舆情源：东方财富股吧实时清洗；\n'
            f'   - 盘面源：新浪财经秒级量价（现价、涨跌幅、成交额）。\n\n'
            f'您可以直接对我说 **“长电科技现在能抄底吗？”**、**“看看太极实业为什么跌”** 或 **“什么是多头诱多”**，我将直接针对您的问题给出专业分析！'
        )

    def _handle_general_chat(self, user_input: str) -> str:
        if self.client:
            try:
                system_prompt = (
                    '你是一位精通 A 股量化套利、散户行为金融学与行情盘面研判的资深专家顾问。\n'
                    '请用专业、客观且富有洞察力的口吻【直接回答用户的具体问题】。若用户未指定股票标的，'
                    '结合当前提问给出清晰框架，并友好提示可以输入具体股票名称进行交叉背离研判。'
                )
                messages = [{'role': 'system', 'content': system_prompt}]
                for m in self.history[-5:]:
                    messages.append({'role': m['role'], 'content': m['content']})

                resp = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=0.7,
                )
                return resp.choices[0].message.content or ''
            except Exception as e:
                logger.warning(f'LLM chat failed: {e}')

        return (
            f'关于您提到的：“{user_input}”：\n\n'
            f'作为专注 A 股散户情绪与盘面背离研判的智能顾问，我建议在分析任何市场现象时，都要避免单一听信社区舆情。\n\n'
            f'如果您想诊断某只具体股票的风险，可直接告诉我标的名称或代码（例如：“长电科技现在能抄底吗？”或“看看太极实业为什么跌”），'
            f'我将实时抓取股吧发帖，穿透反讽伪装，并结合真实成交量价为您出具针对性的风控判断！'
        )

    def _handle_knowledge(self, query: str) -> str:
        q = query.lower()
        if '诱多' in q or 'bull_trap' in q:
            return (
                '📌 **什么是多头诱多 (BULL_TRAP) 陷阱？**\n\n'
                '多头诱多通常发生在股票价格面临阶段性见顶或阴跌通道中：\n'
                '1. **散户端表象**：股吧与社区亢奋度极高，大量散户坚信“主力洗盘”、“主升浪在即”，情绪指数显著偏多（通常 >= +0.25）；\n'
                '2. **盘面端真相**：盘面实际涨势乏力、甚至下挫下跌（跌幅 < -0.5%），主力资金暗中派发出货；\n'
                '3. **Agent 应对策略**：本系统监测到二者背离时会立即发出高风险警报，明确提示“切忌盲目跟风抄底，警惕阴跌与踩踏风险”。'
            )
        if '恐慌' in q or 'panic_bottom' in q:
            return (
                '📌 **什么是恐慌磨底 (PANIC_BOTTOM) 机会？**\n\n'
                '恐慌磨底往往是市场转折前夕的典型特征：\n'
                '1. **散户端表象**：股吧充斥割肉绝望、关灯吃面言论，情绪指数极度悲观（<= -0.25）；\n'
                '2. **盘面端真相**：股价跌无可跌，盘面抗跌甚至微幅翻红，筹码正从非理性散户转移到长线主力手中；\n'
                '3. **Agent 应对策略**：发出关注信号，提示左侧恐慌出清，可分批追踪右侧企稳信号。'
            )
        if 'jev' in q or 'typesafe' in q:
            return (
                '⚡ **关于 TypeSafe Jev 模型在本系统中的定位：**\n\n'
                'Jev 是 TypeSafe AI 研发的**非自回归“系统一”结构化决策模型**：\n'
                '1. **极速响应**：单次决策仅需 ~850ms，相比传统自回归大模型提速 3~5 倍；\n'
                '2. **原生强类型**：直接输出 `Noul` (反讽概率)、`Choice` (多空选择与概率分布) 与 `Score` (情绪量化等级)，**Schema 损坏率为 0%**，天然避免了 JSON 语法损坏；\n'
                '3. **分工协同**：Jev 负责微观高通量发帖打标（快思考），传统 LLM 负责宏观因果反思与深度报告撰写（慢思考）。'
            )
        return (
            '本 Agent 采用“散户情绪与盘面客观事实交叉背离验证”的逆向投资哲学：\n'
            '通过捕捉股民的非理性狂热或恐慌言论，结合真实盘面行情进行批判性反思，帮助投资者识别风险与机会。'
        )
