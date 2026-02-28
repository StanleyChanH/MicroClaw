"""
Custom Tools Example

Shows how to create and register custom tools for your agent.
"""

import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from microclaw import Gateway, GatewayConfig, tool
from microclaw.gateway import CLIChannel, IncomingMessage


# === Custom Tools ===

@tool(description="Get the current date and time")
def get_datetime() -> str:
    """Returns the current date and time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool(description="Calculate a mathematical expression")
def calculate(expression: str) -> str:
    """
    Safely evaluate a mathematical expression.
    Example: calculate("2 + 2 * 3")
    """
    try:
        # Only allow safe math operations
        allowed = set("0123456789+-*/.() ")
        if not all(c in allowed for c in expression):
            return "Error: Invalid characters in expression"
        
        result = eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"Error: {e}"


@tool(description="Store a note in memory")
def remember(key: str, value: str) -> str:
    """Store a key-value pair for later retrieval."""
    # In a real app, this would use the MemoryStore
    _memory[key] = value
    return f"Remembered: {key} = {value}"


@tool(description="Recall a note from memory")
def recall(key: str) -> str:
    """Retrieve a previously stored value."""
    if key in _memory:
        return f"{key} = {_memory[key]}"
    return f"No memory found for: {key}"


# Simple in-memory storage for this example
_memory = {}


async def main():
    # Create gateway
    config = GatewayConfig(
        storage_dir=".microclaw-example",
        default_model="gpt-4o-mini",
        default_provider="openai",
        system_prompt="""You are a helpful assistant with access to tools.

You can:
- Get the current date/time
- Do math calculations
- Remember things for the user
- Recall previously remembered things

Be concise and helpful."""
    )
    
    gateway = Gateway(config)
    
    # Register custom tools
    gateway.add_tool(get_datetime)
    gateway.add_tool(calculate)
    gateway.add_tool(remember)
    gateway.add_tool(recall)
    
    # Add CLI channel
    gateway.add_channel(CLIChannel())
    
    # Add event handlers for visibility
    def on_tool_call(event, name, data):
        if event == "start":
            print(f"\n  🔧 Calling: {name}")
            print(f"     Args: {data}")
    
    gateway.on("tool_call", on_tool_call)
    
    print("\nTry asking:")
    print("  - What time is it?")
    print("  - Calculate 15% of 250")
    print("  - Remember that my favorite color is blue")
    print("  - What's my favorite color?")
    print()
    
    # Run
    await gateway.start()


if __name__ == "__main__":
    asyncio.run(main())
