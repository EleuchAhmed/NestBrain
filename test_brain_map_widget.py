from nestbrain.ui.brain_map_colors import CATEGORY_COLORS, UNCATEGORIZED_CATEGORY
from nestbrain.ui.brain_map_widget import CategoryColorManager, _extract_category_from_note_path, _resolve_note_path


def test_resolve_note_path_prefers_top_level_path():
    payload = {
        "path": "C:/vault/Software Engineering & Development/Backend/note.md",
        "metadata": {"path": "C:/vault/Other/Note.md"},
    }

    assert _resolve_note_path(payload) == "C:/vault/Software Engineering & Development/Backend/note.md"


def test_resolve_note_path_reads_metadata_path_when_top_level_missing():
    payload = {
        "metadata": {"path": "C:/vault/Artificial Intelligence & Data/LLMs/note.md"},
    }

    assert _resolve_note_path(payload) == "C:/vault/Artificial Intelligence & Data/LLMs/note.md"


def test_resolve_note_path_reads_metadata_note_path_when_needed():
    payload = {
        "metadata": {"note_path": "C:/vault/Design & User Experience/UI/note.md"},
    }

    assert _resolve_note_path(payload) == "C:/vault/Design & User Experience/UI/note.md"


def test_extract_category_from_note_path_returns_folder_name():
    note_path = "C:/vault/Cloud Computing & Infrastructure/Cloud Architecture/note.md"

    assert _extract_category_from_note_path(note_path, vault_root_index=1) == "Cloud Architecture"


def test_extract_category_from_note_path_prefers_known_subcategory():
    note_path = "C:/vault/Artificial Intelligence & Data/Machine Learning (ML)/note.md"

    assert _extract_category_from_note_path(note_path, vault_root_index=1) == "Machine Learning (ML)"


def test_extract_category_from_note_path_falls_back_to_parent_category():
    note_path = "C:/vault/Software Engineering & Development/Unknown Folder/note.md"

    assert _extract_category_from_note_path(note_path, vault_root_index=1) == "Software Engineering & Development"


def test_extract_category_from_note_path_falls_back_when_missing():
    assert _extract_category_from_note_path("", vault_root_index=0) == "Uncategorized"


def test_category_color_manager_uses_exact_taxonomy_color():
    manager = CategoryColorManager()

    color = manager.get_color("Cloud Computing & Infrastructure")

    assert color.name().lower() == CATEGORY_COLORS["Cloud Computing & Infrastructure"].lower()


def test_category_color_manager_falls_back_to_uncategorized_color():
    manager = CategoryColorManager()

    color = manager.get_color("Unknown Category")

    assert color.name().lower() == CATEGORY_COLORS[UNCATEGORIZED_CATEGORY].lower()