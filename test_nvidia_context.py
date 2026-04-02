"""Compare direct NVIDIA call vs pipeline context call"""
import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
load_dotenv()

from nestbrain.core.nvidia_client import NvidiaNIMClient

async def test_direct():
    """Test calling NVIDIA directly"""
    print("TEST 1: Direct synchronous call in async context")
    client = NvidiaNIMClient()
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say hello"}
    ]
    
    print(f"DEBUG: About to call generate_chat_completion directly")
    try:
        response = client.generate_chat_completion(
            model="deepseek-ai/deepseek-v3.2",
            messages=messages,
            temperature=0.3
        )
        print(f"SUCCESS: Got response of {len(response)} chars: {response[:100]}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")

async def test_via_executor():
    """Test calling NVIDIA via executor"""
    print("\nTEST 2: Via run_in_executor")
    client = NvidiaNIMClient()
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say hello"}
    ]
    
    print(f"DEBUG: About to call via executor")
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.generate_chat_completion(
                model="deepseek-ai/deepseek-v3.2",
                messages=messages,
                temperature=0.3
            )
        )
        print(f"SUCCESS: Got response of {len(response)} chars: {response[:100]}")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")

async def main():
    print("Testing NVIDIA API calls in different contexts")
    await test_direct()
    await test_via_executor()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted!")
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
