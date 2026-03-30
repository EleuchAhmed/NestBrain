#!/usr/bin/env python3
"""Fix the errors dict in pipeline_runner.py to include vault key."""

filepath = 'nestbrain/core/pipeline_runner.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the final return dict errors to include vault key
old_pattern = '''            "errors": {
                "zotero": zotero_error,
                "ollama": ollama_error,
            },
        }

    def load_archive'''

new_pattern = '''            "errors": {
                "zotero": zotero_error,
                "ollama": ollama_error,
                "vault": "",
            },
        }

    def load_archive'''

content = content.replace(old_pattern, new_pattern)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated pipeline_runner.py - added vault key to errors dict")
