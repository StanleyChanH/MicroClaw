"""
飞书机器人 - 使用阿里云通义千问

环境变量 (配置在 .env 文件):
   ALIYUN_API_KEY      - 阿里云 API Key
   FEISHU_APP_ID       - 飞书应用 ID
   FEISHU_APP_SECRET   - 飞书应用密钥
"""

import os
from microclaw import Gateway, GatewayConfig
from microclaw.channels import FeishuChannel, FeishuConfig

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def main():
    # Check required env vars
    required = ["ALIYUN_API_KEY", "FEISHU_APP_ID", "FEISHU_APP_SECRET"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"[ERROR] Missing environment variables: {missing}")
        print("Please create .env file with:")
        print("  ALIYUN_API_KEY=xxx")
        print("  FEISHU_APP_ID=xxx")
        print("  FEISHU_APP_SECRET=xxx")
        return

    # Gateway with Aliyun Qwen3.5-Plus
    gateway = Gateway(GatewayConfig(
        storage_dir="~/.microclaw",
        default_model="qwen3.5-plus",
        default_provider="openai_compatible",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key=os.environ["ALIYUN_API_KEY"],
    ))

    # Feishu channel
    feishu = FeishuChannel(
        config=FeishuConfig(
            app_id=os.environ["FEISHU_APP_ID"],
            app_secret=os.environ["FEISHU_APP_SECRET"],
        ),
        port=8081
    )
    gateway.add_channel(feishu)

    print("""
========================================
  MicroClaw Feishu Bot (Qwen3.5-Plus)
========================================

Webhook: http://0.0.0.0:8081/feishu/webhook

Feishu Open Platform Setup:
1. Event subscription URL: http://your-server:8081/feishu/webhook
2. Subscribe event: im.message.receive_v1
3. Permissions: im:message, im:message:send_as_bot

For local testing, use ngrok:
  ngrok http 8081

Press Ctrl+C to stop
""")

    gateway.run()


if __name__ == "__main__":
    main()
