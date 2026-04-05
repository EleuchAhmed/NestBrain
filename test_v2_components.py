import json
from pathlib import Path

from nestbrain.core.stages.entity_extractor import EntityExtractor
from nestbrain.core.stages.master_synthesizer import MasterSynthesizer
from nestbrain.core.stages.note_seeder import NoteSeeder


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
    assert seeder.get_link_overrides().get("K8s") == "kubernetes"

    log_path = tmp_path / "seeder_log.json"
    assert log_path.exists()
    records = json.loads(log_path.read_text(encoding="utf-8"))
    assert records[-1]["action"] == "skipped"
    assert records[-1]["matched_note"] == "kubernetes"


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
