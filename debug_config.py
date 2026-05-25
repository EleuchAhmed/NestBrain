#!/usr/bin/env python3
"""Debug the configuration loading."""

import os
import json
from pathlib import Path

# Add the nestbrain module to path
import sys
sys.path.insert(0, "/mnt/c/Users/Mega Pc/Desktop/research-pipeline")

print("Debugging configuration loading...\n")

# Check environment variables
print("Environment variables:")
print(f"  NVIDIA_API_KEY: {'SET' if os.getenv('NVIDIA_API_KEY') else 'NOT SET'}")
print(f"  OLLAMA_HOST: {os.getenv('OLLAMA_HOST', 'NOT SET')}")

# Check config.json directly
config_path = Path("/mnt/c/Users/Mega Pc/Desktop/research-pipeline/nestbrain/config.json")
print(f"\nChecking config file at: {config_path}")
if config_path.exists():
    with open(config_path) as f:
        config = json.load(f)
    print(f"  nvidia_api_key: {'SET' if config.get('nvidia_api_key') else 'EMPTY'}")
    print(f"  ollama_host: {config.get('ollama_host', 'NOT SET')}")
    print(f"  nvidia_host: {config.get('nvidia_host', 'NOT SET')}")
else:
    print(f"  Config file not found!")

# Now check what the _init_hybrid_client function would do
print("\nSimulating _init_hybrid_client():")
nvidia_api_key = os.getenv("NVIDIA_API_KEY", "")
ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
print(f"  Initial nvidia_api_key from env: {'SET' if nvidia_api_key else 'EMPTY'}")
print(f"  Initial ollama_host from env: {ollama_host}")

try:
    from nestbrain.core.paths import get_config_path
    config_file = get_config_path()
    print(f"  Config file path from get_config_path(): {config_file}")
    if config_file.exists():
        with open(config_file) as f:
            config = json.load(f)
            print(f"  Config loaded successfully")
            if not nvidia_api_key and config.get("nvidia_api_key"):
                nvidia_api_key = config["nvidia_api_key"]
                print(f"    Set nvidia_api_key from config: {'SET' if nvidia_api_key else 'EMPTY'}")
            if config.get("ollama_host"):
                print(f"    Config ollama_host value: {config.get('ollama_host')}")
                ollama_host = config["ollama_host"]
                print(f"    Set ollama_host from config: {ollama_host}")
    else:
        print(f"  Config file does not exist at: {config_file}")
except Exception as e:
    print(f"  Error loading config: {e}")
    import traceback
    traceback.print_exc()

print(f"\nFinal values:")
print(f"  nvidia_api_key: {'SET' if nvidia_api_key else 'EMPTY'}")
print(f"  ollama_host: {ollama_host}")
