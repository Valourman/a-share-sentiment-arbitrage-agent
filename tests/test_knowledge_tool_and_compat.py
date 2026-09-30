"""针对 FinancialKnowledgeTool 与老版本知识库向下兼容性的单元测试"""

from unittest.mock import MagicMock
from src.knowledge.tools import FinancialKnowledgeTool
from src.knowledge.hybrid_engine import FinancialRAGKnowledgeBase
from src.knowledge.schema import Document, KnowledgeType
from src.memory.knowledge import FinancialKnowledgeRetriever, KnowledgeItem
from src.tools.base import BaseTool, ToolResult


def test_financial_knowledge_tool_metadata():
    """测试 FinancialKnowledgeTool 的工具元数据与 OpenAI 契约生成"""
    tool = FinancialKnowledgeTool()
    assert isinstance(tool, BaseTool)
    assert tool.name == "search_financial_knowledge"
    assert "散户黑话" in tool.description or "金融知识库" in tool.description

    # 测试 parameters 结构
    schema = tool.to_openai_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "search_financial_knowledge"
    params = schema["function"]["parameters"]
    assert "query" in params["properties"]
    assert "stock_code" in params["properties"]
    assert "top_k" in params["properties"]
    assert "query" in params["required"]


def test_financial_knowledge_tool_execution_success():
    """测试默认知识库下散户黑话与反讽心理检索执行"""
    tool = FinancialKnowledgeTool()
    result = tool.execute(query="感谢主力送钱")
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.error is None
    assert "感谢主力" in result.output or "送钱" in result.output or "反讽" in result.output


def test_financial_knowledge_tool_empty_or_not_found():
    """测试查询空或标的代码未匹配时的优雅降级输出"""
    tool = FinancialKnowledgeTool()

    # 1. 空查询
    result_empty = tool.execute(query="")
    assert result_empty.success is True
    assert "未检索到" in result_empty.output

    # 2. 标的代码过滤无匹配
    result_code_none = tool.execute(query="感谢主力", stock_code="999999")
    assert result_code_none.success is True
    assert "未检索到" in result_code_none.output


def test_financial_knowledge_tool_error_handling():
    """测试知识库检索出现内部异常时的防御性错误封装"""
    mock_kb = MagicMock(spec=FinancialRAGKnowledgeBase)
    mock_kb.retrieve.side_effect = RuntimeError("向量索引崩溃")

    tool = FinancialKnowledgeTool(kb=mock_kb)
    result = tool.execute(query="测试崩溃")
    assert result.success is False
    assert result.output == ""
    assert "知识库检索异常" in result.error
    assert "向量索引崩溃" in result.error


def test_financial_knowledge_tool_with_custom_kb_and_filtering():
    """测试自定义金融知识库接入与标的股票代码过滤检索"""
    kb = FinancialRAGKnowledgeBase(chunk_size=100, chunk_overlap=20)
    kb.add_document(
        Document(
            doc_id="doc_ann_600667",
            title="重大资产重组",
            content="公司正在积极推进重大资产购买事项，拟收购半导体芯片资产。",
            doc_type=KnowledgeType.ANNOUNCEMENT,
            stock_code="600667",
        )
    )
    kb.add_document(
        Document(
            doc_id="doc_ann_000001",
            title="银行季度分红",
            content="平安银行拟实施中期利润分配方案，每股派发现金红利。",
            doc_type=KnowledgeType.ANNOUNCEMENT,
            stock_code="000001",
        )
    )

    tool = FinancialKnowledgeTool(kb=kb)
    res_stock = tool.execute(query="资产购买重组", stock_code="600667", top_k=2)
    assert res_stock.success is True
    assert "600667" in res_stock.output
    assert "000001" not in res_stock.output


def test_backward_compatibility_memory_knowledge():
    """测试对老代码 src.memory.knowledge 的完整向下兼容性"""
    retriever = FinancialKnowledgeRetriever()
    assert len(retriever.DEFAULT_KNOWLEDGE_BASE) >= 10

    matched = retriever.search("主升浪", top_k=2)
    assert len(matched) > 0
    assert matched[0].term == "主升浪"
    assert isinstance(matched[0], KnowledgeItem)

    ctx = retriever.format_as_context(matched)
    assert "【A 股领域背景知识参考】" in ctx
    assert "主升浪" in ctx

    # 测试动态添加知识项
    retriever.add_item(
        KnowledgeItem(
            term="高低切",
            category="量化特征",
            definition="资金从高位高估值板块流向低位低估值板块的调仓行为",
            sentiment_bias=0.2,
        )
    )
    new_res = retriever.search("盘面出现高低切现象")
    assert any(it.term == "高低切" for it in new_res)
