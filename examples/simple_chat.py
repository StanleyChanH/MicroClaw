"""
Simple Chat Example

The most basic usage of MicroClaw - a CLI chat with an AI agent.
"""

import asyncio
import os

# Ensure we can import microclaw
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from microclaw import Gateway, GatewayConfig
from microclaw.gateway import CLIChannel


async def main():
    # Create gateway with default settings
    config = GatewayConfig(
        storage_dir=".microclaw-example",
        default_model="gpt-4o-mini",
        default_provider="openai"
    )
    
    gateway = Gateway(config)
    gateway.add_channel(CLIChannel())
    
    # Start the gateway (runs until Ctrl+C)
    await gateway.start()


if __name__ == "__main__":
    asyncio.run(main())
