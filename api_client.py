import requests
from typing import Optional, Dict, Any
import json

class APIClient:
    def __init__(self, api_url: str):
        """Initialize APIClient with API URL."""
        self.api_url = api_url

    def call_api(self, query: str, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Call the Lambda function through API Gateway."""
        try:
            request_body = {
                "user_query": query
            }
            if session_id:
                request_body["sessionId"] = session_id
                
            response = requests.post(
                url=self.api_url,
                headers={"Content-Type": "application/json"},
                json=request_body,
                timeout=30
            )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"API Error: {str(e)}")
            return None
