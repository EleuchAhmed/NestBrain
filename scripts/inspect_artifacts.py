import asyncio
import os
import sys
from notebooklm_auth import get_auth_tokens
from notebooklm.client import NotebookLMClient

async def inspect():
    tokens = await get_auth_tokens()
    async with NotebookLMClient(tokens) as client:
        print(f"ArtifactsAPI methods: {dir(client.artifacts)}")

if __name__ == "__main__":
    # Ensure current directory is in path
    sys.path.append(os.getcwd())
    asyncio.run(inspect())
