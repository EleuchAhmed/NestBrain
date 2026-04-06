"""CLI test runner for v2 pipeline with debug output."""
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from nestbrain.core.pipeline_runner import load_config, ensure_config
from nestbrain.core.v2_workflow import PipelineWorkflowV2
from nestbrain.core.zotero_sync import ZoteroSyncClient
from nestbrain.core.ollama_client import OllamaClient

async def main():
    app_root = Path(__file__).resolve().parent
    config_path = ensure_config(app_root)
    config = load_config(config_path)
    
    print(f"DEBUG:STARTUP - Config loaded from {config_path}")
    print(f"DEBUG:STARTUP - Vault path: {config.vault_path}")
    print(f"DEBUG:STARTUP - Zotero host: {config.zotero_host}")
    
    # Initialize clients
    zotero = ZoteroSyncClient(
        library_id=config.zotero_library_id,
        api_key=config.zotero_api_key,
        host=config.zotero_host
    )
    
    ollama = OllamaClient(host=config.ollama_host, api_key=config.nvidia_api_key)
    
    workflow = PipelineWorkflowV2(app_root=app_root)
    
    print(f"DEBUG:STARTUP - PipelineWorkflowV2 created")
    print(f"DEBUG:STARTUP - Zotero and Ollama clients initialized")
    
    def status_callback(msg: str):
        print(f"STATUS:{msg}")
    
    def progress_callback(pct: int):
        print(f"PROGRESS:{pct}")
    
    print(f"DEBUG:STARTUP - Starting run_full_pipeline")
    result = await workflow.run_full_pipeline(
        vault_path=config.vault_path,
        zotero=zotero,
        ollama=ollama,
        selected_collection_key=config.selected_collection_key,
        progress_callback=progress_callback,
        status_callback=status_callback
    )
    print(f"DEBUG:STARTUP - Pipeline completed with result: {result}")

if __name__ == "__main__":
    print("DEBUG:MAIN - Test pipeline CLI starting")
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"ERROR:MAIN - {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
