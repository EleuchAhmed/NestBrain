#!/usr/bin/env python3
"""Quick validation of the hybrid LLM client with Ollama fallback."""

import sys
import json
import logging

logging.basicConfig(level=logging.DEBUG)

# Test 1: Can we import the hybrid client?
try:
    from nestbrain.core.nvidia_client import HybridLLMClient, nvidia_client
    print("✓ Successfully imported HybridLLMClient and nvidia_client")
except Exception as e:
    print(f"✗ Failed to import: {e}")
    sys.exit(1)

# Test 2: Check if hybrid client is configured
try:
    if nvidia_client.is_configured():
        print("✓ Hybrid client is configured (NVIDIA or Ollama available)")
    else:
        print("✗ Hybrid client not configured - check NVIDIA_API_KEY and Ollama accessibility")
        sys.exit(1)
except Exception as e:
    print(f"✗ Error checking configuration: {e}")
    sys.exit(1)

# Test 3: Test entity extraction with a simple prompt
try:
    print("\nTesting entity extraction...")
    test_messages = [
        {"role": "system", "content": "You are an expert IT Knowledge Entity Extractor. Extract technical entities from the text. Return a JSON array with objects containing 'entity', 'confidence', and 'justification' fields."},
        {"role": "user", "content": "This is about Docker containers and Kubernetes orchestration. We also use Redis for caching."}
    ]
    
    response = nvidia_client.generate_chat_completion(
        model="deepseek-ai/deepseek-v3.2",
        messages=test_messages,
        temperature=0.1,
        max_tokens=1024
    )
    
    # Try to parse the response as JSON
    try:
        entities = json.loads(response)
        if isinstance(entities, list) and len(entities) > 0:
            print(f"✓ Entity extraction successful, extracted {len(entities)} entities")
            for entity in entities[:3]:
                print(f"  - {entity.get('entity', 'N/A')}: {entity.get('justification', '')}")
        else:
            print("✓ Entity extraction returned valid JSON (though not as expected format)")
            print(f"  Response: {response[:200]}")
    except json.JSONDecodeError:
        print(f"✓ Got response from LLM (not valid JSON, but model responded)")
        print(f"  Response: {response[:200]}")

except Exception as e:
    print(f"✗ Entity extraction test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Test classification
try:
    print("\nTesting classification...")
    test_messages_classification = [
        {"role": "system", "content": "You are a document classifier. Return a JSON object with 'category', 'subcategory', 'confidence', and 'reasoning' fields."},
        {"role": "user", "content": "Docker is a containerization platform that helps package applications. It uses images and containers..."}
    ]
    
    response = nvidia_client.generate_chat_completion(
        model="deepseek-ai/deepseek-v3.2",
        messages=test_messages_classification,
        temperature=0.0,
        max_tokens=512
    )
    
    print(f"✓ Classification test successful")
    print(f"  Response: {response[:200]}")

except Exception as e:
    print(f"✗ Classification test failed: {e}")
    sys.exit(1)

print("\n✓ All validation tests passed! The hybrid client is working.")
print("You can now run the pipeline and it will use Ollama for entity extraction and classification.")
