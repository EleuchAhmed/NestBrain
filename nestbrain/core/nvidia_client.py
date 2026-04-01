import os
import json
import logging
from typing import Dict, Any, List, Optional
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

class NvidiaNIMClient:
    """Client for interfacing with NVIDIA NIM serverless endpoints."""
    
    BASE_URL = "https://integrate.api.nvidia.com/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("NVIDIA_API_KEY")
        if not self.api_key:
            logger.warning("NVIDIA_API_KEY is not set. API calls will fail.")

    def generate_chat_completion(self, model: str, messages: List[Dict[str, str]], 
                                 temperature: float = 0.7, max_tokens: int = 1024,
                                 response_format: Optional[Dict[str, str]] = None) -> str:
        """Execute a chat completion request against a NIM model."""
        url = f"{self.BASE_URL}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        if response_format:
            payload["response_format"] = response_format

        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result['choices'][0]['message']['content']
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            logger.error(f"NVIDIA API Error ({e.code}): {error_body}")
            raise Exception(f"NVIDIA API call failed: {error_body}")
        except Exception as e:
            logger.error(f"Failed to connect to NVIDIA NIM: {e}")
            raise

    def generate_embeddings(self, model: str, input_texts: List[str], input_type: str = "query") -> List[List[float]]:
        """Execute an embedding request against a NIM model."""
        url = f"{self.BASE_URL}/embeddings"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Depending on nv-embedqa, input_type may be required or implicit
        payload = {
            "model": model,
            "input": input_texts,
            "input_type": input_type,
            "encoding_format": "float"
        }

        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                return [item['embedding'] for item in result['data']]
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            logger.error(f"NVIDIA API Error ({e.code}): {error_body}")
            raise Exception(f"NVIDIA API call failed: {error_body}")
        except Exception as e:
            logger.error(f"Failed to connect to NVIDIA NIM: {e}")
            raise

    def rerank(self, model: str, query: str, passages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank passages using a reranker model like rerank-qa-mistral-4b."""
        url = f"{self.BASE_URL}/ranking"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        payload = {
            "model": model,
            "query": {"text": query},
            "passages": [{"text": p.get("text", "")} for p in passages]
        }

        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                # Result typically contains a "rankings" array of objects with "index" and "logit"
                return result.get('rankings', [])
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            logger.error(f"NVIDIA API Error ({e.code}): {error_body}")
            raise Exception(f"NVIDIA API call failed: {error_body}")
        except Exception as e:
            logger.error(f"Failed to connect to NVIDIA NIM: {e}")
            raise

nvidia_client = NvidiaNIMClient()
