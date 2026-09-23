from src.memory.buffer import ConversationBufferMemory
from src.memory.knowledge import FinancialKnowledgeRetriever, KnowledgeItem
from src.core.message import Message, RoleType


def test_conversation_buffer_memory():
    mem = ConversationBufferMemory(max_messages=3)
    mem.add_message(Message.system("系统指令"))
    mem.add_user_message("问题 1")
    mem.add_assistant_message("回答 1")
    mem.add_user_message("问题 2")

    messages = mem.get_messages()
    # 首个 system 消息被保留，后跟最新的 2 条
    assert len(messages) == 3
    assert messages[0].role == RoleType.SYSTEM
    assert messages[-1].content == "问题 2"

    ctx_str = mem.get_context_string()
    assert "USER: 问题 2" in ctx_str

    mem.clear()
    assert len(mem.get_messages()) == 0


def test_financial_knowledge_retriever():
    retriever = FinancialKnowledgeRetriever()
    results = retriever.search("主力今天又送钱了，接着吃面吧")
    assert len(results) > 0
    terms = [r.term for r in results]
    assert "送钱" in terms or "吃面" in terms

    context_str = retriever.format_as_context(results)
    assert "【A 股领域背景知识参考】" in context_str

    # 动态插入自定义知识
    retriever.add_item(
        KnowledgeItem(term="小作文", category="A股谣言", definition="未经证实的虚假消息", sentiment_bias=0.0)
    )
    custom_res = retriever.search("盘中突发小作文")
    assert any(r.term == "小作文" for r in custom_res)
