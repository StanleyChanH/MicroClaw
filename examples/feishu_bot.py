"""
飞书机器人示例

使用步骤:
1. 在飞书开放平台创建企业自建应用
2. 获取 App ID 和 App Secret
3. 配置事件订阅:
   - 地址: http://你的服务器:8081/feishu/webhook
   - 事件: im.message.receive_v1
4. 发布应用，添加到群聊或启用私聊
5. 运行此脚本

环境变量:
   export FEISHU_APP_ID="cli_xxxxx"
   export FEISHU_APP_SECRET="your_secret"
   export OPENAI_API_KEY="sk-xxx"
"""

import os
import asyncio

from microclaw import Gateway, GatewayConfig
from microclaw.channels import FeishuChannel, FeishuConfig


def main():
    # 创建 Gateway
    gateway = Gateway(GatewayConfig(
        storage_dir="~/.microclaw",
        default_model="gpt-4o-mini",
        default_provider="openai",
    ))

    # 添加飞书通道
    feishu = FeishuChannel(
        config=FeishuConfig(
            app_id=os.environ.get("FEISHU_APP_ID", ""),
            app_secret=os.environ.get("FEISHU_APP_SECRET", ""),
        ),
        port=8081
    )
    gateway.add_channel(feishu)

    # 事件处理
    def on_feishu_message(event, name, data):
        if event == "start":
            print(f"🔧 收到消息，处理中...")

    gateway.on("tool_call", on_feishu_message)

    print("""
╔═══════════════════════════════════════════╗
║       MicroClaw 飞书机器人已启动           ║
╚═══════════════════════════════════════════╝

Webhook 地址: http://0.0.0.0:8081/feishu/webhook

请在飞书开放平台配置事件订阅，订阅 im.message.receive_v1 事件
""")

    # 启动
    gateway.run()


if __name__ == "__main__":
    main()
