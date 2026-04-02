import json
import logging
import re
from typing import List, Dict, Any
from ..nvidia_client import nvidia_client

logger = logging.getLogger(__name__)

class QuestionPlanner:
    """Layer 1: The Architect (deepseek-v3.2)
    Generates an exhaustive research taxonomy for the input subject.
    """
    
    MODEL = "deepseek-ai/deepseek-v3.2"

    def __init__(self):
        # Fallback to a valid DeepSeek model identifier for NVIDIA NIM if v3.2 isn't strictly named this
        # e.g. deepseek-ai/deepseek-coder-33b-instruct, etc.
        # Assuming deepseek-v3.2 as per user mapping
        self.client = nvidia_client
        self.used_fallback = False
        self.last_error = ""

    def generate_taxonomy(self, subject: str, context_summary: str = "") -> List[str]:
        """
        Takes a subject and generates a list of essential questions covering:
        what, why, how, when, tradeoffs, limitations, dependencies, history.
        """
        print(f"DEBUG:PLANNER:START - Generating research taxonomy for subject: {subject}")
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
            print(f"DEBUG:PLANNER:NVIDIA_REQUEST_START - About to call NVIDIA API with model {self.MODEL}")
            response_text = self.client.generate_chat_completion(
                model=self.MODEL,
                messages=messages,
                temperature=0.3
            )
            print(f"DEBUG:PLANNER:NVIDIA_REQUEST_COMPLETE - Received response of {len(response_text)} chars")
            
            # Clean up potential markdown formatting from the response
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
                
            taxonomy = json.loads(cleaned_text.strip())
            
            if not isinstance(taxonomy, list):
                raise ValueError("Response was not a JSON list of strings.")
            print(f"DEBUG:PLANNER:COMPLETE - Successfully generated {len(taxonomy)} taxonomy questions")
            self.used_fallback = False
            self.last_error = ""
                
            return taxonomy

        except Exception as e:
            logger.error(f"Failed to generate taxonomy: {e}")
            print(f"DEBUG:PLANNER:FALLBACK - Using fallback taxonomy due to error: {str(e)[:100]}")
            self.used_fallback = True
            self.last_error = str(e)
            return self._build_fallback_taxonomy(subject, context_summary)

    def _build_fallback_taxonomy(self, subject: str, context_summary: str) -> List[str]:
        """Build deterministic but richer questions when model-based planning fails."""
        normalized = re.sub(r"[^A-Za-z0-9 ]+", " ", subject).strip()
        tokens = [token for token in normalized.split() if len(token) > 2]
        focus_terms = tokens[:2]

        base_questions = [
            f"What problem does {subject} solve and why does it matter?",
            f"How does {subject} work end to end in practice?",
            f"What architectural components are required to implement {subject}?",
            f"What tradeoffs, risks, and failure modes are common with {subject}?",
            f"How should {subject} be evaluated, benchmarked, or validated?",
            f"When should teams avoid {subject} and choose an alternative approach?",
        ]

        if focus_terms:
            base_questions.append(
                f"How do {focus_terms[0]} and {focus_terms[-1]} interact within {subject}?"
            )

        if context_summary.strip():
            base_questions.append(
                f"Which details from the provided sources most strongly influence decisions about {subject}?"
            )

        return base_questions
