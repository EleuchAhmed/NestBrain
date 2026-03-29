import sys, asyncio, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notebooklm_auth import get_auth_tokens
from notebooklm.client import NotebookLMClient

async def main():
    tokens = await get_auth_tokens()
    async with NotebookLMClient(tokens) as client:
        notebook = await client.notebooks.create(title="TEST-NB")
        print(f"Attributes: {dir(notebook)}")
        print(f"Content: {notebook.__dict__}")
        await client.notebooks.delete(notebook_id=notebook.id if hasattr(notebook, 'id') else notebook.notebook_id)

if __name__ == "__main__":
    asyncio.run(main())
