import json
import logging
from typing import List, Dict, Any
from ..nvidia_client import nvidia_client

logger = logging.getLogger(__name__)

class QuestionPlanner:
    """Layer 1: The Architect (deepseek-v3.2)
    Generates an exhaustive research taxonomy for the input subject.
    """
    
    MODEL = "deepseek-v3.2"

    def __init__(self):
        # Fallback to a valid DeepSeek model identifier for NVIDIA NIM if v3.2 isn't strictly named this
        # e.g. deepseek-ai/deepseek-coder-33b-instruct, etc.
        # Assuming deepseek-v3.2 as per user mapping
        self.client = nvidia_client

    def generate_taxonomy(self, subject: str, context_summary: str = "") -> List[str]:
        """
        Takes a subject and generates a list of essential questions covering:
        what, why, how, when, tradeoffs, limitations, dependencies, history.
        """
        logger.info(f"Generating research taxonomy for subject: {subject}")
        
        system_prompt = (
            "You are an expert Research Architect. Your job is to take a subject and break it down into an "
            "exhaustive research taxonomy. You must formulate specific, targeted questions covering:\n"
            "- Definitions (What is it?)\n"
            "- Motivations (Why does it exist?)\n"
            "- Implementations/Mechanisms (How does it work?)\n"
            "- Context (When should it be used? History?)\n"
            "- Comparisons (Tradeoffs, alternatives)\n"
            "- Limitations\n"
            "\n"
            "Return ONLY a JSON array of strings, where each string is a distinct research question. No markdown blocks."
        )

        user_content = f"Subject: {subject}\n"
        if context_summary:
            user_content += f"Additional Context: {context_summary}\n"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        try:
            # We enforce a JSON array response using the prompt
            response_text = self.client.generate_chat_completion(
                model=self.MODEL,
                messages=messages,
                temperature=0.3
            )
            
            # Clean up potential markdown formatting from the response
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
                
            taxonomy = json.loads(cleaned_text.strip())
            
            if not isinstance(taxonomy, list):
                raise ValueError("Response was not a JSON list of strings.")
                
            return taxonomy

        except Exception as e:
            logger.error(f"Failed to generate taxonomy: {e}")
            # Fallback taxonomy
            return [
                f"What is {subject}?",
                f"Why is {subject} important?",
                f"How does {subject} work at a technical level?",
                f"What are the limitations and tradeoffs of {subject}?"
            ]
