"""
飞书机器人示例

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
        print("  OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1  # 阿里云通义")
        print("  FEISHU_APP_ID=xxx")
        print("  FEISHU_APP_SECRET=xxx")
        return

    # Gateway 配置 (使用阿里云通义千问)
    gateway = Gateway(GatewayConfig(
        storage_dir="~/.microclaw",
        default_model=os.environ.get("MICROCLAW_MODEL", "qwen3.5-plus"),
        default_provider=os.environ.get("MICROCLAW_PROVIDER", "openai_compatible"),
        base_url=os.environ.get("OPENAI_BASE_URL"),
        api_key=os.environ["OPENAI_API_KEY"],
    ))

    # 飞书通道
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
  MicroClaw 飞书机器人
========================================

Webhook 地址: http://0.0.0.0:8081/feishu/webhook

飞书开放平台配置:
1. 事件订阅地址: http://your-server:8081/feishu/webhook
2. 订阅事件: im.message.receive_v1
3. 权限: im:message, im:message:send_as_bot

本地测试可使用 ngrok:
  ngrok http 8081

按 Ctrl+C 停止
""")

    gateway.run()


if __name__ == "__main__":
    main()
