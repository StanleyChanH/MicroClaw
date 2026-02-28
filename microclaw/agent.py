"""
Agent - The AI's Brain (OpenClaw-style)

The Agent implements the agentic loop:
1. Receive message
2. Build context (system prompt + workspace + history)
3. Think (call LLM with tools)
4. Act (execute tool calls)
5. Observe (process results)
6. Repeat until done

Supports multiple providers: OpenAI, Anthropic, Ollama.
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
    """Thinking/reasoning level for the model."""
    OFF = "off"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class AgentConfig:
    """Configuration for an agent."""

    # Model settings
    model: str = "gpt-4o-mini"
    provider: str = "openai"  # openai, anthropic, ollama, openai_compatible
    temperature: float = 0.7
    max_tokens: int = 4096

    # OpenAI compatible API settings (for custom endpoints)
    base_url: Optional[str] = None  # Custom API endpoint
    api_key: Optional[str] = None   # Custom API key (falls back to env vars)

    # Agent behavior
    max_turns: int = 10  # Max tool-use turns per request
    thinking: ThinkingLevel = ThinkingLevel.OFF

    # Context window (for compaction decisions)
    context_window: int = 128000  # Default for GPT-4o

    # System prompt (can be overridden by workspace files)
    system_prompt: str = "You are a helpful AI assistant."

    # Workspace
    workspace_dir: str = "~/.microclaw/workspace"

    # Compaction
    compaction_enabled: bool = True
    compaction_reserve_tokens: int = 20000
    compaction_soft_threshold: int = 4000


@dataclass
class AgentResponse:
    """Response from an agent turn."""
    
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
    The AI agent that thinks and acts.
    
    Features:
    - Multi-provider support (OpenAI, Anthropic, Ollama)
    - Workspace integration (SOUL.md, USER.md, memory)
    - Tool execution loop
    - Session compaction
    """
    
    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        tools: Optional[ToolRegistry] = None,
    ):
        self.config = config or AgentConfig()
        self.tools = tools or ToolRegistry()
        
        # Initialize workspace
        self.workspace = WorkspaceFiles(MemoryConfig(
            workspace_dir=self.config.workspace_dir
        ))
        self.workspace.initialize_defaults()
        
        # Register built-in tools
        for tool in get_builtin_tools():
            self.tools.register(tool)
        
        # Register memory tools
        for tool in create_memory_tools(self.workspace):
            self.tools.register(tool)
        
        # Initialize LLM client
        self._client = None
        self._init_client()
        
        # Compaction
        if self.config.compaction_enabled:
            self._compactor = Compactor(
                summarize_fn=self._summarize_for_compaction,
                reserve_tokens=self.config.compaction_reserve_tokens,
                soft_threshold=self.config.compaction_soft_threshold,
            )
        else:
            self._compactor = None
    
    def _init_client(self):
        """Initialize the LLM client based on provider."""
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
                raise ImportError("openai package required: pip install openai")

        elif provider == "openai_compatible":
            # OpenAI-compatible API (DeepSeek, Moonshot, Zhipu, vLLM, LocalAI, etc.)
            try:
                from openai import OpenAI
                if not self.config.base_url:
                    raise ValueError(
                        "base_url is required for openai_compatible provider. "
                        "Set it via config or OPENAI_BASE_URL env var."
                    )
                self._client = OpenAI(
                    api_key=self.config.api_key or os.environ.get("OPENAI_API_KEY"),
                    base_url=self.config.base_url,
                )
                self._call_llm = self._call_openai
            except ImportError:
                raise ImportError("openai package required: pip install openai")

        elif provider == "anthropic":
            try:
                from anthropic import Anthropic
                self._client = Anthropic(
                    api_key=self.config.api_key,
                )
                self._call_llm = self._call_anthropic
            except ImportError:
                raise ImportError("anthropic package required: pip install anthropic")

        elif provider == "ollama":
            try:
                import ollama
                # Ollama may need custom host
                if self.config.base_url:
                    ollama.host = self.config.base_url
                self._client = ollama
                self._call_llm = self._call_ollama
            except ImportError:
                raise ImportError("ollama package required: pip install ollama")
        else:
            raise ValueError(f"Unknown provider: {provider}")
    
    def _build_system_prompt(self, is_main_session: bool = True) -> str:
        """Build the full system prompt with workspace context."""
        parts = [self.config.system_prompt]
        
        # Add workspace context
        context = self.workspace.build_context(is_main_session=is_main_session)
        if context:
            parts.append(context)
        
        return "\n\n".join(parts)
    
    def _call_openai(self, messages: List[Dict], tools: List[Dict]) -> AgentResponse:
        """Call OpenAI API."""
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
        """Call Anthropic API."""
        # Separate system message
        system = None
        anthropic_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                anthropic_messages.append(msg)
        
        # Convert tool format
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
        """Call Ollama API (local models)."""
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
        """Generate a summary for compaction."""
        # Build a prompt for summarization
        content_parts = []
        for msg in messages:
            role = msg.role.value if isinstance(msg.role, MessageRole) else msg.role
            content_parts.append(f"[{role}]: {msg.content[:500]}")
        
        prompt = "Summarize the following conversation, preserving key decisions, facts, and context:\n\n"
        prompt += "\n".join(content_parts)
        
        if instructions:
            prompt += f"\n\nFocus on: {instructions}"
        
        # Call LLM for summary
        messages_for_summary = [
            {"role": "system", "content": "You are a helpful assistant that creates concise conversation summaries."},
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
        Run the agent loop for a user message.
        
        Args:
            message: The user's message
            session: The conversation session
            on_tool_call: Callback for tool events (start/end)
            is_main_session: Whether this is a main session (affects memory loading)
            
        Returns:
            The agent's final response
        """
        # Add user message to session
        user_msg = session.add_user_message(message)
        
        # Build system prompt with workspace context
        system_prompt = self._build_system_prompt(is_main_session=is_main_session)
        
        # Get tool schemas
        tool_schemas = self.tools.schemas()
        
        # Build initial messages
        messages = session.get_messages_for_llm(system_prompt=system_prompt)
        
        # Agent loop
        for turn in range(self.config.max_turns):
            # Call the LLM
            response = self._call_llm(messages, tool_schemas)
            
            # Update token counts
            session.update_token_counts(response.input_tokens, response.output_tokens)
            
            # No tool calls = we're done
            if not response.has_tool_calls:
                final_response = response.content
                session.add_assistant_message(final_response)
                return final_response
            
            # Process tool calls
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["arguments"]
                tool_id = tool_call["id"]
                
                if on_tool_call:
                    on_tool_call("start", tool_name, tool_args)
                
                # Execute the tool
                try:
                    result = await self.tools.execute(tool_name, tool_args)
                    result_str = str(result)
                except Exception as e:
                    result_str = f"Error: {e}"
                
                if on_tool_call:
                    on_tool_call("end", tool_name, result_str)
                
                # Add to messages for next LLM call
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
                
                # Add tool result to session history
                session.add_tool_result(tool_id, result_str, tool_name)
        
        # Max turns reached
        final = "I've reached my action limit for this request."
        session.add_assistant_message(final)
        return final
    
    def run_sync(
        self,
        message: str,
        session: Session,
        on_tool_call: Optional[Callable] = None,
        is_main_session: bool = True
    ) -> str:
        """Synchronous version of run()."""
        return asyncio.run(self.run(message, session, on_tool_call, is_main_session))


# === Agent Builder ===

class AgentBuilder:
    """Fluent builder for creating agents."""

    def __init__(self):
        self._config = AgentConfig()
        self._tools = ToolRegistry()

    def model(self, model: str, provider: str = "openai") -> "AgentBuilder":
        """Set the model and provider."""
        self._config.model = model
        self._config.provider = provider
        return self

    def base_url(self, url: str) -> "AgentBuilder":
        """Set base URL for OpenAI-compatible APIs."""
        self._config.base_url = url
        return self

    def api_key(self, key: str) -> "AgentBuilder":
        """Set API key."""
        self._config.api_key = key
        return self

    def workspace(self, path: str) -> "AgentBuilder":
        """Set workspace directory."""
        self._config.workspace_dir = path
        return self

    def system(self, prompt: str) -> "AgentBuilder":
        """Set base system prompt."""
        self._config.system_prompt = prompt
        return self

    def tool(self, tool) -> "AgentBuilder":
        """Add a tool."""
        self._tools.register(tool)
        return self

    def temperature(self, temp: float) -> "AgentBuilder":
        """Set temperature."""
        self._config.temperature = temp
        return self

    def max_turns(self, turns: int) -> "AgentBuilder":
        """Set max tool turns."""
        self._config.max_turns = turns
        return self

    def thinking(self, level: ThinkingLevel) -> "AgentBuilder":
        """Set thinking level."""
        self._config.thinking = level
        return self

    def build(self) -> Agent:
        """Build the agent."""
        return Agent(config=self._config, tools=self._tools)
