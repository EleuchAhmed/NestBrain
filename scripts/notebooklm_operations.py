import sys
import json
import asyncio
import os
import time

# Ensure the root directory is in the python path to import notebooklm_auth
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notebooklm_auth import get_client

async def main():
    try:
        input_data = sys.stdin.read()
        if not input_data:
            print(json.dumps({"error": "Missing input on stdin"}))
            sys.exit(1)
            
        payload = json.loads(input_data)
        action = payload.get("action")
        args = payload.get("args", {})
    except Exception as e:
        print(json.dumps({"error": f"Invalid JSON payload on stdin: {e}"}))
        sys.exit(1)
        
    try:
        client = await get_client()
        result = {}

        if action == "createNotebook":
            notebook = await client.notebooks.create(title=args["title"])
            result = {"notebookId": notebook.id}
            
        elif action == "ingestUrl":
            source = await client.sources.add_url(
                notebook_id=args["notebookId"],
                url=args["url"],
                wait=True
            )
            result = {"success": True, "sourceId": source.id}
            
        elif action == "ingestText":
            source = await client.sources.add_text(
                notebook_id=args["notebookId"],
                title=args["title"],
                content=args["content"],
                wait=True
            )
            result = {"success": True, "sourceId": source.id}
            
        elif action == "interrogate":
            notebook_id = args["notebookId"]
            queries = args["queries"]
            responses = []
            
            for query in queries:
                try:
                    res = await client.chat.ask(notebook_id=notebook_id, question=query)
                    responses.append(f"### Query: {query}\n\n{res.answer}")
                except Exception as e:
                    responses.append(f"### Query: {query}\n\n⚠️ Error: {str(e)}")
                # Small delay to respect rate limits
                await asyncio.sleep(2)
                
            result = {"responses": responses}
            
        elif action == "generateMedia":
            notebook_id = args["notebookId"]
            audio_url = None
            video_url = None
            
            # Request audio
            try:
                await client.artifacts.generate_audio_overview(notebook_id)
            except Exception as e:
                result["audioError"] = str(e)
                
            # Request video
            # NOTE: notebooklm-py video generation might not be natively exposed exactly like this, 
            # but usually it's `generate_video(notebook_id)` or similar. 
            # If video generation isn't directly exposed or reliably working, we'll try it and handle failure gracefully.
            try:
                if hasattr(client.artifacts, 'generate_video'):
                    await client.artifacts.generate_video(notebook_id)
            except Exception as e:
                result["videoError"] = str(e)

            # Wait for completion (poll studio list up to 5 mins)
            for _ in range(60):
                await asyncio.sleep(5)
                artifacts = await client.artifacts.list(notebook_id)
                audio_finished = video_finished = True
                
                for a in artifacts:
                    if a.type.lower() == "audio_overview" and a.state == "COMPLETED" and not audio_url:
                        audio_url = a.url
                    if a.type.lower() == "video" and a.state == "COMPLETED" and not video_url:
                        video_url = a.url
                        
                # Wait until both audio and video have appeared if requested
                # If either failed to be requested, skip waiting for it
                if ("audioError" not in result and not audio_url) or ("videoError" not in result and hasattr(client.artifacts, 'generate_video') and not video_url):
                    continue
                break

            result = {"audioUrl": audio_url, "videoUrl": video_url}
            
        else:
            result = {"error": f"Unknown action: {action}"}
            
        print(json.dumps(result))
        
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
