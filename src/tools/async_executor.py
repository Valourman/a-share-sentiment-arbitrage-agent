import concurrent.futures
from typing import Any, Callable, Dict, List, Optional, Tuple
from src.tools.registry import ToolRegistry, global_tool_registry


class AsyncToolExecutor:
    """
    Hello Agents 并发工具执行器
    使用线程池高效并行调度独立工具任务，避免 I/O 阻塞
    """
    def __init__(
        self,
        max_workers: int = 5,
        registry: Optional[ToolRegistry] = None,
    ):
        self.max_workers = max_workers
        self.registry = registry or global_tool_registry

    def execute_parallel(
        self,
        tasks: List[Tuple[str, Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """
        并行执行多个独立的工具调用
        :param tasks: 列表，每个元素为 (工具名称, 参数字典)
        :return: 执行结果列表，包含 tool_name, status, result / error
        """
        results: List[Dict[str, Any]] = [{} for _ in tasks]

        def _run_single(index: int, tool_name: str, kwargs: Dict[str, Any]):
            try:
                tool = self.registry.get(tool_name)
                if not tool:
                    return index, {
                        "tool_name": tool_name,
                        "status": "error",
                        "error": f"工具 '{tool_name}' 未注册",
                    }
                output = tool.execute(**kwargs)
                return index, {
                    "tool_name": tool_name,
                    "status": "success",
                    "result": output,
                }
            except Exception as e:
                return index, {
                    "tool_name": tool_name,
                    "status": "error",
                    "error": str(e),
                }

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_idx = {
                executor.submit(_run_single, i, t[0], t[1]): i
                for i, t in enumerate(tasks)
            }
            for future in concurrent.futures.as_completed(future_to_idx):
                idx, res = future.result()
                results[idx] = res

        return results
