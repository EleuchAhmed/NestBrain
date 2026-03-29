"""
Direct NotebookLM interrogation and video generation script.
Uses the notebooklm-py library to query the notebook and generate video.
"""
import sys
import json
import asyncio
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notebooklm_auth import get_auth_tokens
from notebooklm.client import NotebookLMClient

NOTEBOOK_ID = "49816000-f396-4941-a088-b5a152537d82"

QUERIES = [
    "Extract the primary thesis, the 3-5 foundational arguments, and the ultimate conclusion about LLM fine-tuning from these sources. Include exact impactful quotes if any.",
    "Detail the specific methodology, techniques (like LoRA, QLoRA, RLHF, PEFT), data preparation steps, and frameworks discussed for fine-tuning LLMs.",
    "Identify all domain-specific terminology and technical jargon related to LLM fine-tuning. Define each term based on the source context.",
    "What are the key trade-offs, challenges, and nuances in LLM fine-tuning? What are common pitfalls and how to avoid them?",
    "Summarize the real-world applications and use cases for LLM fine-tuning discussed in the sources. What industries or scenarios benefit most?"
]

async def main():
    print("Authenticating with NotebookLM...", file=sys.stderr)
    tokens = await get_auth_tokens()
    
    async with NotebookLMClient(tokens) as client:
        responses = []
        
        for i, query in enumerate(QUERIES):
            print(f"Running query {i+1}/{len(QUERIES)}...", file=sys.stderr)
            try:
                res = await client.chat.ask(notebook_id=NOTEBOOK_ID, question=query)
                answer = res.answer if hasattr(res, 'answer') else str(res)
                responses.append({"query": query, "answer": answer})
                print(f"  Got response ({len(answer)} chars)", file=sys.stderr)
            except Exception as e:
                print(f"  ERROR: {e}", file=sys.stderr)
                responses.append({"query": query, "answer": f"ERROR: {str(e)}"})
            await asyncio.sleep(3)
        
        # Generate video
        print("\nRequesting video generation...", file=sys.stderr)
        video_url = None
        try:
            if hasattr(client.artifacts, 'generate_video'):
                await client.artifacts.generate_video(NOTEBOOK_ID)
                print("Video generation started, polling...", file=sys.stderr)
            elif hasattr(client.artifacts, 'generate'):
                await client.artifacts.generate(NOTEBOOK_ID, artifact_type='video')
                print("Video generation started via generic generate(), polling...", file=sys.stderr)
            else:
                methods = [m for m in dir(client.artifacts) if not m.startswith('_')]
                print(f"Available artifact methods: {methods}", file=sys.stderr)
                print("No video generation method found, trying audio...", file=sys.stderr)
                try:
                    await client.artifacts.generate_audio_overview(NOTEBOOK_ID)
                    print("Audio overview generation started", file=sys.stderr)
                except Exception as ae:
                    print(f"Audio generation also failed: {ae}", file=sys.stderr)
        except Exception as e:
            print(f"Video generation error: {e}", file=sys.stderr)
        
        # Poll for artifacts
        print("Polling for completed artifacts...", file=sys.stderr)
        audio_url = None
        for attempt in range(36):  # ~3 minutes
            await asyncio.sleep(5)
            try:
                artifacts = await client.artifacts.list(NOTEBOOK_ID)
                for a in artifacts:
                    kind = getattr(a, 'kind', '').lower() if hasattr(a, 'kind') else ''
                    state = getattr(a, 'state', '').lower() if hasattr(a, 'state') else ''
                    url = getattr(a, 'url', None)
                    print(f"  Artifact: kind={kind}, state={state}, url={url}", file=sys.stderr)
                    
                    if 'video' in kind and state == 'completed' and url:
                        video_url = url
                    if 'audio' in kind and state == 'completed' and url:
                        audio_url = url
                
                if video_url or audio_url:
                    break
                    
                if attempt % 6 == 0 and attempt > 0:
                    print(f"  Still waiting... ({attempt * 5}s elapsed)", file=sys.stderr)
            except Exception as e:
                print(f"  Poll error: {e}", file=sys.stderr)
        
        result = {
            "notebookId": NOTEBOOK_ID,
            "responses": responses,
            "videoUrl": video_url,
            "audioUrl": audio_url
        }
        
        # Write results
        output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                    "staging", "llm-finetuning-interrogation.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\nResults written to {output_path}", file=sys.stderr)
        print(json.dumps({"success": True, "outputPath": output_path, "videoUrl": video_url, "audioUrl": audio_url}))

if __name__ == "__main__":
    asyncio.run(main())
