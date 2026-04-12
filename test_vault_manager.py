from __future__ import annotations

import json
from pathlib import Path

from nestbrain.core import vault_manager


class StubNvidiaClient:
    def __init__(self, response: str):
        self.response = response

    def generate_chat_completion(self, **kwargs):
        return self.response


class RaisingNvidiaClient:
    def generate_chat_completion(self, **kwargs):
        raise RuntimeError("NVIDIA API unavailable")


def _patch_vault_paths(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    config_path = tmp_path / "config.json"
    vault_root = tmp_path / "My Brain"
    monkeypatch.setattr(vault_manager, "get_config_path", lambda: config_path)
    monkeypatch.setattr(vault_manager, "get_default_vault_root", lambda: vault_root)
    return config_path, vault_root


def _write_note(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_init_vault_creates_root_readme_and_config(monkeypatch, tmp_path: Path):
    config_path, vault_root = _patch_vault_paths(monkeypatch, tmp_path)

    created_root = vault_manager.init_vault()

    assert created_root == vault_root
    assert vault_root.exists()
    assert (vault_root / "README.md").exists()
    assert not any(child.is_dir() for child in vault_root.iterdir() if child.name != "README.md")

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert payload["vault_path"] == str(vault_root)
    assert payload["vault_initialized"] is True


def test_init_vault_keeps_existing_vault(monkeypatch, tmp_path: Path):
    config_path, vault_root = _patch_vault_paths(monkeypatch, tmp_path)
    vault_root.mkdir(parents=True)
    readme_path = vault_root / "README.md"
    readme_path.write_text("existing readme", encoding="utf-8")
    config_path.write_text(
        json.dumps({"vault_path": str(vault_root), "vault_initialized": False}),
        encoding="utf-8",
    )

    created_root = vault_manager.init_vault()

    assert created_root == vault_root
    assert readme_path.read_text(encoding="utf-8") == "existing readme"


def test_classify_and_file_files_into_taxonomy_folder(monkeypatch, tmp_path: Path):
    _, vault_root = _patch_vault_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        vault_manager,
        "nvidia_client",
        StubNvidiaClient(
        json.dumps(
            {
                "category": "Cloud Computing & Infrastructure",
                "subcategory": "DevOps",
                "confidence": 0.93,
                "reasoning": "This note is about deployment automation and platform operations.",
            }
        )
        ),
    )

    source = _write_note(
        tmp_path,
        "ci-note.md",
        "This note discusses deployment pipelines, release automation, and operational controls for shipping software safely.",
    )

    final_path = Path(vault_manager.classify_and_file(str(source)))

    assert final_path.parent == vault_root / "Cloud Computing & Infrastructure" / "DevOps"
    assert final_path.exists()
    assert not source.exists()

    content = final_path.read_text(encoding="utf-8")
    assert "_classified_by: AI (auto)_" in content
    assert "_category: Cloud Computing & Infrastructure_" in content
    assert "_subcategory: DevOps_" in content
    assert "_confidence: 0.93_" in content

    log_payload = json.loads((vault_root / "vault_log.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert log_payload["note_name"] == "ci-note.md"
    assert log_payload["target_path"] == str(final_path)


def test_classify_and_file_empty_llm_response_uses_keyword_heuristic(monkeypatch, tmp_path: Path):
    _, vault_root = _patch_vault_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(vault_manager, "nvidia_client", StubNvidiaClient(""))

    source = _write_note(
        tmp_path,
        "infra-note.md",
        "This note covers kubernetes clusters, docker images, and devops deployment pipelines in production systems.",
    )

    final_path = Path(vault_manager.classify_and_file(str(source)))

    assert final_path.parent == vault_root / "Cloud Computing & Infrastructure"
    assert final_path.exists()
    assert "unclassified" not in str(final_path).lower()


def test_classify_and_file_no_keywords_uses_hardcoded_fallback(monkeypatch, tmp_path: Path):
    _, vault_root = _patch_vault_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(vault_manager, "nvidia_client", StubNvidiaClient("not json"))

    source = _write_note(
        tmp_path,
        "ambiguous-note.md",
        "XQZ flarn blort nimbic quoras. Zinth vex lumar. Tral nix ombra pelk tunar.",
    )

    final_path = Path(vault_manager.classify_and_file(str(source)))

    expected_domain = vault_manager.FALLBACK_TAXONOMY_DOMAINS[0]
    assert final_path.parent == vault_root / expected_domain
    assert "unclassified" not in str(final_path).lower()


def test_no_note_is_filed_under_unclassified(monkeypatch, tmp_path: Path):
    _, vault_root = _patch_vault_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(vault_manager, "nvidia_client", RaisingNvidiaClient())

    source = _write_note(
        tmp_path,
        "security-note.md",
        "Threat modeling with owasp controls and encryption standards improves application security posture.",
    )

    final_path = Path(vault_manager.classify_and_file(str(source)))
    assert final_path.exists()
    assert "unclassified" not in str(final_path).lower()

    audit = vault_manager.audit_unclassified_notes(vault_root)
    assert audit["has_unclassified"] is False
    assert audit["count"] == 0


def test_classify_and_file_renames_on_collision(monkeypatch, tmp_path: Path):
    _, vault_root = _patch_vault_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        vault_manager,
        "nvidia_client",
        StubNvidiaClient(
        json.dumps(
            {
                "category": "Artificial Intelligence & Data",
                "subcategory": "Machine Learning (ML)",
                "confidence": 0.91,
                "reasoning": "The note is about model training and evaluation.",
            }
        )
        ),
    )

    source1 = _write_note(tmp_path, "collision.md", "This note discusses training data, features, evaluation, and model iterations in a machine learning workflow.")
    first_path = Path(vault_manager.classify_and_file(str(source1)))

    source2 = _write_note(tmp_path, "collision.md", "This note discusses training data, features, evaluation, and model iterations in a machine learning workflow.")
    second_path = Path(vault_manager.classify_and_file(str(source2)))

    assert first_path.exists()
    assert second_path.exists()
    assert second_path != first_path
    assert second_path.stem.startswith("collision_")


def test_get_vault_stats_counts_top_level_categories(monkeypatch, tmp_path: Path):
    _, vault_root = _patch_vault_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        vault_manager,
        "nvidia_client",
        StubNvidiaClient(
        json.dumps(
            {
                "category": "Design & User Experience",
                "subcategory": "User Interface (UI) Design",
                "confidence": 0.95,
                "reasoning": "The note discusses layout and interface patterns.",
            }
        )
        ),
    )

    note_a = _write_note(tmp_path, "ui-note.md", "This note covers layout, interaction patterns, and interface design considerations for desktop software.")
    vault_manager.classify_and_file(str(note_a))

    monkeypatch.setattr(
        vault_manager,
        "nvidia_client",
        StubNvidiaClient(
        json.dumps(
            {
                "category": "Cybersecurity",
                "subcategory": None,
                "confidence": 0.88,
                "reasoning": "The note is about threat modeling and security controls.",
            }
        )
        ),
    )
    note_b = _write_note(tmp_path, "security-note.md", "This note covers threat modeling, vulnerability triage, and security control decisions for a service.")
    vault_manager.classify_and_file(str(note_b))

    stats = vault_manager.get_vault_stats()

    assert stats["Design & User Experience"] == 1
    assert stats["Cybersecurity"] == 1
    assert all("unclassified" not in key.lower() for key in stats)