"""
工具系统 - AI 的超能力

工具是 AI 可以调用以与外界交互的函数。
本模块提供:
- Tool: 可调用的工具定义
- ToolRegistry: 管理可用工具
- @tool 装饰器: 简单的工具注册方式
"""

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Tool:
    """AI 可以调用的工具。"""

    name: str
    description: str
    handler: Callable
    parameters: Dict[str, Any] = field(default_factory=dict)

    def __call__(self, **kwargs) -> Any:
        """使用给定参数执行工具。"""
        return self.handler(**kwargs)

    def to_schema(self) -> Dict[str, Any]:
        """转换为 LLM 的 JSON Schema。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": [
                        k for k, v in self.parameters.items()
                        if not v.get("optional", False)
                    ]
                }
            }
        }


class ToolRegistry:
    """可用工具的注册表。"""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """注册工具。"""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        """按名称获取工具。"""
        return self._tools.get(name)

    def list(self) -> List[Tool]:
        """列出所有已注册的工具。"""
        return list(self._tools.values())

    def schemas(self) -> List[Dict[str, Any]]:
        """获取所有工具的 JSON Schema。"""
        return [t.to_schema() for t in self._tools.values()]

    async def execute(self, name: str, arguments: Dict[str, Any]) -> Any:
        """按名称使用给定参数执行工具。"""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"未知的工具: {name}")

        # 同时支持同步和异步处理器
        result = tool(**arguments)
        if inspect.isawaitable(result):
            result = await result

        return result


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None
) -> Callable:
    """
    从函数创建工具的装饰器。

    用法:
        @tool(description="搜索网络")
        def web_search(query: str) -> str:
            ...
    """
    def decorator(func: Callable) -> Tool:
        # 从类型提示和文档字符串提取参数信息
        sig = inspect.signature(func)
        hints = func.__annotations__

        parameters = {}
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue

            param_type = hints.get(param_name, Any)
            type_map = {
                str: "string",
                int: "integer",
                float: "number",
                bool: "boolean",
                list: "array",
                dict: "object",
            }

            parameters[param_name] = {
                "type": type_map.get(param_type, "string"),
                "description": f"{param_name} 参数",
            }

            if param.default != inspect.Parameter.empty:
                parameters[param_name]["optional"] = True
                parameters[param_name]["default"] = param.default

        tool_obj = Tool(
            name=name or func.__name__,
            description=description or func.__doc__ or "无描述",
            handler=func,
            parameters=parameters
        )

        return tool_obj

    return decorator


# === 内置工具 ===

@tool(description="执行 shell 命令并返回输出")
def shell_exec(command: str) -> str:
    """运行 shell 命令。"""
    import subprocess
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout
        if result.stderr:
            output += f"\n标准错误: {result.stderr}"
        return output or "(无输出)"
    except subprocess.TimeoutExpired:
        return "错误: 命令超时"
    except Exception as e:
        return f"错误: {e}"


@tool(description="读取文件内容")
def read_file(path: str) -> str:
    """从磁盘读取文件。"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"读取文件错误: {e}"


@tool(description="将内容写入文件")
def write_file(path: str, content: str) -> str:
    """将内容写入文件。"""
    try:
        import os
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"成功写入 {len(content)} 字节到 {path}"
    except Exception as e:
        return f"写入文件错误: {e}"


@tool(description="使用 DuckDuckGo 搜索网络")
def web_search(query: str, max_results: int = 5) -> str:
    """搜索网络并返回结果。"""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return "未找到结果"

            output = []
            for r in results:
                output.append(f"**{r['title']}**\n{r['href']}\n{r['body']}\n")
            return "\n".join(output)
    except ImportError:
        return "错误: 未安装 duckduckgo-search"
    except Exception as e:
        return f"搜索错误: {e}"


def get_builtin_tools() -> List[Tool]:
    """获取所有内置工具。"""
    return [shell_exec, read_file, write_file, web_search]
