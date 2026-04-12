import asyncio
import json
from pathlib import Path

from nestbrain.core.stages.entity_extractor import EntityExtractor
from nestbrain.core.stages.master_synthesizer import MasterSynthesizer
from nestbrain.core.stages.note_seeder import NoteSeeder
from nestbrain.core.stages.notewriter_stage import write_note
from nestbrain.core.note_renderer import SynthesisResult


class StubLLMClient:
    def __init__(self, response: str, configured: bool = True):
        self._response = response
        self._configured = configured

    def generate_chat_completion(self, **kwargs):
        return self._response

    def is_configured(self) -> bool:
        return self._configured


def test_synthesizer_weaves_inline_and_removes_link_sections():
    synth = MasterSynthesizer()
    content = (
        "# HTTP\n\n"
        "HTTP depends on TCP/IP and follows the OSI Model.\n"
        "Later, TCP/IP appears again in troubleshooting guidance.\n\n"
        "## Knowledge Graph\n"
        "[[TCP/IP]]\n"
        "[[OSI Model]]\n"
    )

    updated = synth.weave_inline_wikilinks(content, ["TCP/IP", "OSI Model"])

    assert "## Knowledge Graph" not in updated
    assert "HTTP depends on [[TCP/IP]] and follows the [[OSI Model]]." in updated
    assert updated.count("[[TCP/IP]]") == 1
    assert updated.count("[[OSI Model]]") == 1


def test_entity_extractor_filters_by_confidence_and_keeps_justifications():
    extractor = EntityExtractor()
    extractor.client = StubLLMClient(
        json.dumps(
            [
                {
                    "entity": "JWT Authentication",
                    "confidence": 0.92,
                    "justification": "Named security mechanism with clear standards and implementation depth.",
                },
                {
                    "entity": "strategy",
                    "confidence": 0.40,
                    "justification": "Too generic.",
                },
                {
                    "entity": "Kubernetes",
                    "confidence": 0.75,
                    "justification": "Concrete orchestration platform with operational depth.",
                },
            ]
        )
    )

    entities = extractor.extract_entities("dummy master note")

    assert entities == ["JWT Authentication", "Kubernetes"]
    assert len(extractor.last_scored_entities) == 3
    assert all("justification" in row for row in extractor.last_scored_entities)


def test_note_seeder_skips_semantic_duplicate_via_alias_and_logs(tmp_path: Path):
    existing_note = tmp_path / "kubernetes.md"
    existing_note.write_text(
        "---\n"
        "aliases: [K8s, Kube]\n"
        "---\n"
        "# Kubernetes\n",
        encoding="utf-8",
    )

    seeder = NoteSeeder(str(tmp_path))
    seeder.client = StubLLMClient("{}", configured=False)

    ok = seeder.process_extracted_term("K8s", "context", "Container Orchestration")

    assert ok is True
    assert seeder.get_link_overrides().get("K8s") == "K8s"

    log_path = tmp_path / "seeder_log.json"
    assert log_path.exists()
    records = json.loads(log_path.read_text(encoding="utf-8"))
    assert records[-1]["action"] == "skipped"
    assert records[-1]["matched_note"] == "kubernetes"


def test_note_seeder_creates_note_with_alias_frontmatter(tmp_path: Path, monkeypatch):
    seeder = NoteSeeder(str(tmp_path))
    seeder.client = StubLLMClient("# Retrieval-Augmented Generation (RAG)\n\nStub content")

    from nestbrain.core.stages import note_seeder as note_seeder_module
    monkeypatch.setattr(note_seeder_module, "classify_and_file", lambda path: path)

    created = seeder.process_extracted_term(
        "Retrieval-Augmented Generation (RAG)",
        "context",
        "LLM Systems",
    )

    assert created is True
    expected_note = (
        tmp_path
        / "20_Concepts"
        / "Systems Design"
        / "retrieval-augmented-generation-rag.md"
    )
    assert expected_note.exists()

    content = expected_note.read_text(encoding="utf-8")
    assert "aliases: [\"Retrieval-Augmented Generation (RAG)\"]" in content


def test_note_seeder_matches_existing_slug_and_backfills_alias(tmp_path: Path):
    existing_note = tmp_path / "retrieval-augmented-generation-rag.md"
    existing_note.write_text(
        "# retrieval-augmented-generation-rag\n\nExisting content\n",
        encoding="utf-8",
    )

    seeder = NoteSeeder(str(tmp_path))
    seeder.client = StubLLMClient("{}", configured=False)

    candidate = "Retrieval-Augmented Generation (RAG)"
    ok = seeder.process_extracted_term(candidate, "context", "LLM Systems")

    assert ok is True
    assert seeder.get_link_overrides().get(candidate) == candidate

    updated = existing_note.read_text(encoding="utf-8")
    assert "aliases: [\"Retrieval-Augmented Generation (RAG)\"]" in updated


def test_note_seeder_creates_when_no_match_and_logs(tmp_path: Path, monkeypatch):
    seeder = NoteSeeder(str(tmp_path))
    seeder.client = StubLLMClient("{}", configured=False)

    monkeypatch.setattr(seeder, "_seed_new_note", lambda *args, **kwargs: True)

    ok = seeder.process_extracted_term("Redis Sorted Set", "context", "Data Structures")

    assert ok is True

    log_path = tmp_path / "seeder_log.json"
    records = json.loads(log_path.read_text(encoding="utf-8"))
    assert records[-1]["action"] == "created"
    assert records[-1]["entity"] == "Redis Sorted Set"


def test_notewriter_skips_filing_when_classification_fails(tmp_path: Path, monkeypatch):
    from nestbrain.core.stages import notewriter_stage as stage_module

    def raise_value_error(_path: str) -> str:
        raise ValueError("Unable to classify note 'edge-case-title'")

    failure_records: list[dict[str, str]] = []

    def capture_failure(stage: str, note_title: str, reason: str, source_path: str | None = None):
        failure_records.append(
            {
                "stage": stage,
                "note_title": note_title,
                "reason": reason,
                "source_path": source_path or "",
            }
        )
        return tmp_path / "classification_failures.jsonl"

    monkeypatch.setattr(stage_module, "classify_and_file", raise_value_error)
    monkeypatch.setattr(stage_module, "log_classification_failure", capture_failure)

    synthesis = SynthesisResult(
        academic_synthesis="Academic synthesis",
        conceptual_deep_dive="Deep dive",
        actionable_knowledge="Takeaways",
        knowledge_connections="Connections",
        critical_evaluation="Critical evaluation",
        glossary="Glossary",
    )

    relative_path = asyncio.run(
        write_note(
            collection_slug="edge-case-title",
            collection_display_name="Edge Case Title",
            items=[{"key": "A1", "title": "Source"}],
            synthesis=synthesis,
            media_paths={},
            vault_path=str(tmp_path),
            status_callback=None,
        )
    )

    assert relative_path == ""
    assert failure_records
    assert failure_records[0]["stage"] == "notewriter_stage"
    assert failure_records[0]["note_title"] == "Edge Case Title"


def test_note_seeder_logs_classification_failure_without_crashing(tmp_path: Path, monkeypatch):
    from nestbrain.core.stages import note_seeder as seeder_module

    failure_records: list[dict[str, str]] = []

    def raise_value_error(_path: str) -> str:
        raise ValueError("Unable to classify note 'Redis Streams'")

    def capture_failure(stage: str, note_title: str, reason: str, source_path: str | None = None):
        failure_records.append(
            {
                "stage": stage,
                "note_title": note_title,
                "reason": reason,
                "source_path": source_path or "",
            }
        )
        return tmp_path / "classification_failures.jsonl"

    monkeypatch.setattr(seeder_module, "classify_and_file", raise_value_error)
    monkeypatch.setattr(seeder_module, "log_classification_failure", capture_failure)

    seeder = NoteSeeder(str(tmp_path))
    seeder.client = StubLLMClient("# Redis Streams\n\nseed content")

    ok = seeder.process_extracted_term("Redis Streams", "context", "Message Queues")

    assert ok is False
    assert failure_records
    assert failure_records[0]["stage"] == "note_seeder"
    assert failure_records[0]["note_title"] == "Redis Streams"
