# Pipeline Context

Design intent document. This file captures target architecture direction. For current implementation truth, use ARCHITECTURE.md, README.md, and nestbrain/core/workflow_engine.py.

What you're building
A self-expanding, interconnected knowledge graph in a note vault, where an AI agent researches, links, and propagates knowledge across the vault automatically.

Current state
- User inputs a subject.
- PipelineRunner validates vault and delegates to PipelineWorkflow in workflow_engine.py.
- Workflow syncs Zotero collections and ingests new sources into NotebookLM.
- Question planner builds research taxonomy, Q&A loop runs iterative interrogation, and master synthesizer builds the deep-dive note body.
- Entity extraction and NoteSeeder create or merge concept notes.
- Notewriter stage renders collection note, then vault_manager classifies and files it.
- L3 propagation runs vector indexing, semantic auditing, and connection annotation for related notes.

Target state - the three layers
Layer 1 - Dynamic deep research per subject
Instead of one query, the AI runs a research session. It starts with a planning step: given the subject, what are the essential questions to fully cover it? It then queries NotebookLM iteratively until coverage is deemed complete. The result is a rich, multi-angle note rather than a shallow summary.

Layer 2 - Automatic term detection and linked note creation
After the master note is synthesized, the AI scans it for knowledge entities. For each detected entity:
- Check the vault index.
- If no note exists, create a new note populated from both NotebookLM and the model's own knowledge.
- If a note exists, append a new section to that existing note with information relevant to the current subject.
- Inject a backlink to the subject note.

Layer 3 - Vault-wide propagation on every new note
When any note is created or updated, the AI runs a semantic similarity pass over the vault index to surface related notes. For each related note found above a relevance threshold:
- Add a mention of the new note.
- Optionally append a short explanation of the connection.
- Log what was updated so the user can review changes.

Implementation note: Layer 3 is implemented through vector_indexer.py, semantic_auditor.py, and connection_annotator.py. It operates on candidate matches and does not yet provide a separate user-facing propagation report beyond note updates and existing logs.

Architecture decisions to make
- Vault index format: full text vs embeddings.
- Term detection method: regex/NLP vs model extraction.
- Existing note update strategy: append only vs full rewrite.
- Relevance threshold for vault scan: fixed cutoff vs top-K.
- Session management: one session per subject vs shared.

Data flow per note creation event
Subject input
-> Question planner
-> NotebookLM loop
-> Master note synthesizer
-> Term detector
-> For each term:
   vault_index.check(term)
   -> [new] create_note(term, NotebookLM + model knowledge)
   -> [exists] patch_note(term, new_context) + inject_backlink
-> Vault scanner
   -> For each related note above threshold:
      update_note(related, mention_new_note)

What to build first
1. Layer 1 - iterative Q&A loop.
2. Vault index - build the embedding index.
3. Layer 2 (new note path only) - term detection and new note creation.
4. Layer 2 (patch path) - enrich existing notes.
5. Layer 3 - vault-wide propagation.

Component context
- Question planner: subject name, source summary, question taxonomy.
- NotebookLM loop: current question, previous Q&A pairs.
- Master note synthesizer: all Q&A pairs, subject name, note template.
- Term detector: full master note text, list of terms already in the vault.
- Vault scanner: new note summary/embedding, full vault index.
- Note patcher: existing note content, new context snippet, subject note title.
