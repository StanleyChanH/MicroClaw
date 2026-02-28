"""
Webhook Server Example

Run MicroClaw as an HTTP API that can receive messages via POST requests.
Perfect for integrating with messaging platforms, Slack bots, etc.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from microclaw import Gateway, GatewayConfig
from microclaw.gateway import WebhookChannel


async def main():
    config = GatewayConfig(
        storage_dir=".microclaw-webhook",
        default_model="gpt-4o-mini",
        default_provider="openai",
        system_prompt="You are a helpful API assistant. Keep responses concise."
    )
    
    gateway = Gateway(config)
    
    # Add webhook channel
    gateway.add_channel(WebhookChannel(
        host="0.0.0.0",
        port=8080
    ))
    
    # Log events
    def on_message(msg):
        print(f"📨 Message from {msg.sender}: {msg.content[:50]}...")
    
    def on_response(msg, response):
        print(f"📤 Response: {response[:50]}...")
    
    gateway.on("message_received", on_message)
    gateway.on("response_ready", on_response)
    
    print("""
╔═══════════════════════════════════════════════════════╗
║           🦞 MicroClaw Webhook Server                  ║
╚═══════════════════════════════════════════════════════╝

Endpoints:
  POST /message  - Send a message to the agent
  GET  /health   - Health check

Example request:
  curl -X POST http://localhost:8080/message \\
    -H "Content-Type: application/json" \\
    -d '{"sender": "user123", "message": "Hello!"}'

Example response:
  {"response": "Hello! How can I help you today?"}

Press Ctrl+C to stop.
""")
    
    await gateway.start()


if __name__ == "__main__":
    asyncio.run(main())
