import sys, asyncio, os, inspect
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notebooklm_auth import get_auth_tokens
from notebooklm.client import NotebookLMClient

async def main():
    tokens = await get_auth_tokens()
    async with NotebookLMClient(tokens) as client:
        print(f"add_file signature: {inspect.signature(client.sources.add_file)}")

if __name__ == "__main__":
    asyncio.run(main())
