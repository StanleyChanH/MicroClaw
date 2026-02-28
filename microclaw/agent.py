"""
Agent - AI 的大脑 (OpenClaw 风格)

Agent 实现了智能体循环:
1. 接收消息
2. 构建上下文 (系统提示 + 工作区 + 历史记录)
3. 思考 (调用 LLM 并使用工具)
4. 行动 (执行工具调用)
5. 观察 (处理结果)
6. 循环直到完成

支持多种提供商: OpenAI、Anthropic、Ollama。
"""

import asyncio
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

from .memory import MemoryConfig, WorkspaceFiles, create_memory_tools
from .session import Compactor, Message, MessageRole, Session
from .tools import ToolRegistry, get_builtin_tools


class ThinkingLevel(str, Enum):
    """模型的思考/推理级别。"""
    OFF = "off"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class AgentConfig:
    """Agent 配置。"""

    # 模型设置
    model: str = "gpt-4o-mini"
    provider: str = "openai"  # openai, anthropic, ollama, openai_compatible
    temperature: float = 0.7
    max_tokens: int = 4096

    # OpenAI 兼容 API 设置 (用于自定义端点)
    base_url: Optional[str] = None  # 自定义 API 端点
    api_key: Optional[str] = None   # 自定义 API 密钥 (回退到环境变量)

    # Agent 行为
    max_turns: int = 10  # 每次请求最大工具调用轮数
    thinking: ThinkingLevel = ThinkingLevel.OFF

    # 上下文窗口 (用于压缩决策)
    context_window: int = 128000  # GPT-4o 默认值

    # 系统提示 (可被工作区文件覆盖)
    system_prompt: str = "你是一个有帮助的 AI 助手。"

    # 工作区
    workspace_dir: str = "~/.microclaw/workspace"

    # 压缩
    compaction_enabled: bool = True
    compaction_reserve_tokens: int = 20000
    compaction_soft_threshold: int = 4000


@dataclass
class AgentResponse:
    """Agent 轮次的响应。"""

    content: str
    tool_calls: List[Dict] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    thinking: Optional[str] = None

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class Agent:
    """
    会思考和行动的 AI Agent。

    特性:
    - 多提供商支持 (OpenAI、Anthropic、Ollama)
    - 工作区集成 (SOUL.md、USER.md、memory)
    - 工具执行循环
    - 会话压缩
    """

    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        tools: Optional[ToolRegistry] = None,
    ):
        self.config = config or AgentConfig()
        self.tools = tools or ToolRegistry()

        # 初始化工作区
        self.workspace = WorkspaceFiles(MemoryConfig(
            workspace_dir=self.config.workspace_dir
        ))
        self.workspace.initialize_defaults()

        # 设置工作区环境变量，供工具使用
        import os
        os.environ['MICROCLAW_WORKSPACE'] = str(self.workspace.workspace)

        # 注册内置工具
        for tool in get_builtin_tools():
            self.tools.register(tool)

        # 注册记忆工具
        for tool in create_memory_tools(self.workspace):
            self.tools.register(tool)

        # 初始化 LLM 客户端
        self._client = None
        self._init_client()

        # 压缩器
        if self.config.compaction_enabled:
            self._compactor = Compactor(
                summarize_fn=self._summarize_for_compaction,
                reserve_tokens=self.config.compaction_reserve_tokens,
                soft_threshold=self.config.compaction_soft_threshold,
            )
        else:
            self._compactor = None

    def _init_client(self):
        """根据提供商初始化 LLM 客户端。"""
        import os
        provider = self.config.provider.lower()

        if provider == "openai":
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.config.api_key,
                    base_url=self.config.base_url,
                )
                self._call_llm = self._call_openai
            except ImportError:
                raise ImportError("需要安装 openai 包: pip install openai")

        elif provider == "openai_compatible":
            # OpenAI 兼容 API (DeepSeek、Moonshot、智谱、vLLM、LocalAI 等)
            try:
                from openai import OpenAI
                if not self.config.base_url:
                    raise ValueError(
                        "openai_compatible 提供商需要设置 base_url。"
                        "通过配置或 OPENAI_BASE_URL 环境变量设置。"
                    )
                self._client = OpenAI(
                    api_key=self.config.api_key or os.environ.get("OPENAI_API_KEY"),
                    base_url=self.config.base_url,
                )
                self._call_llm = self._call_openai
            except ImportError:
                raise ImportError("需要安装 openai 包: pip install openai")

        elif provider == "anthropic":
            try:
                from anthropic import Anthropic
                self._client = Anthropic(
                    api_key=self.config.api_key,
                )
                self._call_llm = self._call_anthropic
            except ImportError:
                raise ImportError("需要安装 anthropic 包: pip install anthropic")

        elif provider == "ollama":
            try:
                import ollama
                # Ollama 可能需要自定义主机
                if self.config.base_url:
                    ollama.host = self.config.base_url
                self._client = ollama
                self._call_llm = self._call_ollama
            except ImportError:
                raise ImportError("需要安装 ollama 包: pip install ollama")
        else:
            raise ValueError(f"未知的提供商: {provider}")

    def _build_system_prompt(self, is_main_session: bool = True) -> str:
        """构建带有工作区上下文的完整系统提示。"""
        parts = [self.config.system_prompt]

        # 添加工作区上下文
        context = self.workspace.build_context(is_main_session=is_main_session)
        if context:
            parts.append(context)

        return "\n\n".join(parts)

    def _call_openai(self, messages: List[Dict], tools: List[Dict]) -> AgentResponse:
        """调用 OpenAI API。"""
        kwargs = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = self._client.chat.completions.create(**kwargs)
        msg = response.choices[0].message
        usage = response.usage

        result = AgentResponse(
            content=msg.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

        if msg.tool_calls:
            for tc in msg.tool_calls:
                result.tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments)
                })

        return result

    def _call_anthropic(self, messages: List[Dict], tools: List[Dict]) -> AgentResponse:
        """调用 Anthropic API。"""
        # 分离系统消息
        system = None
        anthropic_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                anthropic_messages.append(msg)

        # 转换工具格式
        anthropic_tools = []
        for t in tools:
            anthropic_tools.append({
                "name": t["function"]["name"],
                "description": t["function"]["description"],
                "input_schema": t["function"]["parameters"]
            })

        kwargs = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": anthropic_messages,
        }

        if system:
            kwargs["system"] = system
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        response = self._client.messages.create(**kwargs)

        result = AgentResponse(
            content="",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        for block in response.content:
            if block.type == "text":
                result.content = block.text
            elif block.type == "tool_use":
                result.tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input
                })

        return result

    def _call_ollama(self, messages: List[Dict], tools: List[Dict]) -> AgentResponse:
        """调用 Ollama API (本地模型)。"""
        response = self._client.chat(
            model=self.config.model,
            messages=messages,
            tools=tools if tools else None
        )

        msg = response["message"]
        result = AgentResponse(
            content=msg.get("content", ""),
        )

        if "tool_calls" in msg:
            for tc in msg["tool_calls"]:
                result.tool_calls.append({
                    "id": tc.get("id", ""),
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"]
                })

        return result

    async def _summarize_for_compaction(
        self,
        messages: List[Message],
        instructions: Optional[str] = None
    ) -> str:
        """为压缩生成摘要。"""
        # 构建摘要提示
        content_parts = []
        for msg in messages:
            role = msg.role.value if isinstance(msg.role, MessageRole) else msg.role
            content_parts.append(f"[{role}]: {msg.content[:500]}")

        prompt = "请总结以下对话，保留关键决策、事实和上下文:\n\n"
        prompt += "\n".join(content_parts)

        if instructions:
            prompt += f"\n\n重点关注: {instructions}"

        # 调用 LLM 生成摘要
        messages_for_summary = [
            {"role": "system", "content": "你是一个帮助创建简洁对话摘要的助手。"},
            {"role": "user", "content": prompt}
        ]

        response = self._call_llm(messages_for_summary, [])
        return response.content

    async def run(
        self,
        message: str,
        session: Session,
        on_tool_call: Optional[Callable] = None,
        is_main_session: bool = True
    ) -> str:
        """
        为用户消息运行 Agent 循环。

        参数:
            message: 用户消息
            session: 对话会话
            on_tool_call: 工具事件回调 (start/end)
            is_main_session: 是否为主会话 (影响记忆加载)

        返回:
            Agent 的最终响应
        """
        # 将用户消息添加到会话
        user_msg = session.add_user_message(message)

        # 构建带有工作区上下文的系统提示
        system_prompt = self._build_system_prompt(is_main_session=is_main_session)

        # 获取工具模式
        tool_schemas = self.tools.schemas()

        # 构建初始消息
        messages = session.get_messages_for_llm(system_prompt=system_prompt)

        # Agent 循环
        for turn in range(self.config.max_turns):
            # 调用 LLM
            response = self._call_llm(messages, tool_schemas)

            # 更新 token 计数
            session.update_token_counts(response.input_tokens, response.output_tokens)

            # 没有工具调用 = 完成
            if not response.has_tool_calls:
                final_response = response.content
                session.add_assistant_message(final_response)
                return final_response

            # 处理工具调用
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["arguments"]
                tool_id = tool_call["id"]

                if on_tool_call:
                    on_tool_call("start", tool_name, tool_args)

                # 执行工具
                try:
                    result = await self.tools.execute(tool_name, tool_args)
                    result_str = str(result)
                except Exception as e:
                    result_str = f"错误: {e}"

                if on_tool_call:
                    on_tool_call("end", tool_name, result_str)

                # 添加到消息以供下次 LLM 调用
                messages.append({
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": [{
                        "id": tool_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(tool_args)
                        }
                    }]
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": result_str
                })

                # 将工具结果添加到会话历史
                session.add_tool_result(tool_id, result_str, tool_name)

        # 达到最大轮数
        final = "我已达到本次请求的操作限制。"
        session.add_assistant_message(final)
        return final

    def run_sync(
        self,
        message: str,
        session: Session,
        on_tool_call: Optional[Callable] = None,
        is_main_session: bool = True
    ) -> str:
        """run() 的同步版本。"""
        return asyncio.run(self.run(message, session, on_tool_call, is_main_session))


# === Agent 构建器 ===

class AgentBuilder:
    """流式构建 Agent 的工具类。"""

    def __init__(self):
        self._config = AgentConfig()
        self._tools = ToolRegistry()

    def model(self, model: str, provider: str = "openai") -> "AgentBuilder":
        """设置模型和提供商。"""
        self._config.model = model
        self._config.provider = provider
        return self

    def base_url(self, url: str) -> "AgentBuilder":
        """设置 OpenAI 兼容 API 的基础 URL。"""
        self._config.base_url = url
        return self

    def api_key(self, key: str) -> "AgentBuilder":
        """设置 API 密钥。"""
        self._config.api_key = key
        return self

    def workspace(self, path: str) -> "AgentBuilder":
        """设置工作区目录。"""
        self._config.workspace_dir = path
        return self

    def system(self, prompt: str) -> "AgentBuilder":
        """设置基础系统提示。"""
        self._config.system_prompt = prompt
        return self

    def tool(self, tool) -> "AgentBuilder":
        """添加工具。"""
        self._tools.register(tool)
        return self

    def temperature(self, temp: float) -> "AgentBuilder":
        """设置温度。"""
        self._config.temperature = temp
        return self

    def max_turns(self, turns: int) -> "AgentBuilder":
        """设置最大工具轮数。"""
        self._config.max_turns = turns
        return self

    def thinking(self, level: ThinkingLevel) -> "AgentBuilder":
        """设置思考级别。"""
        self._config.thinking = level
        return self

    def build(self) -> Agent:
        """构建 Agent。"""
        return Agent(config=self._config, tools=self._tools)
