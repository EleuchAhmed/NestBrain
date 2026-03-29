import asyncio
import json
import os
import sys
from pathlib import Path
from notebooklm.auth import AuthTokens
from notebooklm.client import NotebookLMClient

async def main():
    auth_file = Path(os.path.expanduser("~/.notebooklm-mcp/auth.json"))
    if not auth_file.exists():
        print("ERROR: Auth file not found at", auth_file)
        print("Please authenticate using the browser-auth tool first.")
        # But we will try to print out the NotebookLM methods anyway
        return
        
    try:
        data = json.loads(auth_file.read_text())
        
        auth = AuthTokens(
            cookies=data.get('cookies', {}),
            csrf_token=data.get('csrf_token', ''),
            session_id=data.get('session_id', '')
        )
        
        print("Authenticating with notebooklm-py...")
        async with NotebookLMClient(auth) as client:
            print("Successfully authenticated!")
            
            # Create a test notebook
            print("Creating test notebook...")
            notebook = await client.notebooks.create(title="Pipeline Test Notebook")
            print(f"Created notebook: {notebook.title} (ID: {notebook.id})")
            
            # Add one URL source
            print("Adding URL source...")
            source = await client.sources.add_url(
                notebook_id=notebook.id,
                url="https://en.wikipedia.org/wiki/Artificial_intelligence",
                wait=True
            )
            print(f"Added source: {source.title}")
            
            # Send one query
            print("Sending query...")
            response = await client.chat.ask(
                notebook_id=notebook.id,
                question="What is the summary of this article?"
            )
            print("Got response:", response.answer)
            
    except Exception as e:
        print("ERROR:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
