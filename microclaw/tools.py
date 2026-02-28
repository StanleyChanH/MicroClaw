"""
Tool System - The AI's superpowers

Tools are functions the AI can call to interact with the world.
This module provides:
- Tool: A callable tool definition
- ToolRegistry: Manages available tools
- @tool decorator: Easy tool registration
"""

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Tool:
    """A tool that the AI can invoke."""
    
    name: str
    description: str
    handler: Callable
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def __call__(self, **kwargs) -> Any:
        """Execute the tool with given arguments."""
        return self.handler(**kwargs)
    
    def to_schema(self) -> Dict[str, Any]:
        """Convert to JSON schema for the LLM."""
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
    """Registry of available tools."""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list(self) -> List[Tool]:
        """List all registered tools."""
        return list(self._tools.values())
    
    def schemas(self) -> List[Dict[str, Any]]:
        """Get all tool schemas for the LLM."""
        return [t.to_schema() for t in self._tools.values()]
    
    async def execute(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool by name with given arguments."""
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")
        
        # Handle both sync and async handlers
        result = tool(**arguments)
        if inspect.isawaitable(result):
            result = await result
        
        return result


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None
) -> Callable:
    """
    Decorator to create a tool from a function.
    
    Usage:
        @tool(description="Search the web")
        def web_search(query: str) -> str:
            ...
    """
    def decorator(func: Callable) -> Tool:
        # Extract parameter info from type hints and docstring
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
                "description": f"The {param_name} parameter",
            }
            
            if param.default != inspect.Parameter.empty:
                parameters[param_name]["optional"] = True
                parameters[param_name]["default"] = param.default
        
        tool_obj = Tool(
            name=name or func.__name__,
            description=description or func.__doc__ or "No description",
            handler=func,
            parameters=parameters
        )
        
        return tool_obj
    
    return decorator


# === Built-in Tools ===

@tool(description="Execute a shell command and return the output")
def shell_exec(command: str) -> str:
    """Run a shell command."""
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
            output += f"\nSTDERR: {result.stderr}"
        return output or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Command timed out"
    except Exception as e:
        return f"Error: {e}"


@tool(description="Read the contents of a file")
def read_file(path: str) -> str:
    """Read a file from disk."""
    try:
        with open(path, 'r') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"


@tool(description="Write content to a file")
def write_file(path: str, content: str) -> str:
    """Write content to a file."""
    try:
        import os
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)
        return f"Successfully wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


@tool(description="Search the web using DuckDuckGo")
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web and return results."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return "No results found"
            
            output = []
            for r in results:
                output.append(f"**{r['title']}**\n{r['href']}\n{r['body']}\n")
            return "\n".join(output)
    except ImportError:
        return "Error: duckduckgo-search not installed"
    except Exception as e:
        return f"Error searching: {e}"


def get_builtin_tools() -> List[Tool]:
    """Get all built-in tools."""
    return [shell_exec, read_file, write_file, web_search]
