"""
会话管理 - OpenClaw 风格

MicroClaw 的会话设计参考了 OpenClaw:
- 会话键: 私聊使用 `agent:<agentId>:<key>`，群聊使用 `agent:<agentId>:<channel>:group:<id>`
- 每日重置: 会话在可配置的时间点过期 (默认凌晨 4 点)
- 空闲重置: 可选的不活动超时
- 压缩: 接近 token 限制时总结旧上下文
- JSONL 转录: 追加式日志记录完整历史
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

# === 消息类型 ===

class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    COMPACTION = "compaction"  # 特殊: 压缩后的摘要


@dataclass
class Message:
    """对话中的单条消息。"""

    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    name: Optional[str] = None  # 用于工具结果
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 JSONL 存储。"""
        data = {
            "role": self.role.value if isinstance(self.role, MessageRole) else self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.name:
            data["name"] = self.name
        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            data["tool_calls"] = self.tool_calls
        if self.metadata:
            data["metadata"] = self.metadata
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """从存储反序列化。"""
        role = data["role"]
        if isinstance(role, str):
            role = MessageRole(role)
        return cls(
            role=role,
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
            name=data.get("name"),
            tool_call_id=data.get("tool_call_id"),
            tool_calls=data.get("tool_calls"),
            metadata=data.get("metadata", {})
        )

    def to_openai(self) -> Dict[str, Any]:
        """转换为 OpenAI 消息格式。"""
        msg = {"role": self.role.value if isinstance(self.role, MessageRole) else self.role}

        # 处理压缩摘要
        if self.role == MessageRole.COMPACTION:
            msg["role"] = "system"
            msg["content"] = f"[之前的对话摘要]\n{self.content}"
            return msg

        msg["content"] = self.content

        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            msg["tool_calls"] = self.tool_calls
        if self.name:
            msg["name"] = self.name

        return msg


# === 会话键工具 ===

@dataclass
class SessionKey:
    """
    遵循 OpenClaw 规范的结构化会话键。

    格式: agent:<agentId>:<type>:<identifier>
    示例:
        - agent:main:main (主私聊会话)
        - agent:main:whatsapp:group:123456 (WhatsApp 群组)
        - agent:main:dm:+1234567890 (按用户的私聊)
        - cron:daily-report (定时任务)
    """

    raw: str
    agent_id: str = "main"
    session_type: str = "main"  # main, dm, group, channel
    identifier: Optional[str] = None
    channel: Optional[str] = None

    @classmethod
    def parse(cls, key: str) -> "SessionKey":
        """解析会话键字符串。"""
        parts = key.split(":")

        if parts[0] == "agent" and len(parts) >= 3:
            agent_id = parts[1]

            if len(parts) == 3:
                # agent:main:main
                return cls(raw=key, agent_id=agent_id, session_type=parts[2])
            elif len(parts) == 4:
                # agent:main:dm:user123
                return cls(raw=key, agent_id=agent_id, session_type=parts[2], identifier=parts[3])
            elif len(parts) >= 5:
                # agent:main:whatsapp:group:123
                return cls(
                    raw=key,
                    agent_id=agent_id,
                    channel=parts[2],
                    session_type=parts[3],
                    identifier=":".join(parts[4:])
                )

        # 简单键的回退处理
        return cls(raw=key, session_type=key)

    @classmethod
    def for_dm(cls, agent_id: str = "main", peer_id: Optional[str] = None, channel: Optional[str] = None) -> "SessionKey":
        """创建私聊会话键。"""
        if peer_id and channel:
            key = f"agent:{agent_id}:{channel}:dm:{peer_id}"
        elif peer_id:
            key = f"agent:{agent_id}:dm:{peer_id}"
        else:
            key = f"agent:{agent_id}:main"
        return cls.parse(key)

    @classmethod
    def for_group(cls, group_id: str, agent_id: str = "main", channel: str = "unknown") -> "SessionKey":
        """创建群聊会话键。"""
        key = f"agent:{agent_id}:{channel}:group:{group_id}"
        return cls.parse(key)

    def __str__(self) -> str:
        return self.raw


# === 重置策略 ===

@dataclass
class ResetPolicy:
    """
    会话重置策略 (OpenClaw 风格)。

    模式:
    - daily: 每天在指定时间重置
    - idle: 不活动 N 分钟后重置
    - both: 以先触发的为准
    """

    mode: Literal["daily", "idle", "both"] = "daily"
    at_hour: int = 4  # 每日重置的小时 (0-23, 本地时间)
    idle_minutes: Optional[int] = None

    def is_expired(self, last_update: datetime, now: Optional[datetime] = None) -> bool:
        """检查会话是否应该重置。"""
        now = now or datetime.now()

        if self.mode in ("daily", "both"):
            # 找到最近的重置时间
            reset_today = now.replace(hour=self.at_hour, minute=0, second=0, microsecond=0)
            if now < reset_today:
                reset_today -= timedelta(days=1)

            if last_update < reset_today:
                return True

        if self.mode in ("idle", "both") and self.idle_minutes:
            idle_threshold = now - timedelta(minutes=self.idle_minutes)
            if last_update < idle_threshold:
                return True

        return False


# === 会话 ===

@dataclass
class Session:
    """
    具有 OpenClaw 风格特性的对话会话。

    特性:
    - 结构化会话键
    - 具有 JSONL 持久化的消息历史
    - Token 追踪
    - 压缩支持
    - 重置策略
    """

    key: SessionKey
    session_id: str  # 此会话实例的唯一 ID
    messages: List[Message] = field(default_factory=list)

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Token 追踪
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    # 压缩
    compaction_count: int = 0
    last_compaction_at: Optional[datetime] = None

    # 来源元数据 (此会话的来源)
    origin: Dict[str, Any] = field(default_factory=dict)

    # 状态 (任意会话范围的数据)
    state: Dict[str, Any] = field(default_factory=dict)

    def add_message(
        self,
        role: MessageRole,
        content: str,
        **kwargs
    ) -> Message:
        """向会话添加消息。"""
        msg = Message(role=role, content=content, **kwargs)
        self.messages.append(msg)
        self.updated_at = datetime.now()
        return msg

    def add_user_message(self, content: str, **metadata) -> Message:
        return self.add_message(MessageRole.USER, content, metadata=metadata)

    def add_assistant_message(self, content: str, tool_calls: Optional[List] = None) -> Message:
        return self.add_message(MessageRole.ASSISTANT, content, tool_calls=tool_calls)

    def add_tool_result(self, tool_call_id: str, content: str, name: str) -> Message:
        return self.add_message(
            MessageRole.TOOL,
            content,
            tool_call_id=tool_call_id,
            name=name
        )

    def get_messages_for_llm(
        self,
        system_prompt: Optional[str] = None,
        max_messages: Optional[int] = None
    ) -> List[Dict]:
        """获取格式化为 LLM API 的消息。"""
        result = []

        if system_prompt:
            result.append({"role": "system", "content": system_prompt})

        messages = self.messages
        if max_messages:
            messages = messages[-max_messages:]

        for msg in messages:
            result.append(msg.to_openai())

        return result

    def update_token_counts(self, input_tokens: int, output_tokens: int):
        """更新 token 使用追踪。"""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens = self.input_tokens + self.output_tokens

    def to_dict(self) -> Dict[str, Any]:
        """序列化会话元数据 (不含消息 - 消息存储到 JSONL)。"""
        return {
            "key": str(self.key),
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "compaction_count": self.compaction_count,
            "last_compaction_at": self.last_compaction_at.isoformat() if self.last_compaction_at else None,
            "origin": self.origin,
            "state": self.state,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], messages: List[Message] = None) -> "Session":
        """反序列化会话。"""
        return cls(
            key=SessionKey.parse(data["key"]),
            session_id=data["session_id"],
            messages=messages or [],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
            compaction_count=data.get("compaction_count", 0),
            last_compaction_at=datetime.fromisoformat(data["last_compaction_at"]) if data.get("last_compaction_at") else None,
            origin=data.get("origin", {}),
            state=data.get("state", {}),
        )


# === 会话存储 (基于 JSONL, 类似 OpenClaw) ===

class SessionStore:
    """
    OpenClaw 风格的会话存储。

    结构:
    - sessions.json: 所有会话的元数据
    - <session_id>.jsonl: 每个会话的消息转录
    """

    def __init__(self, storage_dir: str, reset_policy: Optional[ResetPolicy] = None):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.reset_policy = reset_policy or ResetPolicy()

        # 内存缓存
        self._sessions: Dict[str, Session] = {}
        self._metadata: Dict[str, Dict] = {}

        # 加载现有会话
        self._load_metadata()

    @property
    def _metadata_path(self) -> Path:
        return self.storage_dir / "sessions.json"

    def _transcript_path(self, session_id: str) -> Path:
        return self.storage_dir / f"{session_id}.jsonl"

    def _load_metadata(self):
        """从 sessions.json 加载会话元数据。"""
        if self._metadata_path.exists():
            try:
                with open(self._metadata_path, 'r', encoding='utf-8') as f:
                    self._metadata = json.load(f)
            except Exception:
                self._metadata = {}

    def _save_metadata(self):
        """保存会话元数据到 sessions.json。"""
        with open(self._metadata_path, 'w', encoding='utf-8') as f:
            json.dump(self._metadata, f, indent=2, ensure_ascii=False)

    def _load_transcript(self, session_id: str) -> List[Message]:
        """从 JSONL 转录文件加载消息。"""
        messages = []
        path = self._transcript_path(session_id)

        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            messages.append(Message.from_dict(data))
                        except Exception:
                            pass

        return messages

    def _append_to_transcript(self, session_id: str, message: Message):
        """追加消息到 JSONL 转录文件。"""
        path = self._transcript_path(session_id)
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(message.to_dict(), ensure_ascii=False) + "\n")

    def _generate_session_id(self) -> str:
        """生成唯一的会话 ID。"""
        import uuid
        return uuid.uuid4().hex[:12]

    def get(self, key: str | SessionKey) -> Session:
        """
        获取或创建会话。

        处理:
        - 会话过期 (每日/空闲重置)
        - 从磁盘加载
        - 创建新会话
        """
        if isinstance(key, str):
            key = SessionKey.parse(key)

        key_str = str(key)

        # 检查会话是否存在且仍然有效
        if key_str in self._metadata:
            meta = self._metadata[key_str]
            updated_at = datetime.fromisoformat(meta["updated_at"])

            if self.reset_policy.is_expired(updated_at):
                # 会话已过期 - 创建新的
                return self._create_session(key)

            # 从缓存或磁盘加载
            if key_str not in self._sessions:
                messages = self._load_transcript(meta["session_id"])
                self._sessions[key_str] = Session.from_dict(meta, messages)

            return self._sessions[key_str]

        # 创建新会话
        return self._create_session(key)

    def _create_session(self, key: SessionKey) -> Session:
        """创建新会话。"""
        session_id = self._generate_session_id()
        session = Session(key=key, session_id=session_id)

        key_str = str(key)
        self._sessions[key_str] = session
        self._metadata[key_str] = session.to_dict()
        self._save_metadata()

        return session

    def save(self, session: Session, message: Optional[Message] = None):
        """
        保存会话状态。

        如果提供了消息，将其追加到转录文件。
        始终更新元数据。
        """
        key_str = str(session.key)

        if message:
            self._append_to_transcript(session.session_id, message)

        self._metadata[key_str] = session.to_dict()
        self._save_metadata()

    def reset(self, key: str | SessionKey) -> Session:
        """强制重置会话 (如 /new 或 /reset)。"""
        if isinstance(key, str):
            key = SessionKey.parse(key)
        return self._create_session(key)

    def list(self, active_minutes: Optional[int] = None) -> List[Dict]:
        """列出所有会话，可选按活动时间过滤。"""
        now = datetime.now()
        results = []

        for key, meta in self._metadata.items():
            updated_at = datetime.fromisoformat(meta["updated_at"])

            if active_minutes:
                threshold = now - timedelta(minutes=active_minutes)
                if updated_at < threshold:
                    continue

            results.append({
                "key": key,
                "session_id": meta["session_id"],
                "updated_at": meta["updated_at"],
                "total_tokens": meta.get("total_tokens", 0),
            })

        return sorted(results, key=lambda x: x["updated_at"], reverse=True)

    def delete(self, key: str | SessionKey) -> bool:
        """删除会话。"""
        if isinstance(key, str):
            key = SessionKey.parse(key)

        key_str = str(key)

        if key_str in self._metadata:
            session_id = self._metadata[key_str]["session_id"]

            # 删除转录文件
            transcript = self._transcript_path(session_id)
            if transcript.exists():
                transcript.unlink()

            # 从元数据中删除
            del self._metadata[key_str]
            self._save_metadata()

            # 从缓存中删除
            if key_str in self._sessions:
                del self._sessions[key_str]

            return True

        return False


# === 压缩 ===

class Compactor:
    """
    处理会话压缩 (总结旧上下文)。

    当会话接近上下文窗口限制时，压缩器会:
    1. 获取较早的消息
    2. 通过 LLM 总结它们
    3. 用压缩消息替换它们
    """

    def __init__(
        self,
        summarize_fn,  # 接收消息并返回摘要的可调用对象
        reserve_tokens: int = 20000,
        soft_threshold: int = 4000,
    ):
        self.summarize_fn = summarize_fn
        self.reserve_tokens = reserve_tokens
        self.soft_threshold = soft_threshold

    def should_compact(self, session: Session, context_window: int, current_tokens: int) -> bool:
        """检查是否需要压缩。"""
        available = context_window - self.reserve_tokens - self.soft_threshold
        return current_tokens > available

    async def compact(
        self,
        session: Session,
        keep_recent: int = 10,
        instructions: Optional[str] = None
    ) -> str:
        """
        压缩会话历史。

        返回摘要文本。
        """
        if len(session.messages) <= keep_recent:
            return ""

        # 分割消息
        to_summarize = session.messages[:-keep_recent]
        to_keep = session.messages[-keep_recent:]

        # 生成摘要
        summary = await self.summarize_fn(to_summarize, instructions)

        # 创建压缩消息
        compaction_msg = Message(
            role=MessageRole.COMPACTION,
            content=summary,
            metadata={"compacted_count": len(to_summarize)}
        )

        # 替换消息
        session.messages = [compaction_msg] + to_keep
        session.compaction_count += 1
        session.last_compaction_at = datetime.now()

        return summary
