"""Test NVIDIA API connectivity"""
import urllib.request
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
import os

sys.path.insert(0, str(Path(__file__).parent))
load_dotenv()

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
print(f"DEBUG: API key present: {bool(NVIDIA_API_KEY)}")

if not NVIDIA_API_KEY:
    print("ERROR: NVIDIA_API_KEY not set in .env")
    sys.exit(1)

url = "https://integrate.api.nvidia.com/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {NVIDIA_API_KEY}",
    "Content-Type": "application/json",
}

payload = {
    "model": "deepseek-ai/deepseek-v3.2",
    "messages": [
        {"role": "user", "content": "Say hello"}
    ],
    "temperature": 0.3,
    "max_tokens": 100,
}

print(f"DEBUG: Testing NVIDIA API endpoint: {url}")
print(f"DEBUG: With model: deepseek-ai/deepseek-v3.2")

try:
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
    print(f"DEBUG: Request built, about to call urlopen with timeout=30s")
    
    with urllib.request.urlopen(req, timeout=30) as response:
        print(f"DEBUG: Got response!")
        result = json.loads(response.read().decode('utf-8'))
        print(f"SUCCESS: API responded: {result.get('choices', [{}])[0].get('message', {}).get('content', '')[:100]}")
        
except urllib.error.HTTPError as e:
    error_body = e.read().decode('utf-8')
    print(f"HTTP ERROR {e.code}: {error_body[:200]}")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
