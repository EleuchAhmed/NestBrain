import logging
import re
from typing import List, Dict
from ..nvidia_client import nvidia_client

logger = logging.getLogger(__name__)

class MasterSynthesizer:
    """Layer 1: The Author (deepseek-v3.2)
    Synthesizes all Q&A data into a structured Markdown "Master Note" 
    with headers and Obsidian formatting.
    """
    
    MODEL = "deepseek-ai/deepseek-v3.2"
    REQUIRED_SECTIONS = [
        "## Executive Summary",
        "## Core Concepts",
        "## Architecture and Workflow",
        "## Implementation Details",
        "## Tradeoffs and Risks",
        "## Practical Checklist",
    ]
    FORBIDDEN_LINK_SECTION_PATTERN = re.compile(
        r"(?ims)^##?\s*(related notes|related links|links|knowledge graph)\s*$.*?(?=^##?\s|\Z)"
    )

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
            "- You MUST include these exact sections in order:\n"
            "  1) `## Executive Summary`\n"
            "  2) `## Core Concepts`\n"
            "  3) `## Architecture and Workflow`\n"
            "  4) `## Implementation Details`\n"
            "  5) `## Tradeoffs and Risks`\n"
            "  6) `## Practical Checklist`\n"
            "- Use `###` subsections where needed and include source-grounded detail.\n"
            "- Include concrete mechanisms, constraints, and edge cases, not generic prose.\n"
            "- Do NOT write just a list of Q&As. Integrate the knowledge into a coherent technical note.\n"
            "- Embed Obsidian wikilinks like `[[Term]]` inline in natural sentences at first meaningful mention only.\n"
            "- Never output a standalone section named Related Notes, Links, Related Links, or Knowledge Graph.\n"
            "- Do not list bare wikilinks; each link must be contextualized in a sentence.\n"
            "- Each linked concept should appear as a wikilink only once in the note.\n"
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
            final_text = self._ensure_required_structure(subject, response_text.strip(), qa_history)
            final_text = self.weave_inline_wikilinks(final_text, [])
            self.used_fallback = False
            self.last_error = ""
            
            return final_text
            
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

    def _ensure_required_structure(self, subject: str, content: str, qa_history: List[Dict[str, str]]) -> str:
        """Repair sparse or unstructured model output into required sectioned format."""
        text = (content or "").strip()
        if not text:
            return self._build_required_template(subject, qa_history)

        if not text.startswith("# "):
            text = f"# {subject}\n\n" + text

        missing = [section for section in self.REQUIRED_SECTIONS if section not in text]
        if not missing and len(text) >= 1400:
            return text

        repaired = [text.rstrip(), ""]
        grouped = self._group_qa_by_theme(qa_history)

        for section in missing:
            repaired.append(section)
            repaired.append(self._render_section_body(section, grouped))
            repaired.append("")

        # If the note is still too short, append a deterministic expansion block.
        expanded = "\n".join(repaired).strip()
        if len(expanded) < 1400:
            expanded += "\n\n## Detailed Evidence Notes\n"
            expanded += self._render_evidence_notes(qa_history)
        return self._remove_forbidden_link_sections(expanded)

    def _build_required_template(self, subject: str, qa_history: List[Dict[str, str]]) -> str:
        grouped = self._group_qa_by_theme(qa_history)
        blocks = [f"# {subject}", ""]
        for section in self.REQUIRED_SECTIONS:
            blocks.append(section)
            blocks.append(self._render_section_body(section, grouped))
            blocks.append("")
        blocks.append("## Detailed Evidence Notes")
        blocks.append(self._render_evidence_notes(qa_history))
        return "\n".join(blocks).strip()

    def _group_qa_by_theme(self, qa_history: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
        groups: Dict[str, List[Dict[str, str]]] = {
            "summary": [],
            "concepts": [],
            "architecture": [],
            "implementation": [],
            "risks": [],
            "checklist": [],
        }
        for qa in qa_history:
            question = (qa.get("question") or "").lower()
            target = "concepts"
            if any(k in question for k in ["what is", "why", "importance", "foundational"]):
                target = "summary"
            elif any(k in question for k in ["architecture", "system", "workflow", "component"]):
                target = "architecture"
            elif any(k in question for k in ["implement", "technical", "mechanism", "integration", "how"]):
                target = "implementation"
            elif any(k in question for k in ["risk", "limitation", "tradeoff", "edge case", "failure"]):
                target = "risks"
            elif any(k in question for k in ["checklist", "steps", "validation", "benchmark"]):
                target = "checklist"
            groups[target].append(qa)
        return groups

    def _render_section_body(self, section: str, groups: Dict[str, List[Dict[str, str]]]) -> str:
        mapping = {
            "## Executive Summary": "summary",
            "## Core Concepts": "concepts",
            "## Architecture and Workflow": "architecture",
            "## Implementation Details": "implementation",
            "## Tradeoffs and Risks": "risks",
            "## Practical Checklist": "checklist",
        }
        key = mapping.get(section, "concepts")
        rows = groups.get(key) or groups.get("concepts") or []
        if not rows:
            return "- No direct evidence captured for this section in the current run."

        snippets = []
        for qa in rows[:4]:
            q = (qa.get("question") or "").strip()
            a = (qa.get("answer") or "").strip()
            if not q or not a:
                continue
            snippets.append(f"### {q}\n{a}")

        if snippets:
            return "\n\n".join(snippets)
        return "- Section evidence was present but could not be normalized."

    def _render_evidence_notes(self, qa_history: List[Dict[str, str]]) -> str:
        if not qa_history:
            return "- No Q&A evidence available."
        lines = []
        for qa in qa_history[:10]:
            question = (qa.get("question") or "").strip()
            answer = (qa.get("answer") or "").strip()
            if not question or not answer:
                continue
            lines.append(f"- **{question}**: {answer[:280]}{'...' if len(answer) > 280 else ''}")
        return "\n".join(lines) if lines else "- No usable evidence entries available."

    def weave_inline_wikilinks(
        self,
        content: str,
        link_terms: List[str],
        alias_map: Dict[str, str] | None = None,
    ) -> str:
        """Inject first-mention wikilinks inline and remove forbidden link sections."""
        text = self._remove_forbidden_link_sections(content or "")
        if not text.strip():
            return text

        alias_map = alias_map or {}
        normalized_alias_map = {str(k).strip().lower(): str(v).strip() for k, v in alias_map.items() if str(k).strip() and str(v).strip()}
        linked_targets: set[str] = set(
            m.group(1).strip().lower()
            for m in re.finditer(r"\[\[([^\]|#]+)(?:#[^\]]+)?(?:\|[^\]]+)?\]\]", text)
        )

        for term in link_terms:
            mention = (term or "").strip()
            if not mention:
                continue
            target = (normalized_alias_map.get(mention.lower()) or mention).strip()
            if not target:
                continue
            if target.lower() in linked_targets:
                continue

            replaced = self._replace_first_meaningful_mention(text, mention, f"[[{target}]]")
            if replaced != text:
                text = replaced
                linked_targets.add(target.lower())

        return self._dedupe_existing_wikilinks(text)

    def _remove_forbidden_link_sections(self, text: str) -> str:
        cleaned = self.FORBIDDEN_LINK_SECTION_PATTERN.sub("", text)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip() + "\n"

    def _replace_first_meaningful_mention(self, text: str, term: str, replacement: str) -> str:
        lines = text.splitlines()
        needle = term.lower()
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if re.fullmatch(r"\[\[[^\]]+\]\]", stripped):
                continue

            lower_line = line.lower()
            pos = lower_line.find(needle)
            if pos == -1:
                continue

            before = line[max(0, pos - 2):pos]
            after = line[pos + len(term):pos + len(term) + 2]
            if before == "[[" and after == "]]":
                continue

            lines[idx] = line[:pos] + replacement + line[pos + len(term):]
            return "\n".join(lines)
        return text

    def _dedupe_existing_wikilinks(self, text: str) -> str:
        seen: set[str] = set()

        def _repl(match: re.Match[str]) -> str:
            token = match.group(1).strip()
            key = token.lower()
            if key in seen:
                return token
            seen.add(key)
            return match.group(0)

        return re.sub(r"\[\[([^\]|#]+)(?:#[^\]]+)?(?:\|[^\]]+)?\]\]", _repl, text)
