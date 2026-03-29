import sys, json, asyncio, os, re
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notebooklm_auth import get_auth_tokens
from notebooklm.client import NotebookLMClient

# Sources and Output Paths
PDFS = [
    {
        "title": "OpenAI-Agents-Guide",
        "path": r"C:\Users\Mega Pc\Desktop\research-pipeline\staging\20260319T033826Z_a-practical-guide-to-building-agents.pdf",
        "output": r"C:\Users\Mega Pc\Desktop\tech knowledge\20_Concepts\AI-Agents\openai-agents-guide.md"
    },
    {
        "title": "Predibase-FineTuning",
        "path": r"C:\Users\Mega Pc\Desktop\research-pipeline\staging\Predibase_Fine-Tuning_LLMs_ebook_.pdf",
        "output": r"C:\Users\Mega Pc\Desktop\tech knowledge\20_Concepts\AI-Data\predibase-finetuning.md"
    }
]

SYNTHESIS_QUERY = """
Create a comprehensive research note in Markdown format based on this source.
Focus on:
1. Executive Summary
2. Core Architecture/Foundational Principles
3. Technical Implementation Details
4. Practical Advice & Best Practices
5. Comparison/Strategic Significance

Maintain citations [1][2] and use Callouts for important warnings.
"""

async def process_pdf(client, pdf_info):
    print(f"--- Processing {pdf_info['title']} ---")
    
    print(f"Adding notebook for {pdf_info['title']}...")
    notebook = await client.notebooks.create(title=pdf_info['title'])
    nb_id = notebook.id
    
    print(f"Uploading PDF: {pdf_info['path']}...")
    # add_file signature: (notebook_id, file_path, mime_type=None, wait=False, wait_timeout=120.0)
    await client.sources.add_file(notebook_id=nb_id, file_path=pdf_info['path'], wait=True)
    
    print(f"Synthesizing note for {pdf_info['title']}...")
    res = await client.chat.ask(notebook_id=nb_id, question=SYNTHESIS_QUERY)
    answer = res.answer if hasattr(res, 'answer') else str(res)
    
    # Ensure directory
    os.makedirs(os.path.dirname(pdf_info['output']), exist_ok=True)
    with open(pdf_info['output'], 'w', encoding='utf-8') as f:
        f.write(answer)
    print(f"Successfully wrote note to {pdf_info['output']}")
    
    return nb_id

async def main():
    tokens = await get_auth_tokens()
    async with NotebookLMClient(tokens) as client:
        for pdf in PDFS:
            if os.path.exists(pdf['path']):
                try:
                    await process_pdf(client, pdf)
                except Exception as e:
                    print(f"Error processing {pdf['title']}: {e}")
            else:
                print(f"PDF not found: {pdf['path']}")

if __name__ == "__main__":
    asyncio.run(main())
