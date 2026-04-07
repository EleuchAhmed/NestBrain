from __future__ import annotations

from dataclasses import asdict
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from ..core.errors import build_error_payload
from ..core.knowledge_graph import KnowledgeGraphBuilder
from ..core.obsidian_parser import ObsidianNote
from ..core.zotero_sync import ZoteroCollection, ZoteroItem


class GraphWorker(QObject):
    graph_ready = pyqtSignal(dict)
    error = pyqtSignal(dict)
    finished = pyqtSignal()

    def __init__(self, notes_payload: list[dict[str, Any]], collections_payload: list[dict[str, Any]]) -> None:
        super().__init__()
        self.notes_payload = notes_payload
        self.collections_payload = collections_payload

    @pyqtSlot()
    def run(self) -> None:
        try:
            notes = [
                ObsidianNote(
                    path=str(note.get("path", "")),
                    title=str(note.get("title", "Untitled")),
                    tags=list(note.get("tags", [])),
                    wikilinks=list(note.get("wikilinks", [])),
                    last_modified=str(note.get("last_modified", "")),
                    metadata=dict(note.get("metadata", {})),
                    content=str(note.get("content", "")),
                    summary=str(note.get("summary", "")),
                    semantic_tags=list(note.get("semantic_tags", [])),
                )
                for note in self.notes_payload
            ]

            collections: list[ZoteroCollection] = []
            for collection in self.collections_payload:
                items = [
                    ZoteroItem(
                        key=str(item.get("key", "")),
                        title=str(item.get("title", "Untitled Reference")),
                        item_type=str(item.get("item_type", "item")),
                        creators=list(item.get("creators", [])),
                        date=str(item.get("date", "")),
                        url=str(item.get("url", "")),
                        abstract=str(item.get("abstract", "")),
                        collection_key=str(item.get("collection_key", "")),
                    )
                    for item in collection.get("items", [])
                ]
                collections.append(
                    ZoteroCollection(
                        key=str(collection.get("key", "")),
                        name=str(collection.get("name", "Untitled Collection")),
                        item_count=int(collection.get("item_count", len(items))),
                        last_modified=str(collection.get("last_modified", "")),
                        status=str(collection.get("status", "Idle")),
                        items=items,
                    )
                )

            graph_payload = KnowledgeGraphBuilder().build(notes, collections)
            self.graph_ready.emit(graph_payload)
        except Exception as exc:
            self.error.emit(build_error_payload(exc, source="graph_worker"))
        finally:
            self.finished.emit()
