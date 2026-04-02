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
    MAX_FOLLOWUPS = 3
    MIN_ANSWER_CHARS = 220
    MAX_NOTEBOOKLM_RETRIES = 2

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
        print(f"DEBUG:QA_LOOP:START - Starting Q&A research with {len(taxonomy)} taxonomy questions")
        logger.info(f"Starting Q&A research loop across {len(taxonomy)} distinct taxonomy branches.")
        qa_history = []

        for idx, base_question in enumerate(taxonomy):
            print(f"DEBUG:QA_LOOP:QUESTION_{idx} - Processing base question {idx+1}/{len(taxonomy)}")
            logger.info(f"Querying NotebookLM: {base_question}")
            print(f"DEBUG:QA_LOOP:NOTEBOOKLM_ASK_START - About to call NotebookLM for: {base_question[:100]}")
            answer = await self._ask_notebooklm_with_retry(notebook_id, base_question)
            print(f"DEBUG:QA_LOOP:NOTEBOOKLM_ASK_COMPLETE - Received answer of {len(answer)} chars")
            if self._is_low_signal(answer):
                refinement = self._refine_question_for_precision(base_question)
                refined_answer = await self._ask_notebooklm_with_retry(notebook_id, refinement)
                if len(refined_answer.strip()) > len(answer.strip()):
                    answer = refined_answer
                    base_question = refinement
            
            qa_history.append({
                "question": base_question,
                "answer": answer,
                "is_followup": False,
            })

            # Check if we need follow-ups using the devstral model
            follow_ups = self._evaluate_follow_ups(base_question, answer)
            if self._is_low_signal(answer):
                follow_ups.extend(self._deterministic_recovery_followups(base_question))
            follow_ups = self._dedupe_questions(follow_ups)[: self.MAX_FOLLOWUPS]
            
            for fq_question in follow_ups:
                logger.info(f"Executing follow-up query: {fq_question}")
                fq_answer = await self._ask_notebooklm_with_retry(notebook_id, fq_question)
                qa_history.append({
                    "question": fq_question,
                    "answer": fq_answer,
                    "is_followup": True,
                    "parent_question": base_question
                })

        # Ensure cross-cutting precision across architecture, implementation, and risks.
        print(f"DEBUG:QA_LOOP:COVERAGE_START - Building coverage questions")
        coverage_questions = self._build_coverage_questions(taxonomy, qa_history)
        print(f"DEBUG:QA_LOOP:COVERAGE_COUNT - {len(coverage_questions)} coverage questions")
        for cq in coverage_questions:
            logger.info(f"Executing coverage query: {cq}")
            cq_answer = await self._ask_notebooklm_with_retry(notebook_id, cq)
            qa_history.append(
                {
                    "question": cq,
                    "answer": cq_answer,
                    "is_followup": True,
                    "parent_question": "coverage",
                }
            )

        print(f"DEBUG:QA_LOOP:COMPLETE - Q&A research complete with {len(qa_history)} total Q&A entries")
        return qa_history

    async def _ask_notebooklm_with_retry(self, notebook_id: str, question: str) -> str:
        """Ask NotebookLM with bounded retries and richer re-prompts for thin responses."""
        print(f"DEBUG:NOTEBOOKLM_RETRY:START - Asking: {question[:80]}")
        query = question
        for attempt in range(self.MAX_NOTEBOOKLM_RETRIES + 1):
            print(f"DEBUG:NOTEBOOKLM_RETRY:ATTEMPT_{attempt} - Calling synthesize attempt {attempt+1}")
            answer = (await self.nlm.synthesize(notebook_id, query)).strip()
            print(f"DEBUG:NOTEBOOKLM_RETRY:ATTEMPT_{attempt}_COMPLETE - Received {len(answer)} chars")
            if not self._is_low_signal(answer):
                print(f"DEBUG:NOTEBOOKLM_RETRY:SUCCESS - Answer quality acceptable")
                return answer
            if attempt < self.MAX_NOTEBOOKLM_RETRIES:
                query = self._refine_question_for_precision(question)
        print(f"DEBUG:NOTEBOOKLM_RETRY:FALLBACK - Returning answer after max retries")
        return answer

    def _is_low_signal(self, answer: str) -> bool:
        text = (answer or "").strip()
        if len(text) < self.MIN_ANSWER_CHARS:
            return True
        lower = text.lower()
        low_signal_markers = [
            "i don't know",
            "not enough information",
            "no sources",
            "unable to answer",
            "cannot determine",
        ]
        return any(marker in lower for marker in low_signal_markers)

    def _refine_question_for_precision(self, question: str) -> str:
        return (
            f"{question}\n"
            "Answer with source-grounded precision. Include: "
            "(1) key mechanisms, (2) concrete examples, (3) limitations, and (4) implementation details."
        )

    def _deterministic_recovery_followups(self, question: str) -> List[str]:
        return [
            f"What are the concrete implementation steps for: {question}",
            f"What are the most important limitations and failure modes related to: {question}",
            f"Give 2 practical examples or case studies for: {question}",
        ]

    def _build_coverage_questions(self, taxonomy: List[str], qa_history: List[Dict[str, str]]) -> List[str]:
        """Add targeted coverage only when prior responses appear shallow."""
        low_signal_count = sum(1 for entry in qa_history if self._is_low_signal(entry.get("answer", "")))
        if low_signal_count == 0 and len(qa_history) >= max(8, len(taxonomy)):
            return []
        return [
            "Synthesize the end-to-end architecture implied by all sources, including components and data flow.",
            "List the highest-impact implementation decisions and the tradeoffs for each.",
            "Identify major risks, edge cases, and validation checks needed before production use.",
        ]

    def _dedupe_questions(self, questions: List[str]) -> List[str]:
        deduped: List[str] = []
        seen: set[str] = set()
        for q in questions:
            cleaned = " ".join(str(q).split()).strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(cleaned)
        return deduped

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
                
            # Limit follow ups to control API and runtime costs.
            return questions[: self.MAX_FOLLOWUPS]
            
        except Exception as e:
            logger.error(f"Failed to evaluate follow-ups: {e}")
            return []
