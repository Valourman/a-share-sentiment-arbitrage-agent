import time
import uuid
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field
from src.tools.base import Tool

# 任务字典容量上限：防止长驻进程内存无界增长
_MAX_TASKS = 1024


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
    error: Optional[str] = None
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class A2ASkillError(Exception):
    """A2A 技能执行失败异常（调用方可据此与正常结果区分）"""


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
        # 追加随机后缀避免同毫秒提交的任务 ID 碰撞互相覆盖
        task_id = f"task_{self.agent_id}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        task = A2ATask(task_id=task_id, task_name=task_name, input_data=input_data)
        # 容量上限淘汰：超出时丢弃最旧任务
        if len(self._tasks) >= _MAX_TASKS:
            oldest = min(self._tasks.values(), key=lambda t: t.created_at)
            self._tasks.pop(oldest.task_id, None)
        self._tasks[task_id] = task

        # 同步派发执行（失败信息记入 error 字段而非 result，保证结果语义可区分）
        if task_name in self._skills:
            task.status = TaskStatus.RUNNING
            try:
                task.result = self._skills[task_name](**input_data)
                task.status = TaskStatus.COMPLETED
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = f"{type(e).__name__}: {e}"
        else:
            task.status = TaskStatus.FAILED
            task.error = f"未找到技能: {task_name}"

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
        # 检查任务终态：失败时抛出领域异常，避免错误字符串沿调用链静默传播
        if task.status == TaskStatus.FAILED:
            raise A2ASkillError(task.error or f"技能 '{skill_name}' 执行失败")
        return task.result


class A2ATool(Tool):
    """将 A2A 协作技能封装为当前 Agent 的普通工具"""
    def __init__(self, client: A2AClient, skill_name: str, description: str = ""):
        self.client = client
        self.skill_name = skill_name
        self.name = f"a2a_{skill_name}"
        self.description = description or f"跨智能体调用协同技能: {skill_name}"
        super().__init__()

    def execute(self, **kwargs: Any) -> Any:
        # 直接使用构造时保存的技能名，避免字符串 replace 反推在技能名
        # 本身含 "a2a_" 前缀时被错误多处替换
        return self.client.request_skill(self.skill_name, **kwargs)
