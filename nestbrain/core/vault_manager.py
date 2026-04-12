from __future__ import annotations

import json
import logging
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from .nvidia_client import nvidia_client
from .paths import get_config_path, get_default_vault_root, get_logs_dir
from .utils import to_slug

logger = logging.getLogger(__name__)

VAULT_NAME = "My Brain"
CLASSIFICATION_THRESHOLD = 0.75

TAXONOMY: dict[str, tuple[str, ...]] = {
    "Software Engineering & Development": (
        "Frontend Development",
        "Backend Development",
        "Full-Stack Development",
        "Mobile App Development",
        "Game Development",
        "Embedded Systems",
        "Desktop App Development",
    ),
    "Artificial Intelligence & Data": (
        "Machine Learning (ML)",
        "Deep Learning",
        "Natural Language Processing (NLP)",
        "Computer Vision",
        "Data Science",
        "Data Engineering",
        "MLOps",
    ),
    "Cloud Computing & Infrastructure": (
        "Cloud Architecture",
        "DevOps",
        "Site Reliability Engineering (SRE)",
        "Containerization & Orchestration",
        "Infrastructure as Code (IaC)",
        "Serverless Computing",
    ),
    "Cybersecurity": (
        "Application Security (AppSec)",
        "Network Security",
        "Offensive Security (Red Team)",
        "Defensive Security (Blue Team)",
        "Cryptography",
        "Identity & Access Management (IAM)",
        "Digital Forensics & Incident Response (DFIR)",
    ),
    "Hardware & Computer Architecture": (
        "Computer Architecture",
        "Semiconductor Engineering",
        "IoT Hardware",
        "PCB Design",
    ),
    "Networking & Communications": (
        "Network Engineering",
        "Telecommunications",
        "Wireless Technologies",
    ),
    "Emerging Technologies": (
        "Blockchain & Web3",
        "Quantum Computing",
        "Spatial Computing (AR/VR/MR)",
        "Edge Computing",
    ),
    "IT Operations & Management": (
        "System Administration",
        "Database Administration (DBA)",
        "IT Service Management (ITSM)",
    ),
    "Design & User Experience": (
        "User Interface (UI) Design",
        "User Experience (UX) Research",
        "Interaction Design",
    ),
}

# Last-resort domains to ensure every note receives a valid taxonomy category.
FALLBACK_TAXONOMY_DOMAINS: tuple[str, ...] = tuple(TAXONOMY.keys())

# Keyword-to-domain mapping used when LLM responses are empty or invalid.
KEYWORD_DOMAIN_RULES: tuple[tuple[str, str], ...] = (
    ("frontend", "Software Engineering & Development"),
    ("backend", "Software Engineering & Development"),
    ("api", "Software Engineering & Development"),
    ("python", "Software Engineering & Development"),
    ("javascript", "Software Engineering & Development"),
    ("react", "Software Engineering & Development"),
    ("docker", "Cloud Computing & Infrastructure"),
    ("kubernetes", "Cloud Computing & Infrastructure"),
    ("terraform", "Cloud Computing & Infrastructure"),
    ("devops", "Cloud Computing & Infrastructure"),
    ("mlops", "Artificial Intelligence & Data"),
    ("machine learning", "Artificial Intelligence & Data"),
    ("deep learning", "Artificial Intelligence & Data"),
    ("nlp", "Artificial Intelligence & Data"),
    ("data pipeline", "Artificial Intelligence & Data"),
    ("security", "Cybersecurity"),
    ("owasp", "Cybersecurity"),
    ("encryption", "Cybersecurity"),
    ("network", "Networking & Communications"),
    ("tcp", "Networking & Communications"),
    ("routing", "Networking & Communications"),
    ("iot", "Hardware & Computer Architecture"),
    ("microcontroller", "Hardware & Computer Architecture"),
    ("semiconductor", "Hardware & Computer Architecture"),
    ("blockchain", "Emerging Technologies"),
    ("quantum", "Emerging Technologies"),
    ("ar/vr", "Emerging Technologies"),
    ("system administration", "IT Operations & Management"),
    ("database", "IT Operations & Management"),
    ("ui", "Design & User Experience"),
    ("ux", "Design & User Experience"),
    ("interaction design", "Design & User Experience"),
)


def init_vault() -> Path:
    """Initialize the default vault root on first launch and persist it to config."""
    config_path = get_config_path()
    config = _load_config(config_path)

    vault_path_value = str(config.get("vault_path") or "").strip()
    vault_initialized = bool(config.get("vault_initialized", False))

    vault_root = (
        Path(vault_path_value).expanduser().resolve()
        if vault_path_value
        else get_default_vault_root().expanduser().resolve()
    )
    created = not vault_root.exists()
    vault_root.mkdir(parents=True, exist_ok=True)

    if created:
        readme_path = vault_root / "README.md"
        if not readme_path.exists():
            _write_text_atomic(readme_path, _build_vault_readme())

    config["vault_path"] = str(vault_root)
    config["vault_initialized"] = True
    _save_config(config_path, config)
    return vault_root


def classify_and_file(note_path: str) -> str:
    """Classify a generated note and move it into the correct vault folder."""
    source_path = Path(note_path).expanduser().resolve()
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(f"Note file not found: {note_path}")

    vault_root = init_vault()
    source_bytes = source_path.read_bytes()
    is_binary = False
    if _looks_binary(source_bytes):
        is_binary = True
        content = ""
        title = source_path.stem
        classification = _classify_note(title=title, content=content)
    else:
        content = source_bytes.decode("utf-8", errors="ignore")
        title = source_path.stem
        classification = _classify_note(title=title, content=content)

    category = _normalize_category(str(classification.get("category") or "").strip())
    if not category:
        raise ValueError(f"Unable to classify note '{title}': no valid taxonomy category returned.")

    subcategory = classification.get("subcategory")
    if isinstance(subcategory, str):
        subcategory = _normalize_subcategory(category, subcategory.strip() or None)
    else:
        subcategory = None

    confidence = _coerce_confidence(classification.get("confidence"))
    reasoning = str(classification.get("reasoning") or "Classification fallback used.").strip()

    filed_on = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    footer = _build_metadata_footer(category, subcategory, confidence, filed_on)

    body = "" if is_binary else content
    body = _strip_existing_footer(body)

    target_dir = vault_root / category
    if subcategory:
        target_dir = target_dir / subcategory
    target_dir.mkdir(parents=True, exist_ok=True)

    suffix = source_path.suffix if source_path.suffix else ".md"
    target_path = target_dir / f"{source_path.stem}{suffix}"
    if target_path.exists() and target_path.resolve() != source_path:
        target_path = _unique_target_path(target_dir, source_path.stem, suffix)

    temp_path = _write_temp_text(target_dir, f"{body.rstrip()}\n\n{footer}\n", suffix=suffix)
    temp_path.replace(target_path)

    if source_path.exists() and source_path.resolve() != target_path.resolve():
        try:
            source_path.unlink()
        except FileNotFoundError:
            pass

    _append_vault_log(
        vault_root,
        {
            "timestamp": filed_on,
            "note_name": source_path.name,
            "source_path": str(source_path),
            "target_path": str(target_path),
            "category": category,
            "subcategory": subcategory,
            "confidence": confidence,
            "reasoning": reasoning,
        },
    )

    logger.info("Classified note %s filed to %s with confidence %.2f", source_path.name, target_path, confidence)

    return str(target_path)


def get_vault_stats() -> dict[str, int]:
    """Return counts of filed notes per top-level category."""
    vault_root = _resolve_vault_root(create=False)
    stats = {category: 0 for category in TAXONOMY}

    if vault_root is None or not vault_root.exists():
        return stats

    for note_file in vault_root.rglob("*"):
        if not note_file.is_file() or note_file.name == "README.md":
            continue
        if note_file.suffix.lower() not in {".md", ".txt"}:
            continue
        rel_parts = note_file.relative_to(vault_root).parts
        if not rel_parts:
            continue
        top_level = rel_parts[0]
        if top_level in stats:
            stats[top_level] += 1

    return stats


def find_note_path(title: str, vault_root: str | Path | None = None) -> Path | None:
    """Find a note by title, searching recursively through the vault."""
    root = Path(vault_root).expanduser().resolve() if vault_root else _resolve_vault_root(create=False)
    if root is None or not root.exists() or not title.strip():
        return None

    normalized = _sanitize_filename(title)
    exact_title = title.strip().lower()
    candidates: list[Path] = []

    for pattern in ("*.md", "*.txt"):
        for file_path in root.rglob(pattern):
            stem = file_path.stem.lower()
            if stem == exact_title:
                return file_path
            if stem == normalized.lower():
                candidates.append(file_path)

    return candidates[0] if candidates else None


def _classify_note(title: str, content: str) -> dict[str, Any]:
    llm_result = _classify_note_with_retries(title=title, content=content)
    if llm_result:
        return llm_result

    heuristic_domain = _keyword_fallback_domain(title=title, content=content)
    if heuristic_domain:
        return {
            "category": heuristic_domain,
            "subcategory": None,
            "confidence": 0.61,
            "reasoning": "Keyword heuristic fallback selected taxonomy domain.",
        }

    hardcoded_domain = _hardcoded_fallback_domain(title=title, content=content)
    if hardcoded_domain:
        return {
            "category": hardcoded_domain,
            "subcategory": None,
            "confidence": 0.4,
            "reasoning": "Hardcoded taxonomy fallback selected default domain.",
        }

    raise ValueError(f"Unable to classify note '{title}' after LLM retries and all fallbacks.")


def _classify_note_with_retries(title: str, content: str) -> dict[str, Any] | None:
    for attempt in range(3):
        parsed = _classify_note_once(title=title, content=content, attempt=attempt)
        if not isinstance(parsed, dict):
            continue
        category = _normalize_category(str(parsed.get("category") or "").strip())
        if not category:
            continue
        subcategory = _normalize_subcategory(category, parsed.get("subcategory"))
        return {
            "category": category,
            "subcategory": subcategory,
            "confidence": _coerce_confidence(parsed.get("confidence")),
            "reasoning": str(parsed.get("reasoning") or "LLM classification result.").strip(),
        }
    return None


def _classify_note_once(title: str, content: str, attempt: int) -> dict[str, Any] | None:
    taxonomy_lines = []
    for category, subcategories in TAXONOMY.items():
        taxonomy_lines.append(f"{category}: {', '.join(subcategories)}")

    retry_instruction = ""
    if attempt == 1:
        retry_instruction = (
            "Previous attempt was invalid. Return EXACTLY one of the taxonomy category names. "
            "Do not return null, empty strings, or unknown category labels."
        )
    elif attempt == 2:
        retry_instruction = (
            "Final attempt: choose the single closest parent category even if uncertain. "
            "subcategory may be null."
        )

    system_prompt = (
        "You are a strict document classifier. Given the content of a note, you must\n"
        "determine exactly which category and subcategory it belongs to from the taxonomy below.\n\n"
        "Return ONLY a valid JSON object in this exact format — no explanation, no markdown:\n"
        "{\n"
        '  "category": "<exact parent folder name>",\n'
        '  "subcategory": "<exact subfolder name or null>",\n'
        '  "confidence": <float between 0.0 and 1.0>,\n'
        '  "reasoning": "<one sentence max>"\n'
        "}\n\n"
        + (retry_instruction + "\n\n" if retry_instruction else "")
        + "TAXONOMY:\n"
        + "\n".join(taxonomy_lines)
    )
    user_prompt = f"Title: {title}\n\nContent:\n{content[:12000]}"

    try:
        response_text = nvidia_client.generate_chat_completion(
            model="deepseek-ai/deepseek-v3.2",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=512,
        )
        parsed = _extract_json_object(response_text)
        if isinstance(parsed, dict):
            return parsed
    except Exception as exc:
        logger.warning("Vault classification attempt %s failed for %s: %s", attempt + 1, title, exc)
    return None


def _keyword_fallback_domain(title: str, content: str) -> str | None:
    text = f"{title}\n{content}".lower()
    scores: dict[str, int] = {category: 0 for category in TAXONOMY}
    for keyword, category in KEYWORD_DOMAIN_RULES:
        if keyword in text:
            scores[category] += 1

    best_category = None
    best_score = 0
    for category, score in scores.items():
        if score > best_score:
            best_category = category
            best_score = score

    if best_category and best_score > 0:
        return best_category
    return None


def _hardcoded_fallback_domain(title: str, content: str) -> str | None:
    if not FALLBACK_TAXONOMY_DOMAINS:
        return None

    # Deterministic selection using title/content tokens against category names.
    text = f"{title} {content}".lower()
    category_scores: dict[str, int] = {category: 0 for category in FALLBACK_TAXONOMY_DOMAINS}
    for category in FALLBACK_TAXONOMY_DOMAINS:
        tokens = re.findall(r"[a-z]+", category.lower())
        for token in tokens:
            if token in text:
                category_scores[category] += 1

    ranked = sorted(FALLBACK_TAXONOMY_DOMAINS, key=lambda item: category_scores[item], reverse=True)
    return ranked[0]


def log_classification_failure(
    stage: str,
    note_title: str,
    reason: str,
    source_path: str | None = None,
) -> Path:
    payload = {
        "timestamp": datetime.now().isoformat(),
        "stage": stage,
        "note_title": note_title,
        "reason": reason,
        "source_path": source_path or "",
    }
    logs_dir = get_logs_dir()
    log_path = logs_dir / "classification_failures.jsonl"
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    logger.warning("Classification failed in %s for %s: %s", stage, note_title, reason)
    return log_path


def append_vault_log_entry(vault_root: str | Path | None, payload: dict[str, Any]) -> Path:
    root = Path(vault_root).expanduser().resolve() if vault_root else _resolve_vault_root(create=False)
    if root is None:
        root = _resolve_vault_root(create=True)
    if root is None:
        raise ValueError("Vault root could not be resolved for logging.")

    _append_vault_log(root, payload)
    return root / "vault_log.jsonl"


def audit_unclassified_notes(vault_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(vault_root).expanduser().resolve() if vault_root else _resolve_vault_root(create=False)
    if root is None or not root.exists():
        return {"has_unclassified": False, "count": 0, "notes": []}

    affected_notes: list[str] = []
    for directory in root.rglob("*"):
        if not directory.is_dir():
            continue
        normalized = directory.name.strip().lower().replace(" ", "")
        if normalized not in {"unclassified", "_unclassified"}:
            continue
        for note_path in directory.rglob("*.md"):
            affected_notes.append(str(note_path.relative_to(root)))

    result = {
        "has_unclassified": bool(affected_notes),
        "count": len(affected_notes),
        "notes": sorted(affected_notes),
    }
    if affected_notes:
        logger.warning("Vault audit found legacy unclassified notes: %s", ", ".join(sorted(affected_notes)))
    else:
        logger.info("Vault audit found no unclassified notes.")
    return result


def _build_vault_readme() -> str:
    taxonomy_text = []
    for category, subcategories in TAXONOMY.items():
        taxonomy_text.append(f"- {category}")
        for subcategory in subcategories:
            taxonomy_text.append(f"  - {subcategory}")

    date_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (
        "# My Brain Vault\n\n"
        "This vault is the auto-managed knowledge store for Nestbrain.\n\n"
        "## Intended Folder Taxonomy\n\n"
        + "\n".join(taxonomy_text)
        + "\n\n"
        "## Filing Behavior\n\n"
        "Subfolders are created automatically by the AI classifier as notes are filed.\n\n"
        f"## Initialized\n\n{date_text}\n"
    )


def _build_metadata_footer(category: str, subcategory: str | None, confidence: float, filed_on: str) -> str:
    subcategory_value = subcategory if subcategory is not None else "null"
    return (
        "---\n"
        "_classified_by: AI (auto)_  \n"
        f"_category: {category}_  \n"
        f"_subcategory: {subcategory_value}_  \n"
        f"_confidence: {confidence:.2f}_  \n"
        f"_filed_on: {filed_on}_  \n"
        "---"
    )


def _append_vault_log(vault_root: Path, payload: dict[str, Any]) -> None:
    log_path = vault_root / "vault_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _save_config(config_path: Path, config: dict[str, Any]) -> None:
    _write_text_atomic(config_path, json.dumps(config, indent=2, ensure_ascii=False))


def _resolve_vault_root(create: bool) -> Path | None:
    config = _load_config(get_config_path())
    configured = str(config.get("vault_path") or "").strip()

    if configured:
        resolved = Path(configured).expanduser().resolve()
        if resolved.exists() or not create:
            return resolved

    default_root = get_default_vault_root().expanduser().resolve()
    if create:
        default_root.mkdir(parents=True, exist_ok=True)
        return default_root
    if default_root.exists():
        return default_root
    return None


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=str(path.parent),
        prefix=f".{path.stem}.",
        suffix=".tmp",
    ) as handle:
        handle.write(content)
        temp_name = handle.name
    Path(temp_name).replace(path)


def _write_temp_text(directory: Path, content: str, suffix: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=str(directory),
        prefix=".nestbrain.",
        suffix=suffix,
    ) as handle:
        handle.write(content)
        return Path(handle.name)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(cleaned[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _coerce_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except Exception:
        confidence = 0.0
    return max(0.0, min(1.0, confidence))


def _normalize_category(category: str) -> str:
    if not category:
        return ""
    if category in TAXONOMY:
        return category
    for known_category in TAXONOMY:
        if known_category.lower() == category.lower():
            return known_category
    return ""


def _normalize_subcategory(category: str, subcategory: Any) -> str | None:
    if not isinstance(subcategory, str):
        return None
    candidate = subcategory.strip()
    if not candidate:
        return None

    known_subcategories = TAXONOMY.get(category, ())
    if candidate in known_subcategories:
        return candidate
    for known in known_subcategories:
        if known.lower() == candidate.lower():
            return known
    return None


def _sanitize_filename(value: str) -> str:
    return to_slug(value)


def _looks_binary(data: bytes) -> bool:
    if not data:
        return False
    if b"\x00" in data:
        return True
    sample = data[:4096]
    text_characters = bytes(range(32, 127)) + b"\n\r\t\b\f"
    non_text = sum(byte not in text_characters for byte in sample)
    return (non_text / max(1, len(sample))) > 0.30


def _strip_existing_footer(content: str) -> str:
    marker = "_classified_by: AI (auto)_"
    marker_index = content.rfind(marker)
    if marker_index == -1:
        return content
    block_start = content.rfind("\n---\n", 0, marker_index)
    if block_start == -1:
        return content[:marker_index].rstrip()
    return content[:block_start].rstrip()


def _unique_target_path(directory: Path, stem: str, suffix: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = directory / f"{stem}_{timestamp}{suffix}"
    counter = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{timestamp}_{counter}{suffix}"
        counter += 1
    return candidate