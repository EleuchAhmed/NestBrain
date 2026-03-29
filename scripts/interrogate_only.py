"""Query NotebookLM and save results (no video polling)."""
import sys, json, asyncio, os
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
    print("Authenticating...", file=sys.stderr)
    tokens = await get_auth_tokens()
    async with NotebookLMClient(tokens) as client:
        responses = []
        for i, query in enumerate(QUERIES):
            print(f"Query {i+1}/{len(QUERIES)}...", file=sys.stderr)
            try:
                res = await client.chat.ask(notebook_id=NOTEBOOK_ID, question=query)
                answer = res.answer if hasattr(res, 'answer') else str(res)
                responses.append({"query": query, "answer": answer})
                print(f"  OK ({len(answer)} chars)", file=sys.stderr)
            except Exception as e:
                print(f"  ERROR: {e}", file=sys.stderr)
                responses.append({"query": query, "answer": f"ERROR: {str(e)}"})
            await asyncio.sleep(3)
        
        output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "staging", "llm-finetuning-interrogation.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"notebookId": NOTEBOOK_ID, "responses": responses}, f, indent=2, ensure_ascii=False)
        print(f"Saved to {output_path}", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(main())
