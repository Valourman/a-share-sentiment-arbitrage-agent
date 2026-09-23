from src.core.config import AgentConfig
from src.core.message import Message, RoleType
from src.core.llm import HelloAgentsLLM
from src.core.agent import BaseAgent


def test_agent_config_defaults():
    cfg = AgentConfig()
    assert cfg.default_model == "gpt-4o-mini"
    assert cfg.temperature == 0.1
    assert cfg.max_retries == 2


def test_message_creation_and_conversion():
    sys_msg = Message.system("系统提示")
    assert sys_msg.role == RoleType.SYSTEM
    assert sys_msg.content == "系统提示"
    d = sys_msg.to_openai_dict()
    assert d == {"role": "system", "content": "系统提示"}

    usr_msg = Message.user("用户输入", name="Alice")
    assert usr_msg.to_openai_dict() == {"role": "user", "content": "用户输入", "name": "Alice"}


class DummyAgent(BaseAgent):
    def run(self, input_text: str, **kwargs):
        self.add_message(Message.user(input_text))
        self.add_message(Message.assistant(f"Echo: {input_text}"))
        return f"Echo: {input_text}"


def test_base_agent_lifecycle():
    agent = DummyAgent(name="TestAgent")
    res = agent.run("Hello HelloAgents")
    assert res == "Echo: Hello HelloAgents"
    assert len(agent.get_history()) == 2
    assert agent.get_history()[0].content == "Hello HelloAgents"

    agent.reset()
    assert len(agent.get_history()) == 0


def test_hello_agents_llm_unavailable_raises_runtime_error():
    empty_cfg = AgentConfig(openai_api_key=None, openai_base_url=None)
    llm = HelloAgentsLLM(config=empty_cfg)
    assert not llm.is_available
    try:
        llm.chat([Message.user("test")])
        assert False, "应当抛出 RuntimeError"
    except RuntimeError as e:
        assert "HelloAgentsLLM 未就绪" in str(e)


def test_hello_agents_llm_chat_mock():
    from unittest.mock import MagicMock
    cfg = AgentConfig(openai_api_key="sk-test", openai_base_url="https://test.api")
    llm = HelloAgentsLLM(config=cfg)
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "mock response"
    mock_resp.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_resp
    llm.client = mock_client

    msgs = [
        Message.system("sys prompt"),
        {"role": "user", "content": "hello"},
        "plain text prompt",
    ]
    res = llm.chat(msgs, model="test-model", temperature=0.5)
    assert res == "mock response"
    mock_client.chat.completions.create.assert_called_once()


class ConcreteReflectionAgent(BaseAgent):
    def execute_initial(self, input_text: str, **kwargs):
        return {"raw": input_text}

    def evaluate_critique(self, initial_result, **kwargs):
        return {"valid": True}

    def reflect_and_refine(self, initial_result, critique, **kwargs):
        return f"Refined: {initial_result['raw']}"


def test_reflection_agent_generic_flow():
    from src.agent.base_reflection import ReflectionAgent

    class TestReflect(ReflectionAgent):
        def execute_initial(self, input_text: str, **kwargs):
            return {"step": 1, "text": input_text}

        def evaluate_critique(self, initial_result, **kwargs):
            return {"is_ok": False, "reason": "need refine"}

        def reflect_and_refine(self, initial_result, critique, **kwargs):
            return {"final": f"{initial_result['text']} (fixed: {critique['reason']})"}

    agent = TestReflect(name="DemoReflector")
    res = agent.run("raw task")
    assert res["final"] == "raw task (fixed: need refine)"
    assert len(agent.get_history()) == 2
