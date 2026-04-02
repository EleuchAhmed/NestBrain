import json
import logging
from typing import List, Dict, Any
from ..nvidia_client import nvidia_client
from ..notebooklm_bridge import NotebookLMBridge

logger = logging.getLogger(__name__)

class QAndALoop:
    """Layer 1: The Researcher (devstral-2-123b)
    Executes iterative Q&A loops with NotebookLM based on the taxonomy; 
    identifies if follow-up questions are needed.
    """
    
    MODEL = "mistralai/devstral-2-123b-instruct-2512"

    def __init__(self, nlm_bridge: NotebookLMBridge):
        self.nlm = nlm_bridge
        self.client = nvidia_client

    async def execute_research(self, notebook_id: str, taxonomy: List[str]) -> List[Dict[str, str]]:
        """
        Iterates through the generated taxonomy questions.
        For each question, interrogates NotebookLM.
        Then uses the Researcher model to decide if a follow-up is needed based on the answer.
        Returns a list of Q&A dictionaries.
        """
        logger.info(f"Starting Q&A research loop across {len(taxonomy)} distinct taxonomy branches.")
        qa_history = []

        for base_question in taxonomy:
            logger.info(f"Querying NotebookLM: {base_question}")
            
            # Query NotebookLM natively via bridge
            # The original NotebookLMBridge's synthesize method is good for single Q&A
            answer = await self.nlm.synthesize(notebook_id, base_question)
            
            qa_history.append({
                "question": base_question,
                "answer": answer
            })

            # Check if we need follow-ups using the devstral model
            follow_ups = self._evaluate_follow_ups(base_question, answer)
            
            for fq_question in follow_ups:
                logger.info(f"Executing follow-up query: {fq_question}")
                fq_answer = await self.nlm.synthesize(notebook_id, fq_question)
                qa_history.append({
                    "question": fq_question,
                    "answer": fq_answer,
                    "is_followup": True,
                    "parent_question": base_question
                })

        return qa_history

    def _evaluate_follow_ups(self, original_question: str, original_answer: str) -> List[str]:
        """
        Uses devstral-2-123b to determine if the answer missed key details or requires a deeper dive.
        Returns a list of 0-2 follow-up questions.
        """
        system_prompt = (
            "You are a meticulous Researcher. You must evaluate the provided answer to the original question. "
            "If the answer is shallow, missing crucial details, or introduces complex terms that need explaining, "
            "generate 1 or 2 specific follow-up questions.\n"
            "If the answer is comprehensive and solid, return an empty array.\n\n"
            "Respond ONLY with a JSON array of strings representing the follow-up questions. "
            "Do not include markdown blocks, just the raw JSON array."
        )

        user_content = f"Original Question: {original_question}\nAnswer Provided: {original_answer}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]

        try:
            response_text = self.client.generate_chat_completion(
                model=self.MODEL,
                messages=messages,
                temperature=0.2
            )
            
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
                
            questions = json.loads(cleaned_text.strip())
            
            if not isinstance(questions, list):
                return []
                
            # Limit to max 2 follow ups to prevent infinite loops / excessive API usage
            return questions[:2]
            
        except Exception as e:
            logger.error(f"Failed to evaluate follow-ups: {e}")
            return []
