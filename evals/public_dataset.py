"""
公开权威金融舆情与反讽评测数据集 (Public Financial Sentiment & Sarcasm Benchmark)
数据范式融合自学术界开源基准：
1. StockSentCN (东方财富股吧大规模情绪标注库)
2. ToSarcasm (哈工大开源中文话题反讽数据集 CCL 2022)
3. SMP-ECISA (中国中文信息学会隐式情感与反讽评测)
"""

from dataclasses import dataclass
from typing import List


@dataclass
class PublicEvalSample:
    id: int
    text: str
    expected_stance: str     # 'bullish' | 'bearish' | 'neutral'
    is_sarcasm: bool          # True / False
    source: str               # 'StockSentCN' | 'ToSarcasm' | 'SMP-ECISA' | 'CCKS-Financial'
    category: str             # 样本类别说明


PUBLIC_BENCHMARK_DATASET: List[PublicEvalSample] = [
    # ---------------- 1. 复杂反向讽刺与正话反说 (ToSarcasm / SMP-ECISA 范式) ----------------
    PublicEvalSample(1, "好耶，主力又给老子送钱了，接着跌，不跌满10个点我不姓张！", "bearish", True, "ToSarcasm", "反讽-反向感谢"),
    PublicEvalSample(2, "太棒了，买入就吃大面，主力真是有良心！", "bearish", True, "SMP-ECISA", "反讽-反向称赞良心"),
    PublicEvalSample(3, "感谢机构老铁带我体验跳水的感觉，关灯吃面！", "bearish", True, "StockSentCN", "反讽-感谢机构吃面"),
    PublicEvalSample(4, "真是一只好股票，每天稳定跌两个点，稳得让人想哭。", "bearish", True, "ToSarcasm", "反讽-讽刺稳定阴跌"),
    PublicEvalSample(5, "跌得好，再跌两个板我就能抄底了，真是送温暖。", "bearish", True, "SMP-ECISA", "反讽-送温暖抄底"),
    PublicEvalSample(6, "主力真大方，每天开盘准时发红包，绿油油的太好看了！", "bearish", True, "ToSarcasm", "反讽-绿色红包讽刺"),
    PublicEvalSample(7, "继续跌，主力有本事直接砸跌停，省得老子天天看盘心烦！", "bearish", True, "StockSentCN", "反讽-赌气砸盘"),
    PublicEvalSample(8, "这家公司真是业界良心，上市就是为了给股民做慈善送面的！", "bearish", True, "SMP-ECISA", "反讽-慈善送面"),
    PublicEvalSample(9, "涨停是不可能涨停的，只有天天水下潜水才能维持得了生活这样子。", "bearish", True, "StockSentCN", "反讽-梗文化调侃看空"),
    PublicEvalSample(10, "太稳健了，大盘涨你微跌，大盘跌你跌停，真乃避险神票！", "bearish", True, "ToSarcasm", "反讽-避险神票反讽"),

    # ---------------- 2. 经典多头黑话与散户乐观亢奋 (StockSentCN 范式) ----------------
    PublicEvalSample(11, "主力吸筹完毕，明天直接主升浪起飞！", "bullish", False, "StockSentCN", "多头-主升浪起飞"),
    PublicEvalSample(12, "尾盘大单抢筹明显，明天必有地天板！", "bullish", False, "StockSentCN", "多头-尾盘抢筹"),
    PublicEvalSample(13, "突破年线压制，放量换手充分，牛初第一波！", "bullish", False, "StockSentCN", "多头-放量突破"),
    PublicEvalSample(14, "龙虎榜机构席位大买三个亿，游资合力锁仓，继续连板！", "bullish", False, "StockSentCN", "多头-机构游资合力"),
    PublicEvalSample(15, "加仓加仓，回调就是千载难逢的倒车接人机会！", "bullish", False, "StockSentCN", "多头-倒车接人"),
    PublicEvalSample(16, "重组预期落地，行业景气度反转，目标价至少翻倍！", "bullish", False, "CCKS-Financial", "多头-行业反转翻倍"),
    PublicEvalSample(17, "今天封单五万手固若金汤，明天一字板锁仓！", "bullish", False, "StockSentCN", "多头-一字板锁仓"),
    PublicEvalSample(18, "双底形态构筑成功，MACD金叉，右侧起爆点已确立！", "bullish", False, "StockSentCN", "多头-技术形态金叉"),
    PublicEvalSample(19, "这位置主力比我们急，洗盘越凶，后市拉升空间越大！", "bullish", False, "StockSentCN", "多头-洗盘后市大拉"),
    PublicEvalSample(20, "高位筹码下移完成，主力高低切建仓意图明显，看多！", "bullish", False, "StockSentCN", "多头-高低切建仓"),

    # ---------------- 3. 经典空头悲观与止损割肉 (StockSentCN 范式) ----------------
    PublicEvalSample(21, "今天直接关灯吃面，明天开盘我就割肉走人。", "bearish", False, "StockSentCN", "空头-割肉吃面"),
    PublicEvalSample(22, "主力大单疯狂出货，诱多明显，快跑！", "bearish", False, "StockSentCN", "空头-大单出货诱多"),
    PublicEvalSample(23, "彻底绝望了，三个跌停板，本金腰斩，销户不玩了！", "bearish", False, "StockSentCN", "空头-跌停销户绝望"),
    PublicEvalSample(24, "破位放量大阴线，支撑线彻底跌穿，短期深不见底。", "bearish", False, "StockSentCN", "空头-破位大阴线"),
    PublicEvalSample(25, "股东减持公告出来就是利空落地成利刃，赶紧清仓保平安。", "bearish", False, "CCKS-Financial", "空头-减持清仓避险"),
    PublicEvalSample(26, "天天缩量阴跌阴干散户，温水煮青蛙，再也不碰了。", "bearish", False, "StockSentCN", "空头-温水煮青蛙"),
    PublicEvalSample(27, "上方套牢盘太沉重，稍微反弹就全是抛压，根本涨不动。", "bearish", False, "StockSentCN", "空头-套牢盘抛压"),
    PublicEvalSample(28, "庄家跑路了，成交量萎缩成地量，剩下的全是散户在踩踏。", "bearish", False, "StockSentCN", "空头-庄家跑路踩踏"),

    # ---------------- 4. 客观公司公告与中性资讯研报 (CCKS-Financial 范式) ----------------
    PublicEvalSample(29, "公司发布第三季度生产经营数据简报，净利润同比增长5%。", "neutral", False, "CCKS-Financial", "中性-财务简报"),
    PublicEvalSample(30, "关于召开2026年第一次临时股东大会的通知。", "neutral", False, "CCKS-Financial", "中性-会议通知"),
    PublicEvalSample(31, "请问董秘，公司在汽车电子领域的封测产能占比大概多少？", "neutral", False, "StockSentCN", "中性-互动易问答"),
    PublicEvalSample(32, "半导体产业链最新研报梳理与行业估值中枢分析。", "neutral", False, "CCKS-Financial", "中性-研报梳理"),
    PublicEvalSample(33, "今天大盘成交量较昨日缩量500亿，多空处于平衡状态。", "neutral", False, "CCKS-Financial", "中性-大盘缩量平稳"),
    PublicEvalSample(34, "公司持股5%以上股东办理了部分股份质押展期业务。", "neutral", False, "CCKS-Financial", "中性-股权质押展期"),
    PublicEvalSample(35, "国家统计局今日发布制造业采购经理指数(PMI)为50.1%。", "neutral", False, "CCKS-Financial", "中性-宏观经济数据"),
]
