import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from src.core.message import Message, RoleType


class MemoryEntry(BaseModel):
    """记忆条目实体"""
    content: str
    user_id: str = "default_user"
    role: str = "user"
    importance: float = Field(default=0.5, ge=0.0, le=1.0, description="重要性权重 (0~1)")
    created_at: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkingMemory:
    """
    工作记忆 (短时信息处理)
    纯内存高速存储，支持容量上限 (默认 50 条) 与生存时间 (TTL) 过期淘汰
    """
    def __init__(self, capacity: int = 50, ttl_seconds: Optional[float] = 3600):
        self.capacity = capacity
        self.ttl_seconds = ttl_seconds
        self._entries: List[MemoryEntry] = []

    def _cleanup_expired(self) -> None:
        """清理已超出 TTL 的条目"""
        if not self.ttl_seconds:
            return
        now = time.time()
        self._entries = [
            e for e in self._entries if (now - e.created_at) < self.ttl_seconds
        ]

    def add(self, content: str, role: str = "user", importance: float = 0.5, user_id: str = "default_user") -> MemoryEntry:
        self._cleanup_expired()
        entry = MemoryEntry(content=content, role=role, importance=importance, user_id=user_id)
        self._entries.append(entry)
        if len(self._entries) > self.capacity:
            # 淘汰最早的低重要性条目
            self._entries.pop(0)
        return entry

    def search(self, query: str, user_id: str = "default_user", top_k: int = 5) -> List[MemoryEntry]:
        self._cleanup_expired()
        results = []
        q_lower = query.lower()
        for e in reversed(self._entries):
            if e.user_id == user_id:
                if q_lower in e.content.lower():
                    results.append(e)
                    if len(results) >= top_k:
                        break
        return results

    def get_all(self, user_id: str = "default_user") -> List[MemoryEntry]:
        self._cleanup_expired()
        return [e for e in self._entries if e.user_id == user_id]

    def clear(self, user_id: Optional[str] = None) -> None:
        if user_id:
            self._entries = [e for e in self._entries if e.user_id != user_id]
        else:
            self._entries.clear()


class MemoryManager:
    """
    Hello Agents 统一记忆管理器
    协调短时工作记忆与持久长期记忆，提供固化 (consolidate) 与遗忘 (forget)
    """
    def __init__(self, working_capacity: int = 50, ttl_seconds: float = 3600):
        self.working_memory = WorkingMemory(capacity=working_capacity, ttl_seconds=ttl_seconds)
        self.long_term_memory: List[MemoryEntry] = []

    def add(
        self,
        content: str,
        role: str = "user",
        importance: float = 0.5,
        user_id: str = "default_user",
    ) -> MemoryEntry:
        """追加一条记忆到工作记忆"""
        entry = self.working_memory.add(content=content, role=role, importance=importance, user_id=user_id)
        # 高重要性记忆直接沉淀至长期记忆 (阈值 >= 0.8)
        if importance >= 0.8:
            self.long_term_memory.append(entry)
        return entry

    def search(self, query: str, user_id: str = "default_user", top_k: int = 5) -> List[MemoryEntry]:
        """跨工作记忆与长期记忆联合搜索"""
        seen = set()
        matched = []

        # 1. 检索工作记忆
        working_res = self.working_memory.search(query, user_id=user_id, top_k=top_k)
        for r in working_res:
            matched.append(r)
            seen.add(r.content)

        # 2. 检索长期记忆补充
        for e in reversed(self.long_term_memory):
            if len(matched) >= top_k:
                break
            if e.user_id == user_id and query.lower() in e.content.lower() and e.content not in seen:
                matched.append(e)
                seen.add(e.content)

        return matched

    def consolidate(self, importance_threshold: float = 0.6, user_id: str = "default_user") -> int:
        """
        记忆固化操作：筛选工作记忆中达到重要性阈值的条目，永久跃迁至长期记忆库
        """
        working_items = self.working_memory.get_all(user_id=user_id)
        consolidated_count = 0
        existing_contents = {e.content for e in self.long_term_memory if e.user_id == user_id}

        for item in working_items:
            if item.importance >= importance_threshold and item.content not in existing_contents:
                self.long_term_memory.append(item)
                existing_contents.add(item.content)
                consolidated_count += 1

        return consolidated_count

    def forget(self, query: Optional[str] = None, importance_below: Optional[float] = None, user_id: str = "default_user") -> int:
        """选择性遗忘机制：根据匹配内容或过低重要度清理长期记忆"""
        initial_len = len(self.long_term_memory)
        self.long_term_memory = [
            e for e in self.long_term_memory
            if not (
                e.user_id == user_id
                and ((query and query.lower() in e.content.lower()) or (importance_below is not None and e.importance < importance_below))
            )
        ]
        return initial_len - len(self.long_term_memory)
