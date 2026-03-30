from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import re
from typing import Any

from .obsidian_parser import ObsidianNote
from .zotero_sync import ZoteroCollection


@dataclass(slots=True)
class GraphNode:
    id: str
    label: str
    node_type: str
    summary: str
    metadata: dict[str, Any]


@dataclass(slots=True)
class GraphEdge:
    source: str
    target: str
    weight: float
    reason: str


class KnowledgeGraphBuilder:
    """Build graph payload from notes, references, and semantic links."""

    NODE_COLORS = {
        "note": (0.63, 0.50, 0.95, 1.0),
        "reference": (0.40, 0.75, 1.00, 1.0),
        "cluster": (0.85, 0.60, 0.40, 1.0),
    }

    def build(
        self,
        notes: list[ObsidianNote],
        collections: list[ZoteroCollection],
        semantic_links: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        semantic_links = semantic_links or []
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        node_by_label: dict[str, str] = {}

        for note in notes:
            node_id = f"note::{self._slugify(note.title)}"
            nodes.append(
                GraphNode(
                    id=node_id,
                    label=note.title,
                    node_type="note",
                    summary=note.summary,
                    metadata={
                        "path": note.path,
                        "tags": note.tags,
                        "wikilinks": note.wikilinks,
                        "semantic_tags": note.semantic_tags,
                    },
                )
            )
            node_by_label[note.title.lower()] = node_id

        references = []
        for collection in collections:
            for item in collection.items:
                references.append((collection, item))

        for collection, item in references:
            label = item.title.strip() or item.key
            node_id = f"ref::{item.key}"
            nodes.append(
                GraphNode(
                    id=node_id,
                    label=label,
                    node_type="reference",
                    summary=item.abstract,
                    metadata={
                        "collection": collection.name,
                        "creators": item.creators,
                        "date": item.date,
                        "url": item.url,
                        "type": item.item_type,
                    },
                )
            )
            node_by_label[label.lower()] = node_id

        edges.extend(self._build_wikilink_edges(notes))
        edges.extend(self._build_tag_similarity_edges(notes))
        edges.extend(self._build_reference_edges(notes, collections))
        edges.extend(self._build_semantic_edges(semantic_links, node_by_label))

        cluster_nodes, cluster_edges = self._build_cluster_nodes(notes)
        nodes.extend(cluster_nodes)
        edges.extend(cluster_edges)

        deduped_edges = self._dedupe_edges(edges)
        node_degrees = self._calculate_degrees(nodes, deduped_edges)

        serialized_nodes = []
        for node in nodes:
            serialized_nodes.append(
                {
                    "id": node.id,
                    "label": node.label,
                    "type": node.node_type,
                    "summary": node.summary,
                    "metadata": node.metadata,
                    "color": self.NODE_COLORS.get(node.node_type, (0.7, 0.7, 0.7, 1.0)),
                    "degree": node_degrees.get(node.id, 0),
                }
            )

        serialized_edges = [
            {
                "source": edge.source,
                "target": edge.target,
                "weight": edge.weight,
                "reason": edge.reason,
            }
            for edge in deduped_edges
        ]

        return {
            "nodes": serialized_nodes,
            "edges": serialized_edges,
        }

    def _build_wikilink_edges(self, notes: list[ObsidianNote]) -> list[GraphEdge]:
        title_to_id = {note.title.lower(): f"note::{self._slugify(note.title)}" for note in notes}
        edges: list[GraphEdge] = []

        for note in notes:
            source_id = f"note::{self._slugify(note.title)}"
            for link in note.wikilinks:
                target_id = title_to_id.get(link.lower())
                if target_id and target_id != source_id:
                    edges.append(GraphEdge(source=source_id, target=target_id, weight=1.0, reason="wikilink"))

        return edges

    def _build_tag_similarity_edges(self, notes: list[ObsidianNote]) -> list[GraphEdge]:
        edges: list[GraphEdge] = []
        for idx, left in enumerate(notes):
            left_tags = set(left.tags + left.semantic_tags)
            if not left_tags:
                continue
            left_id = f"note::{self._slugify(left.title)}"

            for right in notes[idx + 1 :]:
                right_tags = set(right.tags + right.semantic_tags)
                if not right_tags:
                    continue
                overlap = left_tags.intersection(right_tags)
                if overlap:
                    weight = min(2.0, 0.4 + len(overlap) * 0.3)
                    right_id = f"note::{self._slugify(right.title)}"
                    edges.append(
                        GraphEdge(
                            source=left_id,
                            target=right_id,
                            weight=weight,
                            reason=f"shared tags: {', '.join(sorted(overlap)[:4])}",
                        )
                    )

        return edges

    def _build_reference_edges(self, notes: list[ObsidianNote], collections: list[ZoteroCollection]) -> list[GraphEdge]:
        note_tokens: dict[str, set[str]] = {
            f"note::{self._slugify(note.title)}": self._tokenize(" ".join([note.title, note.content]))
            for note in notes
        }

        edges: list[GraphEdge] = []
        for collection in collections:
            for item in collection.items:
                ref_id = f"ref::{item.key}"
                reference_tokens = self._tokenize(" ".join([item.title, item.abstract, " ".join(item.creators)]))
                if not reference_tokens:
                    continue

                for note_id, tokens in note_tokens.items():
                    overlap = tokens.intersection(reference_tokens)
                    if len(overlap) >= 3:
                        edges.append(
                            GraphEdge(
                                source=note_id,
                                target=ref_id,
                                weight=min(2.2, 0.7 + len(overlap) * 0.08),
                                reason="semantic overlap",
                            )
                        )

        return edges

    def _build_semantic_edges(self, semantic_links: list[dict[str, str]], node_by_label: dict[str, str]) -> list[GraphEdge]:
        edges: list[GraphEdge] = []
        for link in semantic_links:
            source_label = str(link.get("source", "")).strip().lower()
            target_label = str(link.get("target", "")).strip().lower()
            reason = str(link.get("reason", "")).strip() or "ai semantic link"
            source = node_by_label.get(source_label)
            target = node_by_label.get(target_label)
            if source and target and source != target:
                edges.append(GraphEdge(source=source, target=target, weight=1.8, reason=reason))
        return edges

    def _build_cluster_nodes(self, notes: list[ObsidianNote]) -> tuple[list[GraphNode], list[GraphEdge]]:
        combined_tags: list[str] = []
        for note in notes:
            combined_tags.extend(note.tags)
            combined_tags.extend(note.semantic_tags)

        top_tags = [tag for tag, _ in Counter(combined_tags).most_common(3)]
        if not top_tags:
            return [], []

        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        for tag in top_tags:
            cluster_id = f"cluster::{self._slugify(tag)}"
            nodes.append(
                GraphNode(
                    id=cluster_id,
                    label=f"Cluster: {tag}",
                    node_type="cluster",
                    summary=f"AI-generated cluster for {tag}",
                    metadata={"tag": tag},
                )
            )

            for note in notes:
                if tag in note.tags or tag in note.semantic_tags:
                    note_id = f"note::{self._slugify(note.title)}"
                    edges.append(GraphEdge(source=cluster_id, target=note_id, weight=1.1, reason="cluster membership"))

        return nodes, edges

    def _dedupe_edges(self, edges: list[GraphEdge]) -> list[GraphEdge]:
        merged: dict[tuple[str, str], GraphEdge] = {}
        for edge in edges:
            key = tuple(sorted((edge.source, edge.target)))
            existing = merged.get(key)
            if existing is None:
                merged[key] = edge
                continue

            existing.weight = max(existing.weight, edge.weight)
            if edge.reason not in existing.reason:
                existing.reason = f"{existing.reason}; {edge.reason}"

        return list(merged.values())

    def _calculate_degrees(self, nodes: list[GraphNode], edges: list[GraphEdge]) -> dict[str, int]:
        degree_map: dict[str, int] = defaultdict(int)
        node_ids = {node.id for node in nodes}

        for edge in edges:
            if edge.source in node_ids:
                degree_map[edge.source] += 1
            if edge.target in node_ids:
                degree_map[edge.target] += 1

        return dict(degree_map)

    def _tokenize(self, text: str) -> set[str]:
        tokens = re.findall(r"[A-Za-z][A-Za-z\-]{2,}", text.lower())
        stop_words = {
            "the",
            "and",
            "that",
            "from",
            "with",
            "this",
            "into",
            "using",
            "their",
            "have",
            "such",
            "were",
            "which",
            "about",
            "also",
            "into",
            "between",
        }
        return {token for token in tokens if token not in stop_words}

    def _slugify(self, text: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
        return cleaned.strip("-") or "node"
