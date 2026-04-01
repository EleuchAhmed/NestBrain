What you're building
A self-expanding, interconnected knowledge graph in Obsidian, where an AI agent doesn't just transcribe — it researches, links, and propagates knowledge across your entire vault automatically.

Current state (v1)

User inputs a subject
AI queries NotebookLM once
AI writes a single note to Obsidian


Target state (v2) — the three layers
Layer 1 — Dynamic deep research per subject
Instead of one query, the AI runs a research session. It starts with a planning step: given the subject, what are the essential questions to fully cover it? (definitions, use cases, tradeoffs, dependencies, history, code patterns, etc.) It then queries NotebookLM iteratively — each answer may trigger a follow-up question — until coverage is deemed complete. The result is a rich, multi-angle note rather than a shallow summary.
Key design decision: the planner should use a structured question taxonomy (what / why / how / when / compare / limitations) to avoid blind spots.
Layer 2 — Automatic term detection and linked note creation
After the master note is synthesized, the AI scans it for knowledge entities: technical terms, algorithm names, frameworks, protocols, people, papers. For each detected entity:

Check the vault index → does a note for this entity already exist?
If no: create a new note populated from both NotebookLM (ask it about the term in context) and the model's own knowledge. Link it bidirectionally to the subject note.
If yes: append a new section to that existing note with information specifically relevant to the current subject. Inject a [[Subject]] backlink. Do not overwrite — only enrich.

This turns every new note into a seed that grows the graph outward.
Layer 3 — Vault-wide propagation on every new note
When any note is created or updated, the AI runs a semantic similarity pass over the vault index to surface related notes (not just exact keyword matches). For each related note found above a relevance threshold:

Add a mention of the new note ([[New Note]]) in the appropriate section
Optionally append a one-sentence "see also" annotation explaining the connection
Log what was updated so the user can review changes

This ensures the graph stays consistent — no orphaned notes, no missed connections.

Architecture decisions to make
DecisionOptionsRecommendationVault index formatFull text vs. embeddingsEmbeddings (semantic search, more robust)Term detection methodRegex/NLP vs. LLM extractionLLM extraction pass (more context-aware)Existing note update strategyAppend only vs. full rewriteAppend only (non-destructive, auditable)Relevance threshold for vault scanFixed cutoff vs. top-KTop-K with a minimum score floorNotebookLM session managementOne session per subject vs. sharedOne session per subject (clean context)

Data flow per note creation event
Subject input
  → Question planner (generates N questions)
    → NotebookLM loop (iterative Q&A)
      → Master note synthesizer
        → Term detector
          → For each term:
              vault_index.check(term)
              → [new]     create_note(term, notebooklm + model knowledge)
              → [exists]  patch_note(term, new_context) + inject_backlink
        → Vault scanner (semantic similarity)
          → For each related note above threshold:
              update_note(related, mention_new_note)

What to build first (suggested order)

Layer 1 — the iterative Q&A loop is the highest-value, lowest-risk improvement. Everything else builds on better raw content.
Vault index — build the embedding index before Layers 2/3, since both depend on it.
Layer 2 (new note path only) — term detection + new note creation, without the patching logic.
Layer 2 (patch path) — add the "note already exists → enrich it" logic.
Layer 3 — vault-wide propagation. Most complex; needs the index mature.


What each component needs to know (context per call)
ComponentContext requiredQuestion plannerSubject name, source document summary, question taxonomyNotebookLM loopCurrent question, previous Q&A pairs in sessionMaster note synthesizerAll Q&A pairs, subject name, note templateTerm detectorFull master note text, list of terms already in vaultVault scannerNew note summary/embedding, full vault indexNote patcherExisting note content, new context snippet, subject note title