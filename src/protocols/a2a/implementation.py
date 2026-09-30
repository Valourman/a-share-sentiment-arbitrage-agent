import time
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field
from src.tools.base import Tool


class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class A2ATask(BaseModel):
    """A2A 跨智能体协作任务实体"""
    task_id: str
    task_name: str
    input_data: Dict[str, Any]
    status: str = TaskStatus.PENDING
    result: Optional[Any] = None
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class A2AServer:
    """
    Hello Agents A2A 服务端点
    注册与暴露智能体特定技能 (Skills)，托管跨 Agent 协作任务生命周期
    """
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._skills: Dict[str, Callable[..., Any]] = {}
        self._tasks: Dict[str, A2ATask] = {}

    def register_skill(self, skill_name: str, handler: Callable[..., Any]) -> None:
        self._skills[skill_name] = handler

    def submit_task(self, task_name: str, input_data: Dict[str, Any]) -> A2ATask:
        task_id = f"task_{self.agent_id}_{int(time.time() * 1000)}"
        task = A2ATask(task_id=task_id, task_name=task_name, input_data=input_data)
        self._tasks[task_id] = task

        # 同步/异步派发执行
        if task_name in self._skills:
            task.status = TaskStatus.RUNNING
            try:
                task.result = self._skills[task_name](**input_data)
                task.status = TaskStatus.COMPLETED
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.result = str(e)
        else:
            task.status = TaskStatus.FAILED
            task.result = f"未找到技能: {task_name}"

        return task

    def get_task(self, task_id: str) -> Optional[A2ATask]:
        return self._tasks.get(task_id)


class A2AClient:
    """
    Hello Agents A2A 客户端
    向目标协作智能体端点提交任务并拉取工件
    """
    def __init__(self, target_server: A2AServer):
        self.server = target_server

    def request_skill(self, skill_name: str, **kwargs: Any) -> Any:
        task = self.server.submit_task(skill_name, kwargs)
        return task.result


class A2ATool(Tool):
    """将 A2A 协作技能封装为当前 Agent 的普通工具"""
    def __init__(self, client: A2AClient, skill_name: str, description: str = ""):
        self.client = client
        self.name = f"a2a_{skill_name}"
        self.description = description or f"跨智能体调用协同技能: {skill_name}"
        super().__init__()

    def execute(self, **kwargs: Any) -> Any:
        return self.client.request_skill(self.name.replace("a2a_", ""), **kwargs)
