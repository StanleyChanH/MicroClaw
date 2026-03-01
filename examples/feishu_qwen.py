"""
飞书机器人示例 - WebSocket 长连接模式

优势:
- 无需公网 IP，本地即可调试
- 无需内网穿透工具 (ngrok 等)
- 开发周期从 1 周缩短到 5 分钟

环境变量 (配置在 .env 文件):
   OPENAI_API_KEY      - API Key (通用于所有 OpenAI 兼容 API)
   OPENAI_BASE_URL     - API 地址 (如阿里云通义: https://dashscope.aliyuncs.com/compatible-mode/v1)
   FEISHU_APP_ID       - 飞书应用 ID
   FEISHU_APP_SECRET   - 飞书应用密钥
"""

import os

from microclaw import Gateway, GatewayConfig
from microclaw.channels import FeishuChannel, FeishuConfig

# 加载 .env 文件
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def main():
    # 检查必需的环境变量
    required = ["OPENAI_API_KEY", "FEISHU_APP_ID", "FEISHU_APP_SECRET"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"[错误] 缺少环境变量: {missing}")
        print("请创建 .env 文件并配置:")
        print("  OPENAI_API_KEY=xxx")
        print("  OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1")
        print("  FEISHU_APP_ID=xxx")
        print("  FEISHU_APP_SECRET=xxx")
        return

    # Gateway 配置
    gateway = Gateway(
        GatewayConfig(
            storage_dir="~/.microclaw",
            default_model=os.environ.get("MICROCLAW_MODEL", "qwen-plus"),
            default_provider=os.environ.get("MICROCLAW_PROVIDER", "openai_compatible"),
            base_url=os.environ.get("OPENAI_BASE_URL"),
            api_key=os.environ["OPENAI_API_KEY"],
        )
    )

    # 飞书通道 - 默认使用 WebSocket 长连接模式 (无需公网 IP)
    feishu = FeishuChannel(
        config=FeishuConfig(
            app_id=os.environ["FEISHU_APP_ID"],
            app_secret=os.environ["FEISHU_APP_SECRET"],
            use_websocket=True,  # 使用 WebSocket 长连接 (默认值)
        ),
        port=8081,  # WebSocket 模式下此参数被忽略
    )
    gateway.add_channel(feishu)

    print("""
========================================
  MicroClaw 飞书机器人
========================================

模式: WebSocket 长连接 (无需公网 IP)

飞书开放平台配置:
1. 事件订阅方式: 选择 "使用长连接接收事件"
2. 订阅事件: im.message.receive_v1
3. 权限: im:message, im:message:send_as_bot

本地即可调试，无需 ngrok！

按 Ctrl+C 停止
""")

    gateway.run()


if __name__ == "__main__":
    main()
