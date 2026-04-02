import logging
from typing import List, Dict
from ..nvidia_client import nvidia_client

logger = logging.getLogger(__name__)

class MasterSynthesizer:
    """Layer 1: The Author (deepseek-v3.2)
    Synthesizes all Q&A data into a structured Markdown "Master Note" 
    with headers and Obsidian formatting.
    """
    
    MODEL = "deepseek-ai/deepseek-r1"

    def __init__(self):
        self.client = nvidia_client
        self.used_fallback = False
        self.last_error = ""

    def synthesize(self, subject: str, qa_history: List[Dict[str, str]]) -> str:
        """
        Takes the complete Q&A history and merges it into a highly readable,
        synthesized Markdown document.
        """
        logger.info(f"Synthesizing Master Note for subject: {subject} from {len(qa_history)} Q&A pairs.")

        system_prompt = (
            "You are an expert Technical Writer and Author creating a definitive master note for a personal Obsidian vault.\n"
            "You will be given a subject and a rough history of Q&A research passes related to that subject.\n"
            "Your task is to synthesize this unstructured Q&A data into a highly structured, flowing, cohesive Markdown document.\n\n"
            "Format REQUIREMENTS:\n"
            "- Use `# [Title]` for the top-level main header.\n"
            "- Use `## ` and `### ` for logical sub-sections.\n"
            "- Incorporate bullet points, bold text for key terms, and markdown tables if comparing concepts.\n"
            "- Do NOT write just a list of Q&As. You must integrate the knowledge together naturally.\n"
            "- Feel free to add `[[]]` around technical terms naturally within the text so Obsidian recognizes them as links.\n"
            "Produce ONLY the final localized markdown note text."
        )

        # Build context from Q&A history
        formatted_qa = "\n\n".join(
            f"Q: {qa['question']}\nA: {qa['answer']}"
            for qa in qa_history
        )

        user_content = (
            f"Subject: {subject}\n\n"
            f"---- RAW RESEARCH Q&A HISTORY ----\n"
            f"{formatted_qa}\n"
            f"----------------------------------\n\n"
            "Please generate the Master Note."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        try:
            response_text = self.client.generate_chat_completion(
                model=self.MODEL,
                messages=messages,
                temperature=0.4
            )
            self.used_fallback = False
            self.last_error = ""
            
            return response_text.strip()
            
        except Exception as e:
            logger.error(f"Failed to synthesize Master Note: {e}")
            self.used_fallback = True
            self.last_error = str(e)
            condensed = qa_history[:8]
            qa_blocks = "\n\n".join(
                f"### Q: {entry.get('question', '').strip()}\n{entry.get('answer', '').strip()}"
                for entry in condensed
                if entry.get("question") and entry.get("answer")
            )
            if not qa_blocks:
                qa_blocks = "No usable Q&A content was generated."

            return (
                f"# {subject}\n\n"
                "## Executive Summary\n"
                "Model synthesis failed, so this note was built from raw research responses.\n\n"
                "## Core Findings\n"
                "- Review the source-backed Q&A appendix below.\n"
                "- Re-run synthesis after verifying NVIDIA API configuration.\n\n"
                "## Open Questions\n"
                "- Which areas need deeper source interrogation?\n"
                "- Which claims need cross-source validation?\n\n"
                "## Q&A Appendix\n"
                f"{qa_blocks}\n"
            )
