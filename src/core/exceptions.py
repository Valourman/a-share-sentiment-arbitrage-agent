"""
Hello Agents 框架统一异常体系
定义基础异常及核心组件派生异常
"""

class HelloAgentsException(RuntimeError):
    """Hello Agents 框架基础根异常，兼容 RuntimeError 基础异常类型"""
    pass


class AgentException(HelloAgentsException):
    """智能体运行时与调度异常"""
    pass


class LLMException(HelloAgentsException):
    """大模型接口调用与网络异常"""
    pass


class ToolException(HelloAgentsException):
    """工具定义与执行异常"""
    pass


class ToolNotFoundException(ToolException):
    """工具未在注册表中找到异常"""
    pass


class ConfigurationException(HelloAgentsException):
    """配置加载与校验异常"""
    pass


class ProtocolException(HelloAgentsException):
    """通信协议 (MCP / A2A / ANP) 交互异常"""
    pass
