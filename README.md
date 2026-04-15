# Nestbrain Research Pipeline

Nestbrain is a professional, standalone desktop application built with Python and PyQt6. It acts as an automated bridge between your reference managers (Zotero), reading platforms (NotebookLM), local Large Language Models (Ollama), and markdown note systems.

By running Nestbrain, you automate the extraction, synthesis, and writing of academic notes directly into your note vault.

## Vault System

On first launch, Nestbrain creates a single vault named `My Brain` in the app's user-data area. On Windows, that defaults to `%APPDATA%/Nestbrain/My Brain`.

The vault starts with only a root `README.md`. The AI classifier creates subfolders automatically when notes are filed, so the root stays clean and no taxonomy folders are pre-created.

Every filed note gets an AI classification footer and an audit record in `vault_log.jsonl`.

## Features
- **Standalone Architecture:** Single-click PyInstaller executable; no Node.js or TypeScript required.
- **Native Browser Automation:** Uses underlying Playwright libraries combined with native `notebooklm-py` API for NotebookLM synchronization.
- **DeepSeek Integration:** Summarizes references using NVIDIA NIM DeepSeek V3.1 via API.
- **Zotero & Note Bridges:** Automatically pulls recent Zotero highlights, generates rich conceptual notes, and deposits them cleanly formatted into the note vault.

## Requirements

1. **Python 3.11+** (if running from source)
2. **NVIDIA API Key**: Must provide `NVIDIA_API_KEY` environment variable.
3. **Zotero**: Should be running locally (default: `http://localhost:23119`) with API integrations enabled.
4. **NotebookLM**: You must manually authenticate to NotebookLM the first time via the App's browser context.

## Local Development Setup

To run from source:
```bash
# 1. Clone repository
git clone https://github.com/EleuchAhmed/NestBrain.git
cd NestBrain

# 2. Setup Virtual Environment
python -m venv .venv
.venv\Scripts\activate  # Windows

# 3. Install Dependencies
pip install -r nestbrain/requirements.txt
playwright install chromium

# 4. Copy Environment configuration
cp .env.example .env
# Edit .env with your specific paths and API keys

# 5. Run the app
python -m nestbrain.main
```

## Packaging (Releasing the Executable)

Nestbrain uses `PyInstaller` for packaging.

To build the executable:
```cmd
.\scripts\build.bat
```
The standalone `.exe` will be located in `scripts\dist\Nestbrain.exe`. You can distribute this single file directly.

## Environment Variables (.env)
- `NOTE_VAULT_PATH`: Absolute path to your note vault.
- `ZOTERO_LIBRARY_ID` and `ZOTERO_API_KEY`: Credentials for Zotero sync.
- `NVIDIA_API_KEY`: Your NVIDIA NIM API key for DeepSeek V3.1.

## Architecture
- **Application Core**: `nestbrain/main.py`
- **GUI Views**: `nestbrain/views/`
- **Business Logic**: `nestbrain/core/workflow.py`, `nestbrain/core/pipeline_runner.py`
- **NotebookLM Wrapper**: `nestbrain/core/notebooklm_bridge.py`
- **Vault Policy Layer**: `nestbrain/core/vault_manager.py`

## License
MIT
