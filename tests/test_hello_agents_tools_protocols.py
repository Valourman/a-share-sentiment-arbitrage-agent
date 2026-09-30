from src.tools.chain import ToolChain
from src.tools.async_executor import AsyncToolExecutor
from src.tools.builtin.calculator import CalculatorTool
from src.tools.builtin.search import SearchTool
from src.tools.registry import ToolRegistry
from src.memory.manager import MemoryManager
from src.memory.tools import MemoryTool
from src.protocols.mcp.client import MCPServer, MCPClient
from src.protocols.mcp.tool import MCPTool
from src.protocols.a2a.implementation import A2AServer, A2AClient, A2ATool


def test_calculator_tool():
    calc = CalculatorTool()
    assert calc.execute(expression="2 + 3 * 4") == "14"
    assert calc.execute(expression="sqrt(16)") == "4.0"
    assert "错误" in calc.execute(expression="import os")


def test_search_tool():
    search = SearchTool()
    res = search.execute(query="特斯拉财报")
    assert "特斯拉" in res or "检索" in res


def test_tool_chain():
    registry = ToolRegistry()
    registry.register(CalculatorTool())

    chain = ToolChain(registry=registry)
    chain.add_step(tool_name="calculator", input_key="raw_expr", output_key="calc_result")

    output = chain.execute(raw_expr="10 + 20")
    assert output["calc_result"] == "30"


def test_async_tool_executor():
    registry = ToolRegistry()
    registry.register(CalculatorTool())

    executor = AsyncToolExecutor(max_workers=2, registry=registry)
    tasks = [
        ("calculator", {"expression": "1 + 1"}),
        ("calculator", {"expression": "2 * 3"}),
    ]
    results = executor.execute_parallel(tasks)

    assert len(results) == 2
    assert results[0]["result"] == "2"
    assert results[1]["result"] == "6"


def test_memory_manager_and_tool():
    manager = MemoryManager(working_capacity=3, ttl_seconds=3600)
    tool = MemoryTool(manager=manager)

    # 1. 写入记忆
    tool.execute(action="add", content="用户偏好高风险成长股", importance=0.9)
    tool.execute(action="add", content="今日买入宁德时代", importance=0.4)

    # 2. 检索记忆
    search_res = tool.execute(action="search", content="成长股")
    assert "高风险成长股" in search_res

    # 3. 固化记忆
    consolidate_res = tool.execute(action="consolidate", content="", importance=0.8)
    assert "成功固化" in consolidate_res


def test_mcp_protocol():
    server = MCPServer(name="MockMCP")
    server.register_tool(
        name="echo",
        description="回显文字",
        handler=lambda msg: f"Echo: {msg}",
    )

    client = MCPClient(server=server)
    tools = client.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "echo"

    mcp_tool = MCPTool(client=client, tool_name="echo", description="回显工具")
    assert mcp_tool.execute(msg="Hello") == "Echo: Hello"


def test_a2a_protocol():
    server = A2AServer(agent_id="agent_alpha")
    server.register_skill("translate", lambda text: f"Translated: {text}")

    client = A2AClient(target_server=server)
    res = client.request_skill("translate", text="Agent")
    assert res == "Translated: Agent"

    a2a_tool = A2ATool(client=client, skill_name="translate")
    assert a2a_tool.execute(text="World") == "Translated: World"
