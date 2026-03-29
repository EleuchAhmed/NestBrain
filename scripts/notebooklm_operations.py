import sys
import json
import asyncio
import os
import time
from contextlib import redirect_stdout
from urllib.parse import urlparse

# Ensure the root directory is in the python path to import notebooklm_auth
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notebooklm_auth import get_auth_tokens
from notebooklm.client import NotebookLMClient
from notebooklm.rpc import AudioFormat, AudioLength, VideoFormat, VideoStyle

async def run_action():
    try:
        input_data = sys.stdin.read()
        if not input_data:
            return {"error": "Missing input on stdin"}
            
        payload = json.loads(input_data)
        action = payload.get("action")
        args = payload.get("args", {})
    except Exception as e:
        return {"error": f"Invalid JSON payload on stdin: {e}"}
        
    try:
        tokens = await get_auth_tokens()
        async with NotebookLMClient(tokens) as client:
            notebook_id = args.get("notebookId")
            
            if action == "createNotebook":
                notebook = await client.notebooks.create(title=args["title"])
                return {"notebookId": notebook.id}
                
            elif action == "ingestUrl":
                source = await client.sources.add_url(
                    notebook_id=notebook_id,
                    url=args["url"],
                    wait=True
                )
                return {"success": True, "sourceId": source.id}
                
            elif action == "ingestText":
                source = await client.sources.add_text(
                    notebook_id=notebook_id,
                    title=args["title"],
                    content=args["content"],
                    wait=True
                )
                return {"success": True, "sourceId": source.id}

            elif action == "ingestFile":
                source = await client.sources.add_file(
                    notebook_id=notebook_id,
                    file_path=args["path"],
                    wait=True
                )
                return {"success": True, "sourceId": source.id}
                
            elif action == "interrogate":
                queries = args["queries"]
                responses = []
                for query in queries:
                    try:
                        res = await client.chat.ask(notebook_id=notebook_id, question=query)
                        responses.append(f"### Query: {query}\n\n{res.answer}")
                    except Exception as e:
                        responses.append(f"### Query: {query}\n\n⚠️ Error: {str(e)}")
                    await asyncio.sleep(1)
                return {"responses": responses}

            elif action == "synthesize":
                query = args.get("query", "Create a comprehensive grounded research note on this topic.")
                res = await client.chat.ask(notebook_id=notebook_id, question=query)
                return {"answer": res.answer}
                
            elif action == "generateMedia":
                media_type = args.get("type", "audio")
                instructions = args.get("instructions")
                max_retries = 3
                
                for attempt in range(max_retries):
                    try:
                        if media_type == "audio":
                            status = await client.artifacts.generate_audio(
                                notebook_id,
                                instructions=instructions,
                                audio_format=AudioFormat.DEEP_DIVE,
                                audio_length=AudioLength.DEFAULT
                            )
                        else:
                            status = await client.artifacts.generate_video(
                                notebook_id,
                                instructions=instructions,
                                video_format=VideoFormat.EXPLAINER,
                                video_style=VideoStyle.AUTO_SELECT
                            )
                        break # Success
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise e
                        print(f"DEBUG: RPC failed, retrying in 5s (attempt {attempt+1}/{max_retries})...", file=sys.stderr)
                        await asyncio.sleep(5)
                
                # Poll for completion (up to 10 minutes for Video)
                timeout = 600.0 if media_type == "video" else 300.0
                result = await client.artifacts.wait_for_completion(
                    notebook_id, 
                    status.task_id,
                    timeout=timeout
                )
                
                if result.is_complete:
                    artifact = await client.artifacts.get(notebook_id, status.task_id)
                    return {
                        "status": "success",
                        "artifactId": status.task_id,
                        "url": getattr(artifact, "url", None)
                    }
                else:
                    return {"status": "failed", "error": result.error or "Generation timed out"}

            elif action == "downloadMedia":
                media_type = args.get("type", "audio")
                artifact_id = args.get("artifactId")
                output_path = args.get("outputPath")
                
                if not output_path:
                    return {"error": "outputPath is required"}

                if media_type == "audio":
                    saved_path = await client.artifacts.download_audio(notebook_id, output_path, artifact_id=artifact_id)
                else:
                    saved_path = await client.artifacts.download_video(notebook_id, output_path, artifact_id=artifact_id)
                
                return {"status": "success", "path": saved_path}
                
            else:
                return {"error": f"Unknown action: {action}"}
            
    except Exception as e:
        return {"error": str(e)}

async def main():
    with redirect_stdout(sys.stderr):
        final_result = await run_action()
    
    sys.stdout.write(json.dumps(final_result))
    sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(main())
