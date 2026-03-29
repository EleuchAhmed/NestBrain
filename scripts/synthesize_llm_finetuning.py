import sys, json, asyncio, os, re
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notebooklm_auth import get_auth_tokens
from notebooklm.client import NotebookLMClient

NOTEBOOK_ID = "49816000-f396-4941-a088-b5a152537d82"
VAULT_NOTE_PATH = r"C:\Users\Mega Pc\Desktop\tech knowledge\20_Concepts\AI-Data\llm-finetuning.md"

SYNTHESIS_QUERY = """
Create a comprehensive, structured, and encyclopedic research note on **LLM Fine-Tuning** in Markdown format.

Structure the note into these 6 sections:
1. **Executive Summary**: Core value proposition and the essential transition from general models to specialized tools.
2. **Core Concepts & Terminology**: A deep glossary (e.g., PEFT, LoRA, QLoRA, SFT, Instruction Tuning, Catastrophic Forgetting).
3. **Technical Deep Dive**: Detail the methodologies, data preparation steps (prompt-response pairs), and optimization techniques (e.g., quantization, hyperparameters).
4. **Strategic Evaluation & Trade-offs**: Compare Fine-tuning vs. Prompting vs. RAG. Discuss risks like Overfitting and Catastrophic Forgetting.
5. **Real-World Applications**: Highlight industries (Healthcare, Legal, Finance) and specific high-impact use cases (stability for technical integration).
6. **Actionable Checklist & Knowledge Graph**: Key takeaways and "See Also" links.

IMPORTANT: 
- Use ONLY the sources in the notebook.
- Include citation numbers [1][2] for grounding.
- Use Callouts for critical warnings.
- Avoid all hallucinations.

Generate the full content of the note.
"""

async def main():
    print("Authenticating with NotebookLM...", file=sys.stderr)
    tokens = await get_auth_tokens()
    async with NotebookLMClient(tokens) as client:
        print("Synthesizing final note via NotebookLM...", file=sys.stderr)
        try:
            res = await client.chat.ask(notebook_id=NOTEBOOK_ID, question=SYNTHESIS_QUERY)
            answer = res.answer if hasattr(res, 'answer') else str(res)
            
            # Ensure the directory exists
            os.makedirs(os.path.dirname(VAULT_NOTE_PATH), exist_ok=True)
            
            # Save to vault
            with open(VAULT_NOTE_PATH, 'w', encoding='utf-8') as f:
                f.write(answer)
            print(f"Successfully wrote note to {VAULT_NOTE_PATH}", file=sys.stderr)
            print("DONE")
        except Exception as e:
            print(f"Error during synthesis: {e}", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(main())
