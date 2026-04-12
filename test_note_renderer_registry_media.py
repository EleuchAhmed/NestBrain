from pathlib import Path

from nestbrain.core.note_renderer import SynthesisResult, merge_into_existing_note, slugify
from nestbrain.core.utils import to_slug
from nestbrain.core.pipeline_runner import PipelineRunner
from nestbrain.core.registry import PipelineRegistry
from nestbrain.core.stages.notebooklm_stage import generate_media


class FakeNotebookLMBridge:
    def __init__(self):
        self.calls: list[str] = []

    async def generate_media(self, notebook_id: str, media_type: str):
        self.calls.append(media_type)
        return {"status": "success", "artifactId": f"{media_type}-artifact"}

    async def download_media(self, notebook_id: str, media_type: str, artifact_id: str, output_path: str):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(f"{media_type}:{artifact_id}", encoding="utf-8")
        return output_path


def test_slugify_normalizes_punctuation_to_fallback_node():
    assert slugify("Hello, World!") == "hello-world"
    assert slugify("!!!") == "node"


def test_to_slug_handles_rag_title():
    assert to_slug("Retrieval-Augmented Generation (RAG)") == "retrieval-augmented-generation-rag"


def test_merge_into_existing_note_preserves_body_text_and_updates_sections():
    existing_content = (
        "---\n"
        "title: Sample\n"
        "last_updated: 2025-01-01T00:00:00\n"
        "notebooklm_video: assets/old-video.mp4\n"
        "notebooklm_audio: assets/old-audio.wav\n"
        "---\n\n"
        "# Sample\n\n"
        "Body text with last_updated: do not rewrite and notebooklm_video: keep this literal.\n\n"
        "## 🧠 Conceptual Deep Dive\n\n"
        "Existing deep dive.\n\n"
        "## 📚 Sources Index\n\n"
        "| # | Title | Type | Key | Date Added |\n"
        "|---|-------|------|-----|------------|\n"
        "| 1 | Old Item | 📄 PDF | OLD | 2025-01-01 |\n\n"
        "---\n\n"
        "## 🕐 Update Log\n\n"
        "| Date | Sources Added | Summary of Changes |\n"
        "|------|--------------|-------------------|\n"
    )

    synthesis = SynthesisResult(
        academic_synthesis="",
        conceptual_deep_dive="New deep dive content.",
        actionable_knowledge="New action item.",
        knowledge_connections="New connection.",
        critical_evaluation="New critique.",
        glossary="New glossary entry.",
    )
    new_items = [{"key": "NEW"}]
    all_items = [
        {"title": "Old Item", "item_type": "journalArticle", "key": "OLD", "date": "2025-01-01"},
        {"title": "New Item", "item_type": "webpage", "key": "NEW", "date": "2025-02-01"},
    ]

    updated = merge_into_existing_note(
        existing_content=existing_content,
        new_items=new_items,
        synthesis=synthesis,
        media_paths={"video": "assets/new-video.mp4", "audio": "assets/new-audio.wav"},
        all_items=all_items,
    )

    assert "last_updated: do not rewrite" in updated
    assert "notebooklm_video: keep this literal" in updated
    assert "assets/new-video.mp4" in updated
    assert "assets/new-audio.wav" in updated
    assert "New deep dive content." in updated
    assert "New Item" in updated


def test_registry_backups_corrupted_json_before_reset(tmp_path: Path):
    registry_file = tmp_path / "pipeline-registry.json"
    registry_file.write_text("{ invalid json", encoding="utf-8")

    registry = PipelineRegistry(registry_file)

    assert registry.data == {}
    backups = list(tmp_path.glob("pipeline-registry.corrupt_*.json"))
    assert backups, "expected a corruption backup file"
    assert backups[0].read_text(encoding="utf-8") == "{ invalid json"


def test_generate_media_downloads_video_and_audio(tmp_path: Path):
    bridge = FakeNotebookLMBridge()

    media_paths = __import__("asyncio").run(
        generate_media(bridge, "notebook-123", "Deep Learning", str(tmp_path))
    )

    assert bridge.calls == ["video", "audio"]
    assert media_paths == {
        "video": "assets/deep-learning-overview.mp4",
        "audio": "assets/deep-learning-overview.wav",
    }
    assert (tmp_path / "assets" / "deep-learning-overview.mp4").exists()
    assert (tmp_path / "assets" / "deep-learning-overview.wav").exists()


def test_pipeline_runner_coerces_payloads_for_graph_building():
    runner = PipelineRunner.__new__(PipelineRunner)

    notes = runner._coerce_notes(
        [
            {
                "path": "note.md",
                "title": "Graph Note",
                "tags": ["ai"],
                "wikilinks": ["Other Note"],
                "last_modified": "2026-04-08T00:00:00",
                "metadata": {"title": "Graph Note"},
                "content": "Graph content",
                "summary": "Summary",
                "semantic_tags": ["ml"],
            }
        ]
    )
    collections = runner._coerce_collections(
        [
            {
                "key": "COLL",
                "name": "Collection",
                "item_count": 1,
                "last_modified": "2026-04-08T00:00:00",
                "items": [
                    {
                        "key": "ITEM",
                        "title": "Reference Title",
                        "item_type": "journalArticle",
                        "creators": ["Ada Lovelace"],
                        "date": "2026",
                        "url": "https://example.com",
                        "abstract": "Reference abstract",
                        "collection_key": "COLL",
                    }
                ],
            }
        ]
    )

    assert notes[0].title == "Graph Note"
    assert collections[0].items[0].title == "Reference Title"
