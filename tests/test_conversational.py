import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.stdout.reconfigure(encoding='utf-8')
from src.tools.stock_resolver import StockResolver
from src.agent.conversational import ConversationalArbitrageAgent


def test_stock_resolver_entities():
    """验证从自然语言句子中准确抽取股票代码与名称（包括太极实业等非静态字典股）"""
    # 截图中失败的 case
    code, name = StockResolver.resolve_from_text("看看太极实业如何？")
    assert code == "600667"
    assert "太极实业" in name

    code1, name1 = StockResolver.resolve_from_text("帮我看看长电科技现在的散户情绪怎么样")
    assert code1 == "600584"
    assert "长电" in name1

    code2, name2 = StockResolver.resolve_from_text("比亚迪今天跌了吗？")
    assert code2 == "002594"
    assert "比亚迪" in name2

    code3, _ = StockResolver.resolve_from_text("查一下 600519 最近表现")
    assert code3 == "600519"

    # 询问模型或概念不应误判为股票
    none_res = StockResolver.resolve_from_text("你是什么模型？")
    assert none_res is None

    none_res2 = StockResolver.resolve_from_text("什么是多头诱多陷阱？")
    assert none_res2 is None


def test_conversational_agent_flow():
    """验证多轮对话流转、身份介绍、实体继承与概念问答"""
    agent = ConversationalArbitrageAgent()

    # 1. 验证模型身份问答 (对应截图 case 1)
    res_identity = agent.chat("你是什么模型？", engine_mode="mock")
    assert res_identity.intent == "SYSTEM_IDENTITY"
    assert "System 1" in res_identity.reply_text
    assert "微观决策引擎" in res_identity.reply_text

    # 2. 验证动态股票问答 (对应截图 case 2)
    res_stock = agent.chat("看看太极实业如何？", max_posts=3, engine_mode="mock")
    assert res_stock.intent == "ANALYZE_STOCK"
    assert res_stock.stock_code == "600667"
    assert res_stock.analysis_state is not None
    assert agent.current_stock_code == "600667"

    # 3. 验证多轮上下文继承追问 (指代代词 '它')
    res_follow = agent.chat("那它今天全天成交额是多少？")
    assert res_follow.intent == "FOLLOW_UP"
    assert res_follow.stock_code == "600667"
    assert "成交额" in res_follow.reply_text

    # 4. 验证金融概念咨询
    res_concept = agent.chat("什么是多头诱多陷阱？")
    assert res_concept.intent == "FINANCIAL_KNOWLEDGE"
    assert "BULL_TRAP" in res_concept.reply_text or "诱多" in res_concept.reply_text

    # 5. 清空记忆
    agent.clear_memory()
    assert agent.current_stock_code is None
    assert len(agent.history) == 0


if __name__ == "__main__":
    test_stock_resolver_entities()
    print("test_stock_resolver_entities: PASSED")
    test_conversational_agent_flow()
    print("test_conversational_agent_flow: PASSED")
    print("\n所有对话式 Agent 针对性测试用例全部通过！")
