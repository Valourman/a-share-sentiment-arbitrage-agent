from dataclasses import dataclass

@dataclass
class EvalSample:
    id: int
    text: str
    expected_stance: str
    is_sarcasm: bool
    description: str

EVAL_DATASET = [
    # 1. 复杂反讽与赌气言论 (最考验模型消歧能力)
    EvalSample(1, '好耶，主力又给老子送钱了，接着跌，不跌满10个点我不姓张！', 'bearish', True, '反向讽刺送钱，实则极度看空'),
    EvalSample(2, '太棒了，买入就吃大面，主力真是有良心！', 'bearish', True, '反向讽刺良心，实则亏损割肉'),
    EvalSample(3, '感谢机构老铁带我体验跳水的感觉，关灯吃面！', 'bearish', True, '反向感谢，实则套牢吃面'),
    EvalSample(4, '真是一只好股票，每天稳定跌两个点，稳得让人想哭。', 'bearish', True, '讽刺稳定，实则持续阴跌'),
    EvalSample(5, '跌得好，再跌两个板我就能抄底了，真是送温暖。', 'bearish', True, '表面称赞送温暖，实则宣泄恐慌'),

    # 2. 典型股市黑话与看多看空
    EvalSample(6, '主力吸筹完毕，明天直接主升浪起飞！', 'bullish', False, '典型多头黑话: 主升浪、起飞'),
    EvalSample(7, '尾盘抢筹明显，明天必有地天板！', 'bullish', False, '典型多头黑话: 抢筹、地天板'),
    EvalSample(8, '今天直接关灯吃面，明天开盘我就割肉走人。', 'bearish', False, '典型空头黑话: 关灯吃面、割肉'),
    EvalSample(9, '主力大单疯狂出货，诱多明显，快跑！', 'bearish', False, '典型空头黑话: 出货、诱多'),
    EvalSample(10, '突破年线压制，换手充分，牛初第一波！', 'bullish', False, '典型多头黑话: 突破、牛初'),

    # 3. 中性客观资讯与产业讨论 (不应误判情绪)
    EvalSample(11, '公司发布第三季度生产经营数据简报，净利润同比增长5%。', 'neutral', False, '客观财务公告'),
    EvalSample(12, '关于召开2026年第一次临时股东大会的通知。', 'neutral', False, '中性日常公告'),
    EvalSample(13, '请问董秘，公司在汽车电子领域的封测产能占比大概多少？', 'neutral', False, '股民互动中性提问'),
    EvalSample(14, '半导体产业链最新研报梳理与行业估值中枢分析。', 'neutral', False, '中性行业研报资讯'),
    EvalSample(15, '今天大盘成交量较昨日缩量500亿，多空处于平衡状态。', 'neutral', False, '中性大盘客观陈述')
]
